from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from services.etl import main as etl


def make_raw(records):
    """Small typed source rows; each dictionary overrides the default line."""
    default = {
        "invoice": "489434", "stockcode": "85048", "description": "Gift",
        "quantity": 1, "invoice_date": "2010-12-01 10:00", "price": 10.0,
        "customer_id": "12345", "country": "United Kingdom",
        "source_sheet": "Year 2009-2010",
    }
    frame = pd.DataFrame([default | record for record in records])
    for column in ("invoice", "stockcode"):
        frame[column] = frame[column].astype("string")
    frame["customer_id"] = frame["customer_id"].astype("Int64").astype("string")
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], format="mixed")
    frame["source_row"] = frame.groupby("source_sheet").cumcount() + 2
    return frame


def write_workbook(path, records):
    """Exercise the actual Excel reader with numeric and text identifier cells."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet in etl.SHEET_ROWS:
        worksheet = workbook.create_sheet(sheet)
        worksheet.append(list(etl.COLUMNS))
        for row in records:
            worksheet.append(row)
    workbook.save(path)


def test_excel_identifier_types_and_guest_ids(tmp_path, monkeypatch):
    records = [
        [489434, 85048, "Gift", 1, "2010-12-01 10:00", 10, 12345, "UK"],
        ["A123", "85048", "Gift", 1, "2010-12-01 10:00", 10, 12345, "UK"],
        ["C489434", "79323P", "Gift", -1, "2010-12-01 10:00", 10, None, "UK"],
    ]
    path = tmp_path / "sample.xlsx"
    write_workbook(path, records)
    monkeypatch.setattr(etl, "SHEET_ROWS", {sheet: 3 for sheet in etl.SHEET_ROWS})
    raw = etl.load_workbook(path)
    assert raw.invoice.tolist()[:3] == ["489434", "A123", "C489434"]
    assert raw.stockcode.tolist()[:3] == ["85048", "85048", "79323P"]
    assert raw.customer_id.iloc[0] == "12345"
    assert pd.isna(raw.customer_id.iloc[2])
    assert raw.source_row.tolist() == [2, 3, 4, 2, 3, 4]


def test_wrong_workbook_row_count_fails(tmp_path):
    path = tmp_path / "short.xlsx"
    write_workbook(path, [[489434, 85048, "Gift", 1, "2010-12-01", 10, 12345, "UK"]])
    with pytest.raises(etl.ETLError, match="1,067,371"):
        etl.load_workbook(path)


def test_missing_workbook_fails():
    with pytest.raises(etl.ETLError, match="Missing data/raw"):
        etl.load_workbook(Path("/missing/online_retail_II.xlsx"))


def test_overlap_is_one_to_one_and_within_sheet_repeats_survive():
    raw = make_raw([{}, {}, {"source_sheet": "Year 2010-2011"}])
    # Reverse input order: preference must depend on sheet, not input position.
    clean, report, _ = etl.clean_data(raw.iloc[::-1])
    assert len(clean) == 2
    assert set(clean.source_sheet) == {"Year 2009-2010"}
    assert clean.is_repeated_line.sum() == 1
    assert not clean.loc[clean.source_row.eq(2), "is_repeated_line"].item()
    assert clean.loc[clean.source_row.eq(3), "is_repeated_line"].item()
    counts = report.set_index("rule")
    assert counts.loc["1_overlap_duplicates", "removed_rows"] == 1
    assert counts.loc["2_repeated_lines_within_sheet", "removed_rows"] == 0


def test_extra_occurrence_in_second_sheet_is_kept():
    raw = make_raw([{}, {"source_sheet": "Year 2010-2011"}, {"source_sheet": "Year 2010-2011"}])
    clean, _, _ = etl.clean_data(raw)
    assert len(clean) == 2
    assert set(clean.source_sheet) == set(etl.SHEET_ROWS)


def test_null_descriptions_still_match_across_sheets():
    raw = make_raw([{"description": None}, {"description": None, "source_sheet": "Year 2010-2011"}])
    clean, report, _ = etl.clean_data(raw)
    assert len(clean) == 1
    assert report.set_index("rule").loc["1_overlap_duplicates", "standalone_rows"] == 1


def test_repeated_extra_rows_and_groups():
    clean, report, _ = etl.clean_data(make_raw([{}, {}, {}]))
    assert len(clean) == 3
    assert clean.is_repeated_line.tolist() == [False, True, True]
    counts = report.set_index("rule")
    assert counts.loc["2_repeated_lines_within_sheet", "standalone_rows"] == 2
    assert counts.loc["2_repeated_line_groups", "standalone_rows"] == 1


def test_cancellations_and_product_pattern():
    raw = make_raw([
        {"invoice": 489434, "stockcode": 85048},
        {"invoice": "A123", "stockcode": "85048"},
        {"invoice": "C489434"}, {"invoice": "c489435"},
        {"stockcode": "POST"}, {"stockcode": "DOT"}, {"stockcode": "M"},
        {"stockcode": "79323P"},
    ])
    clean, report, excluded = etl.clean_data(raw)
    assert clean.invoice.tolist() == ["489434", "A123", "489434"]
    assert clean.stockcode.tolist() == ["85048", "85048", "79323P"]
    assert set(excluded.stockcode) == {"POST", "DOT", "M"}
    assert excluded.row_count.sum() == 3
    assert report.set_index("rule").loc["4_cancellations", "removed_rows"] == 2


def test_standalone_counts_differ_from_sequential_removals():
    raw = make_raw([
        {"customer_id": None, "invoice": "C1", "quantity": -1, "stockcode": "POST"},
        {"invoice": "C2", "quantity": -1, "stockcode": "POST"},
        {"quantity": 0, "stockcode": "POST"},
        {"price": 0}, {"stockcode": "POST"}, {},
    ])
    clean, report, excluded = etl.clean_data(raw)
    counts = report.set_index("rule")
    assert len(clean) == 1
    assert counts.loc["4_cancellations", ["standalone_rows", "removed_rows"]].tolist() == [2, 1]
    assert counts.loc["5_nonpositive_quantity_or_price", ["standalone_rows", "removed_rows"]].tolist() == [4, 2]
    assert counts.loc["6_nonproduct_stockcode", ["standalone_rows", "removed_rows"]].tolist() == [4, 1]
    assert excluded.row_count.tolist() == [1]
    assert counts.loc[counts.unit.eq("rows"), "removed_rows"].sum() + len(clean) == len(raw)
    assert counts.loc["rows_remaining_rules_3_4_5_only", "standalone_rows"] == 2


def test_rule6_standalone_and_sequential_distinct_codes():
    raw = make_raw([
        {"stockcode": "POST", "customer_id": None},
        {"stockcode": "DOT", "invoice": "C1"},
        {"stockcode": "M"}, {"stockcode": "M", "invoice": "A2"}, {},
    ])
    _, report, excluded = etl.clean_data(raw)
    counts = report.set_index("rule")
    assert counts.loc["6_nonproduct_stockcode", ["standalone_rows", "removed_rows"]].tolist() == [4, 2]
    assert counts.loc["6_nonproduct_distinct_stockcodes", ["standalone_rows", "removed_rows"]].tolist() == [3, 1]
    assert excluded.stockcode.tolist() == ["M"]
    assert excluded.row_count.tolist() == [2]
    assert excluded.sample_description.tolist() == ["Gift"]


def test_rules_345_only_survivors_include_overlap_repeats_and_nonproducts():
    raw = make_raw([{}, {}, {"source_sheet": "Year 2010-2011"}, {"stockcode": "POST"}])
    clean, report, _ = etl.clean_data(raw)
    assert len(clean) == 2
    assert report.set_index("rule").loc["rows_remaining_rules_3_4_5_only", "standalone_rows"] == 4


def test_customer_days_and_repeat_purchase_value():
    raw = make_raw([
        {"invoice": "A", "invoice_date": "2011-01-01 10:00", "price": 10},
        {"invoice": "A", "invoice_date": "2011-01-01 10:03", "price": 20},
        {"invoice": "B", "invoice_date": "2011-01-02 09:00", "price": 20},
        {"invoice": "D", "invoice_date": "2011-01-02 17:00", "price": 30},
        {"invoice": "E", "invoice_date": "2011-01-04 10:00", "price": 70},
        {"invoice": "F", "invoice_date": "2011-01-05 23:59:59.999999", "customer_id": "22222"},
    ])
    clean, _, _ = etl.clean_data(raw)
    rfm, multiple = etl.build_rfm(clean, pd.Timestamp("2011-01-05"))
    buyer = rfm.set_index("customer_id").loc["12345"]
    assert buyer.frequency == 2
    assert buyer.recency == 3
    assert buyer["T"] == 4
    assert buyer.monetary_value == pytest.approx(60)  # Mean of repeat-day totals 50 and 70.
    assert multiple == 1
    one_time = rfm.set_index("customer_id").loc["22222"]
    assert one_time[["frequency", "recency", "T", "monetary_value"]].tolist() == [0, 0, 0, 0]
    assert not rfm.isna().any().any()


def test_lines_after_cutoff_are_filtered_before_invoice_aggregation():
    raw = make_raw([
        {"invoice": "A", "invoice_date": "2011-01-01 10:00"},
        {"invoice": "B", "invoice_date": "2011-01-05 23:59", "price": 20},
        {"invoice": "B", "invoice_date": "2011-01-06 00:01", "price": 1000},
    ])
    tables = etl.prepare_tables(raw, pd.Timestamp("2011-01-05"))
    rfm = tables["customer_rfm"]
    assert rfm.frequency.item() == 1
    assert rfm.recency.item() == 4
    assert rfm["T"].item() == 4
    assert rfm.monetary_value.item() == 20
    assert len(tables["clean_transactions"]) == 3  # Full-history cleaning is cutoff-independent.


def test_customer_exclusions_are_separate_from_future_customers():
    raw = make_raw([
        {"invoice_date": "2011-01-01"},
        {"invoice_date": "2011-01-06", "customer_id": "22222"},
        {"invoice": "C1", "customer_id": "33333"},
        {"customer_id": None},
    ])
    tables = etl.prepare_tables(raw, pd.Timestamp("2011-01-05"))
    report = tables["data_quality_report"].set_index("rule")
    assert report.loc["customers_with_id_in_raw", "standalone_rows"] == 3
    assert report.loc["customers_in_rfm", "standalone_rows"] == 1
    assert report.loc["customers_without_valid_purchase", "standalone_rows"] == 1
    assert report.loc["customers_first_purchase_after_cutoff", "standalone_rows"] == 1


@pytest.mark.parametrize("cutoff", ["2009-01-01", "2011-12-09"])
def test_customers_lost_at_rule6_counts_customers_over_full_history(cutoff):
    raw = make_raw([
        {},
        {"stockcode": "POST", "customer_id": "22222"},
        {"stockcode": "DOT", "customer_id": "22222"},
        {"invoice": "C1", "customer_id": "33333"},
        {"stockcode": "POST"},  # This customer's retained product line prevents exclusion.
        {"customer_id": "44444", "invoice_date": "2011-01-01"},
    ])
    tables = etl.prepare_tables(raw, pd.Timestamp(cutoff))
    report = tables["data_quality_report"].set_index("rule")
    assert report.loc["customers_lost_at_rule6", "standalone_rows"] == 1
    assert report.loc["customers_lost_at_rule6", "removed_rows"] == 0
    assert report.loc["customers_without_valid_purchase", "standalone_rows"] == 2


def test_cutoff_before_all_purchases_returns_empty_rfm():
    clean, _, _ = etl.clean_data(make_raw([{}]))
    rfm, multiple = etl.build_rfm(clean, pd.Timestamp("2009-01-01"))
    assert rfm.empty
    assert not rfm.isna().any().any()
    assert multiple == 0


def test_default_cutoff_uses_last_raw_date_even_if_line_is_not_clean():
    raw = make_raw([{}, {"invoice": "C1", "invoice_date": "2011-12-09 12:50"}])
    assert etl.resolve_cutoff(raw, "") == pd.Timestamp("2011-12-09")
    assert etl.resolve_cutoff(raw, "2011-06-30") == pd.Timestamp("2011-06-30")
    with pytest.raises(etl.ETLError, match="CUTOFF_DATE"):
        etl.resolve_cutoff(raw, "2011-06-30T12:00:00")


def reversal_result(records, hours=24):
    raw = make_raw(records)
    overlap = etl.overlap_mask(raw)
    clean, _, _ = etl.clean_data(raw, overlap)
    purchases, cancellations = etl.reversal_inputs(raw, overlap)
    matches = etl.match_reversals(purchases, cancellations, hours)
    removed = etl.reversed_lines(clean, cancellations, matches)
    return clean.drop(index=removed.index), removed


@pytest.mark.parametrize("gap,removed", [(12, 1), (1440, 1), (1441, 0), (0, 0), (-12, 0)])
def test_reversal_window_is_strictly_later_and_inclusive_at_upper_bound(gap, removed):
    purchase_date = pd.Timestamp("2010-12-01 10:00")
    clean, reversed_purchases = reversal_result([
        {}, {"invoice": "c123", "quantity": -1, "price": 999,
             "invoice_date": purchase_date + pd.Timedelta(minutes=gap)},
    ])
    assert len(reversed_purchases) == removed
    assert len(clean) == 1 - removed
    if removed:
        assert reversed_purchases.gap_minutes.item() == gap
        assert reversed_purchases.cancellation_invoice.item() == "c123"
        assert reversed_purchases.line_value.item() == 10  # Prices need not match.


def test_one_cancellation_removes_only_one_identical_purchase():
    clean, removed = reversal_result([
        {}, {}, {"invoice": "C1", "quantity": -1, "invoice_date": "2010-12-01 10:12"},
    ])
    assert len(clean) == len(removed) == 1
    assert removed.source_row.item() == 3  # Stable tie: the later source row is chosen.


def test_closest_purchase_and_chronological_cancellations_are_one_to_one():
    clean, removed = reversal_result([
        {"invoice": "A", "invoice_date": "2010-12-01 09:00"},
        {"invoice": "B", "invoice_date": "2010-12-01 10:00"},
        {"invoice": "C1", "quantity": -1, "invoice_date": "2010-12-01 10:12"},
        {"invoice": "C2", "quantity": -1, "invoice_date": "2010-12-01 10:13"},
        {"invoice": "C3", "quantity": -1, "invoice_date": "2010-12-01 10:14"},
    ])
    assert clean.empty
    assert removed.invoice.tolist() == ["B", "A"]
    assert removed.cancellation_invoice.tolist() == ["C1", "C2"]
    assert not removed.index.duplicated().any()
    assert not removed.cancellation_source_row.duplicated().any()


@pytest.mark.parametrize("change", [
    {"customer_id": "22222"}, {"stockcode": "85049"},
    {"quantity": -2}, {"customer_id": None},
])
def test_reversal_requires_exact_customer_stockcode_and_opposite_quantity(change):
    clean, removed = reversal_result([
        {}, {"invoice": "C1", "quantity": -1, "invoice_date": "2010-12-01 10:12"} | change,
    ])
    assert len(clean) == 1
    assert removed.empty


def test_overlap_cancellation_copy_cannot_reverse_a_second_purchase():
    clean, removed = reversal_result([
        {}, {},
        {"invoice": "C1", "quantity": -1, "invoice_date": "2010-12-01 10:12"},
        {"invoice": "C1", "quantity": -1, "invoice_date": "2010-12-01 10:12",
         "source_sheet": "Year 2010-2011"},
    ])
    assert len(clean) == len(removed) == 1


def test_cancellation_before_repurchase_does_not_reverse_the_repurchase():
    clean, removed = reversal_result([
        {"invoice": "540815", "invoice_date": "2011-01-11 12:55", "quantity": 3114},
        {"invoice": "C550456", "invoice_date": "2011-04-18 13:08", "quantity": -3114},
        {"invoice": "550461", "invoice_date": "2011-04-18 13:20", "quantity": 3114},
    ])
    assert len(clean) == 2  # January is outside 24 hours; April is after the cancellation.
    assert removed.empty


@pytest.mark.parametrize("value", ["bad", "nan", "inf", "-1"])
def test_reversal_window_rejects_invalid_values(value):
    with pytest.raises(etl.ETLError, match="REVERSAL_WINDOW_HOURS"):
        etl.resolve_reversal_window(value)


def test_rule7_reports_value_without_changing_rules_1_to_6():
    raw = make_raw([
        {}, {"invoice": "P2", "stockcode": "POST"},
        {"invoice": "C1", "quantity": -1, "invoice_date": "2010-12-01 10:12"},
        {"invoice": "C2", "stockcode": "POST", "quantity": -1, "invoice_date": "2010-12-01 10:13"},
    ])
    _, baseline_report, _ = etl.clean_data(raw)
    tables = etl.prepare_tables(raw, pd.Timestamp("2010-12-01"))
    report = tables["data_quality_report"]
    pd.testing.assert_frame_equal(report.iloc[:6][baseline_report.columns], baseline_report.iloc[:6])
    counts = report.set_index("rule")
    assert counts.loc["7_quick_reversals", ["standalone_rows", "removed_rows"]].tolist() == [2, 1]
    assert counts.loc["7_quick_reversals", "removed_line_value"] == 10
    assert counts.loc["7_matches_1_hour", "standalone_rows"] == 2
    assert counts.loc["customers_rfm_changed_by_rule7", "standalone_rows"] == 1
    assert len(tables["reversed_purchases"]) == 1
    assert tables["clean_transactions"].empty


def test_historical_rfm_ignores_later_cancellations():
    raw = make_raw([
        {"invoice": "A", "invoice_date": "2011-01-01 10:00"},
        {"invoice": "B", "invoice_date": "2011-01-02 23:59"},
        {"invoice": "C1", "quantity": -1, "invoice_date": "2011-01-03 00:01"},
    ])
    historical = etl.prepare_tables(raw, pd.Timestamp("2011-01-02"))
    assert historical["customer_rfm"].frequency.item() == 1
    assert historical["customer_rfm"].monetary_value.item() == 10
    assert len(historical["clean_transactions"]) == 1  # Full-history cleaning is retrospective.
    assert historical["data_quality_report"].set_index("rule").loc[
        "customers_rfm_changed_by_rule7", "standalone_rows"
    ] == 0
    final = etl.prepare_tables(raw, pd.Timestamp("2011-01-03"))
    assert final["customer_rfm"].frequency.item() == 0
    assert final["customer_rfm"].monetary_value.item() == 0


def test_partial_invoice_reversal_changes_money_without_removing_purchase_day():
    raw = make_raw([
        {"invoice": "A", "invoice_date": "2011-01-01 10:00"},
        {"invoice": "B", "invoice_date": "2011-01-02 10:00"},
        {"invoice": "B", "invoice_date": "2011-01-02 10:01", "stockcode": "85049", "price": 5},
        {"invoice": "C1", "quantity": -1, "invoice_date": "2011-01-02 10:12"},
    ])
    tables = etl.prepare_tables(raw, pd.Timestamp("2011-01-02"))
    assert tables["customer_rfm"].frequency.item() == 1
    assert tables["customer_rfm"].monetary_value.item() == 5
    assert tables["data_quality_report"].set_index("rule").loc[
        "customers_rfm_changed_by_rule7", "standalone_rows"
    ] == 1


def test_zero_window_disables_removal_but_keeps_window_diagnostics():
    raw = make_raw([{}, {"invoice": "C1", "quantity": -1, "invoice_date": "2010-12-01 10:12"}])
    tables = etl.prepare_tables(raw, pd.Timestamp("2010-12-01"), reversal_window_hours=0)
    assert len(tables["clean_transactions"]) == 1
    assert tables["reversed_purchases"].empty
    assert tables["data_quality_report"].set_index("rule").loc["7_matches_24_hours", "standalone_rows"] == 1
