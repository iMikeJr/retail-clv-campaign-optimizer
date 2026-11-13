"""Load the supplied workbook, apply audited rules, and publish customer RFM."""

import os
import sys
import math
from bisect import bisect_left
from datetime import date
from pathlib import Path

import pandas as pd
from psycopg import sql
from sqlalchemy import URL, create_engine


SHEET_ROWS = {"Year 2009-2010": 525_461, "Year 2010-2011": 541_910}
COLUMNS = {
    "Invoice": "invoice", "StockCode": "stockcode", "Description": "description",
    "Quantity": "quantity", "InvoiceDate": "invoice_date", "Price": "price",
    "Customer ID": "customer_id", "Country": "country",
}
READ_DTYPES = {
    "Invoice": "string", "StockCode": "string", "Customer ID": "Int64",
    "Description": "string", "Country": "string",
}


class ETLError(Exception):
    """A validation error whose message is safe to print without credentials."""


def load_workbook(path):
    """Keep every source row, with typed identifiers and Excel row provenance."""
    if not path.is_file():
        raise ETLError("Missing data/raw/online_retail_II.xlsx; supply it locally.")
    frames = []
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        for sheet, expected in SHEET_ROWS.items():
            if sheet not in workbook.sheet_names:
                raise ETLError(f"Missing sheet: {sheet}.")
            frame = pd.read_excel(
                workbook, sheet_name=sheet, dtype=READ_DTYPES,
                # Only empty cells are missing; literal text such as 'NA' is kept.
                keep_default_na=False, na_values=[""],
            )
            if list(frame.columns) != list(COLUMNS):
                raise ETLError(f"Unexpected columns in {sheet}; expected the eight source columns.")
            if len(frame) != expected:
                raise ETLError(
                    f"Row count mismatch in {sheet}: expected {expected:,}, got {len(frame):,}. "
                    f"The workbook must contain {sum(SHEET_ROWS.values()):,} data rows."
                )
            frame = frame.rename(columns=COLUMNS)
            # Nullable Int64 prevents guest IDs becoming 'nan' or IDs like '12345.0'.
            frame["customer_id"] = frame["customer_id"].astype("string")
            frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="raise")
            frame["source_sheet"] = sheet
            # Excel row 1 is the header; the first data row is row 2.
            frame["source_row"] = range(2, len(frame) + 2)
            frames.append(frame)
            print(f"Loaded {sheet}: {len(frame):,} rows", flush=True)
    return pd.concat(frames, ignore_index=True)


def overlap_mask(raw):
    """Identify one-to-one second-sheet copies without removing within-sheet repeats."""
    raw = raw.sort_values(["source_sheet", "source_row"])
    columns = list(COLUMNS.values())
    numbered = raw.assign(
        occurrence=raw.groupby(["source_sheet"] + columns, dropna=False, sort=False).cumcount()
    )
    keys = columns + ["occurrence"]
    first = numbered.loc[numbered.source_sheet.eq("Year 2009-2010"), keys]
    second = numbered.loc[numbered.source_sheet.eq("Year 2010-2011")]
    matches = second.merge(first, on=keys, how="left", indicator=True, validate="one_to_one")
    overlap = pd.Series(False, index=raw.index)
    overlap.loc[second.index] = matches["_merge"].eq("both").to_numpy()
    return overlap


