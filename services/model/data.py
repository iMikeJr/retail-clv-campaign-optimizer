"""Point-in-time customer-day purchases and reproducible features; no stored features."""

import numpy as np
import pandas as pd


FEATURES = [
    "frequency", "recency", "T", "days_since_last", "monetary_value",
    "mean_gap_days", "std_gap_days", "n_purchases_last_90d",
    "n_purchases_last_180d", "total_spend", "last_purchase_value",
    "n_distinct_products", "is_uk",
]


class ModelError(Exception):
    """Safe-to-print validation failure, never containing database credentials."""


def lines_as_of(clean, reversed_purchases, cutoff):
    """Undo retrospective reversals when the cancellation is not yet observed."""
    end = pd.Timestamp(cutoff).normalize() + pd.Timedelta(days=1)
    observed = clean.loc[clean.invoice_date.lt(end)]
    restore = reversed_purchases.loc[
        reversed_purchases.invoice_date.lt(end)
        & reversed_purchases.cancellation_invoice_date.ge(end), clean.columns
    ]
    return pd.concat([observed, restore], ignore_index=True).sort_values(
        ["invoice_date", "source_sheet", "source_row"]
    )


def daily_purchases(lines):
    """Follow ETL: eligible lines -> invoice (earliest timestamp) -> customer-day."""
    invoices = lines.groupby(["customer_id", "invoice"], sort=False).agg(
        purchase_date=("invoice_date", "min"), purchase_value=("line_value", "sum")
    ).reset_index()
    invoices["purchase_date"] = invoices.purchase_date.dt.normalize()
    daily = invoices.groupby(["customer_id", "purchase_date"], sort=True).agg(
        purchase_value=("purchase_value", "sum")
    ).reset_index()
    daily["purchase_number"] = daily.groupby("customer_id").cumcount()
    return daily


def build_features(clean, reversed_purchases, cutoff, cap=None):
    cutoff = pd.Timestamp(cutoff).normalize()
    lines = lines_as_of(clean, reversed_purchases, cutoff)
    purchases = daily_purchases(lines)
    if purchases.empty:
        raise ModelError("No eligible purchases at feature cutoff.")
    if cap is not None:
        purchases["purchase_value"] = purchases.purchase_value.clip(upper=cap)
    groups = purchases.groupby("customer_id", sort=True)
    features = groups.agg(
        frequency=("purchase_date", "size"), first=("purchase_date", "min"),
        last=("purchase_date", "max"), total_spend=("purchase_value", "sum"),
        last_purchase_value=("purchase_value", "last"),
    )
    features["frequency"] -= 1
    features["recency"] = (features["last"] - features["first"]).dt.days
    features["T"] = (cutoff - features["first"]).dt.days
    features["days_since_last"] = features["T"] - features.recency
    repeats = purchases.loc[purchases.purchase_number.gt(0)]
    features["monetary_value"] = repeats.groupby("customer_id").purchase_value.mean()
    features["mean_gap_days"] = features.recency / features.frequency.replace(0, np.nan)
    purchases["gap"] = groups.purchase_date.diff().dt.days
    features["std_gap_days"] = purchases.groupby("customer_id").gap.std(ddof=0)
    for days in (90, 180):
        recent = purchases.loc[purchases.purchase_date.gt(cutoff - pd.Timedelta(days=days))]
        features[f"n_purchases_last_{days}d"] = recent.groupby("customer_id").size()
    features["n_distinct_products"] = lines.groupby("customer_id").stockcode.nunique()
    # tail preserves a missing latest country; groupby.last would skip it.
    country = lines.groupby("customer_id").tail(1).set_index("customer_id").country
    features["is_uk"] = country.eq("United Kingdom").fillna(False).astype(int)
    features = features[FEATURES].fillna(0)
    if not np.isfinite(features.to_numpy()).all():
        raise ModelError("Non-finite point-in-time features.")
    return features


def purchase_cap(clean, reversed_purchases, cutoff):
    purchases = daily_purchases(lines_as_of(clean, reversed_purchases, cutoff))
    return float(purchases.purchase_value.quantile(0.99))


def build_labels(clean, reversed_purchases, customers, cutoff, window_days):
    cutoff = pd.Timestamp(cutoff).normalize()
    end = cutoff + pd.Timedelta(days=window_days)
    purchases = daily_purchases(lines_as_of(clean, reversed_purchases, end))
    future = purchases.loc[purchases.purchase_date.gt(cutoff)]
    labels = future.groupby("customer_id").agg(
        actual_purchases=("purchase_value", "size"), actual_spend=("purchase_value", "sum")
    ).reindex(customers, fill_value=0)
    labels["actual_purchased"] = labels.actual_purchases.gt(0).astype(int)
    return labels


def reconcile_rfm(clean, reversed_purchases, rfm):
    if rfm.empty or rfm.cutoff_date.nunique() != 1:
        raise ModelError("customer_rfm must contain exactly one cutoff and nonempty rows.")
    cutoff = pd.Timestamp(rfm.cutoff_date.iloc[0])
    actual = build_features(clean, reversed_purchases, cutoff)
    expected = rfm.set_index("customer_id").sort_index()
    if not actual.index.equals(expected.index):
        raise ModelError("ETL reconciliation: customer membership mismatch.")
    differences = {}
    for column in ("frequency", "recency", "T", "monetary_value"):
        left, right = actual[column].to_numpy(), expected[column].to_numpy()
        differences[column] = float(np.max(np.abs(left - right)))
        matches = np.isclose(left, right, rtol=1e-10, atol=1e-8) if column == "monetary_value" else left == right
        if not matches.all():
            raise ModelError(f"ETL reconciliation: {column} mismatches={int((~matches).sum())}, "
                             f"max_difference={differences[column]}.")
    return {"cutoff": str(cutoff.date()), "customers": len(actual), "max_differences": differences}