def clean_data(raw, overlap=None):
    """Count rules on raw data, then remove rows in order; retain repeated lines."""
    # 'First' always means the first physical row in its source sheet.
    raw = raw.sort_values(["source_sheet", "source_row"])
    columns = list(COLUMNS.values())
    if overlap is None:
        overlap = overlap_mask(raw)
    repeated = raw.duplicated(["source_sheet"] + columns, keep="first")
    missing_customer = raw.customer_id.isna()
    cancellation = raw.invoice.str.upper().str.startswith("C", na=False)
    nonpositive = raw.quantity.le(0) | raw.price.le(0)
    nonproduct = ~raw.stockcode.str.fullmatch(r"[0-9]{5}[A-Za-z]*", na=False)
    rules = [
        ("1_overlap_duplicates", overlap, True),
        ("2_repeated_lines_within_sheet", repeated, False),
        ("3_missing_customer_id", missing_customer, True),
        ("4_cancellations", cancellation, True),
        ("5_nonpositive_quantity_or_price", nonpositive, True),
        ("6_nonproduct_stockcode", nonproduct, True),
    ]
    remaining = pd.Series(True, index=raw.index)
    report = []
    for name, mask, drop in rules:
        removed = remaining & mask if drop else pd.Series(False, index=raw.index)
        report.append((name, "rows", int(mask.sum()), int(removed.sum())))
        if name == "6_nonproduct_stockcode":
            excluded = raw.loc[removed].groupby("stockcode", sort=True).agg(
                row_count=("stockcode", "size"), sample_description=("description", "first"),
            ).reset_index()
        remaining &= ~removed

    clean = raw.loc[remaining].copy()
    clean["is_repeated_line"] = repeated.loc[remaining]
    clean["line_value"] = clean.quantity * clean.price
    repeated_groups = raw.loc[repeated, ["source_sheet"] + columns].drop_duplicates()
    customers_passing_345 = raw.loc[
        ~missing_customer & ~cancellation & ~nonpositive, "customer_id"
    ].drop_duplicates()
    # Count customers, not excluded lines: a retained product line prevents exclusion.
    lost_at_rule6 = int((~customers_passing_345.isin(clean.customer_id)).sum())
    report.extend([
        ("2_repeated_line_groups", "groups", len(repeated_groups), 0),
        ("rows_remaining_rules_3_4_5_only", "rows",
         int((~missing_customer & ~cancellation & ~nonpositive).sum()), 0),
        ("6_nonproduct_distinct_stockcodes", "stockcodes",
         raw.loc[nonproduct, "stockcode"].nunique(), len(excluded)),
        ("customers_lost_at_rule6", "customers", lost_at_rule6, 0),
    ])
    report = pd.DataFrame(report, columns=["rule", "unit", "standalone_rows", "removed_rows"])
    return clean, report, excluded


def resolve_cutoff(raw, value):
    """An inclusive calendar date, defaulting to the last raw InvoiceDate's date."""
    if not value:
        return raw.invoice_date.max().normalize()
    try:
        return pd.Timestamp(date.fromisoformat(value))
    except ValueError:
        raise ETLError("CUTOFF_DATE must be an ISO calendar date, for example 2011-06-30.") from None


def resolve_reversal_window(value):
    """Accept a finite, nonnegative number of hours; zero disables removal."""
    try:
        hours = float(value)
    except ValueError:
        raise ETLError("REVERSAL_WINDOW_HOURS must be a finite nonnegative number.") from None
    if not math.isfinite(hours) or hours < 0:
        raise ETLError("REVERSAL_WINDOW_HOURS must be a finite nonnegative number.")
    return hours


def match_reversals(purchases, cancellations, window_hours):
    """Chronological cancellations consume the closest available earlier purchase.

    Each key has a time-ordered stack. Binary search skips equal/later timestamps;
    popping the chosen purchase makes reuse impossible. No price comparison is made.
    Equal-time purchase ties choose the largest (source_sheet, source_row); equal-time
    cancellations are processed in ascending source order for deterministic results.
    """
    available = {}
    order = ["invoice_date", "source_sheet", "source_row"]
    for row in purchases.sort_values(order).itertuples():
        key = (row.customer_id, row.stockcode, row.quantity)
        available.setdefault(key, []).append(
            (row.invoice_date, row.source_sheet, row.source_row, row.Index)
        )
    window = None if window_hours is None else pd.Timedelta(hours=window_hours)
    matches = []
    for row in cancellations.sort_values(order).itertuples():
        key = (row.customer_id, row.stockcode, -row.quantity)
        candidates = available.get(key, [])
        position = bisect_left(candidates, (row.invoice_date,)) - 1
        if position < 0:
            continue
        purchase_time, _, _, purchase_index = candidates[position]
        gap = row.invoice_date - purchase_time
        if window is None or gap <= window:
            candidates.pop(position)
            matches.append((purchase_index, row.Index, gap.total_seconds() / 60))
    return pd.DataFrame(matches, columns=["purchase_index", "cancellation_index", "gap_minutes"])


def reversal_inputs(raw, overlap):
    """Cancellation candidates and positive purchases from raw data after rule 1."""
    source = raw.loc[~overlap & raw.customer_id.notna()]
    is_cancellation = source.invoice.str.upper().str.startswith("C", na=False)
    cancellations = source.loc[is_cancellation]
    purchases = source.loc[~is_cancellation & source.quantity.gt(0) & source.price.gt(0)]
    return purchases, cancellations


def reversed_lines(clean, cancellations, matches):
    """Keep only matched purchase lines surviving rules 1–6, with cancellation provenance."""
    matches = matches.loc[matches.purchase_index.isin(clean.index)]
    removed = clean.loc[matches.purchase_index].copy()
    for column in ("invoice", "invoice_date", "source_sheet", "source_row"):
        removed["cancellation_" + column] = cancellations.loc[
            matches.cancellation_index, column
        ].to_numpy()
    removed["gap_minutes"] = matches.gap_minutes.to_numpy()
    return removed


def build_rfm(clean, cutoff):
    """Aggregate eligible lines into invoices, then customer calendar-day purchases."""
    # Filter first: no line from a later day can contribute to an eligible invoice.
    eligible = clean.loc[clean.invoice_date.lt(cutoff + pd.Timedelta(days=1))]
    invoices = eligible.groupby(["customer_id", "invoice"], sort=False).agg(
        purchase_date=("invoice_date", "min"),
        purchase_value=("line_value", "sum"),
    ).reset_index()
    # An invoice is dated by its earliest eligible line, even if minutes differ.
    invoices["purchase_date"] = invoices.purchase_date.dt.normalize()
    purchases = invoices.groupby(["customer_id", "purchase_date"], sort=True).agg(
        purchase_value=("purchase_value", "sum"),
        invoice_count=("invoice", "size"),
    ).reset_index()
    # All invoices on the same calendar date are one BG/NBD purchase occasion.
    purchases["purchase_number"] = purchases.groupby("customer_id").cumcount()
    summary = purchases.groupby("customer_id", sort=True).agg(
        purchase_dates=("purchase_date", "size"),
        first_purchase=("purchase_date", "min"),
        last_purchase=("purchase_date", "max"),
    )
    # Frequency counts repeat purchase dates, excluding the customer's first date.
    summary["frequency"] = summary.purchase_dates - 1
    # Recency is the first-to-last purchase gap, measured in whole calendar days.
    summary["recency"] = (summary.last_purchase - summary.first_purchase).dt.days
    # T uses the same calendar-date convention: first purchase to inclusive cutoff.
    summary["T"] = (cutoff - summary.first_purchase).dt.days
    # Monetary value averages repeat-day totals only. A one-time buyer gets zero.
    repeats = purchases.loc[purchases.purchase_number.gt(0)]
    summary["monetary_value"] = repeats.groupby("customer_id").purchase_value.mean()
    summary["monetary_value"] = summary.monetary_value.fillna(0.0)
    summary["cutoff_date"] = cutoff.date()
    rfm = summary.reset_index()[
        ["customer_id", "frequency", "recency", "T", "monetary_value", "cutoff_date"]
    ]
    if rfm.isna().any().any() or rfm.customer_id.duplicated().any():
        raise ETLError("customer_rfm contains nulls or duplicate customer IDs.")
    return rfm, int(purchases.invoice_count.gt(1).sum())


def prepare_tables(raw, cutoff, reversal_window_hours=24):
    """Build all derived tables, including full-history and cutoff-specific counts."""
    overlap = overlap_mask(raw)
    before, report, excluded = clean_data(raw, overlap)
    purchases, cancellations = reversal_inputs(raw, overlap)
    windows = {"1_hour": 1, "24_hours": 24, "7_days": 168, "30_days": 720, "unlimited": None}
    matches = {
        hours: match_reversals(purchases, cancellations, hours)
        for hours in dict.fromkeys([*windows.values(), reversal_window_hours])
    }
    selected = matches[reversal_window_hours]
    removed = reversed_lines(before, cancellations, selected)
    clean = before.drop(index=removed.index)

    # Full-history cleaning is retrospective. Historical RFM may only use reversals
    # observed through its cutoff, so a later cancellation cannot leak backwards.
    rfm_lines = clean
    cutoff_end = cutoff + pd.Timedelta(days=1)
    if cancellations.invoice_date.ge(cutoff_end).any():
        observed = cancellations.loc[cancellations.invoice_date.lt(cutoff_end)]
        observed_matches = match_reversals(purchases, observed, reversal_window_hours)
        observed_removed = reversed_lines(before, observed, observed_matches)
        rfm_lines = before.drop(index=observed_removed.index)
    baseline_rfm, _ = build_rfm(before, cutoff)
    rfm, multiple_invoices = build_rfm(rfm_lines, cutoff)
    comparison = baseline_rfm.merge(rfm, on="customer_id", how="outer", suffixes=("_before", "_after"))
    changed = (
        comparison.frequency_before.ne(comparison.frequency_after)
        | comparison.monetary_value_before.ne(comparison.monetary_value_after)
    )
    first_purchase = clean.groupby("customer_id").invoice_date.min().dt.normalize()
    metrics = [
        ("7_quick_reversals", "rows", len(selected), len(removed)),
        *[("7_matches_" + name, "pairs", len(matches[hours]), 0) for name, hours in windows.items()],
        ("customers_rfm_changed_by_rule7", "customers", int(changed.sum()), 0),
        ("customers_with_id_in_raw", "customers", raw.customer_id.nunique(), 0),
        ("customers_in_rfm", "customers", len(rfm), 0),
        ("customers_without_valid_purchase", "customers",
         raw.customer_id.nunique() - clean.customer_id.nunique(), 0),
        ("customers_first_purchase_after_cutoff", "customers", int(first_purchase.gt(cutoff).sum()), 0),
        ("customer_days_with_multiple_invoices", "customer_days", multiple_invoices, 0),
    ]
    report = pd.concat([report, pd.DataFrame(metrics, columns=report.columns)], ignore_index=True)
    report["removed_line_value"] = 0.0
    report.loc[report.rule.eq("7_quick_reversals"), "removed_line_value"] = removed.line_value.sum()
    return {
        "raw_transactions": raw, "clean_transactions": clean,
        "data_quality_report": report, "excluded_stockcodes": excluded,
        "customer_rfm": rfm, "reversed_purchases": removed,
    }


def copy_rows(table, connection, keys, rows):
    """pandas to_sql adapter: stream rows with COPY on the existing transaction."""
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table.name), sql.SQL(", ").join(map(sql.Identifier, keys)),
    )
    count = 0
    with connection.connection.driver_connection.cursor() as cursor:
        with cursor.copy(statement) as copy:
            for row in rows:
                copy.write_row(row)
                count += 1
    return count


def publish_tables(tables):
    """Create explicit schemas and replace all contents in one atomic transaction."""
    url = URL.create(
        "postgresql+psycopg", host=os.environ["POSTGRES_HOST"],
        database=os.environ["POSTGRES_DB"], username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.begin() as connection:
            schema = Path(__file__).with_name("schema.sql").read_text()
            for statement in schema.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            connection.exec_driver_sql(
                "TRUNCATE raw_transactions, clean_transactions, data_quality_report, "
                "excluded_stockcodes, customer_rfm, reversed_purchases"
            )
            for name, frame in tables.items():
                frame.to_sql(
                    name, connection, if_exists="append", index=False,
                    chunksize=10_000, method=copy_rows,
                )
            loaded = connection.exec_driver_sql("SELECT count(*) FROM raw_transactions").scalar_one()
            if loaded != sum(SHEET_ROWS.values()):
                raise ETLError(f"Database raw row count mismatch: got {loaded:,}.")
    finally:
        engine.dispose()


def main():
    raw = load_workbook(Path("data/raw/online_retail_II.xlsx"))
    cutoff = resolve_cutoff(raw, os.environ.get("CUTOFF_DATE", ""))
    hours = resolve_reversal_window(os.environ.get("REVERSAL_WINDOW_HOURS", "24"))
    tables = prepare_tables(raw, cutoff, hours)
    print(f"Publishing tables; inclusive cutoff: {cutoff.date()}; reversal window: {hours:g} hours", flush=True)
    publish_tables(tables)
    print(f"Committed {len(raw):,} raw rows, {len(tables['clean_transactions']):,} clean rows, "
          f"{len(tables['customer_rfm']):,} customer RFM rows.", flush=True)
    print("Data quality report:", flush=True)
    print(tables["data_quality_report"].to_string(index=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except ETLError as error:
        print(f"ETL failed: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Database exceptions may embed connection details or source rows.
        # Print the error type only; never log a connection URL or credentials.
        print(f"ETL failed ({type(error).__name__}). Check workbook types, database "
              "availability, and POSTGRES_* settings.", file=sys.stderr)
        sys.exit(1)
