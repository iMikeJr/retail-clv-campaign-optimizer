import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from data import (ModelError, build_features, build_labels, purchase_cap, reconcile_rfm)
from probabilistic import Fit, fit_bgnbd, fit_gamma_gamma, predict_bgnbd, predict_order_value
from test_recovery import simulate_bgnbd


def make_lines(records):
    rows = []
    for number, row in enumerate(records):
        rows.append({"customer_id": "1", "invoice": f"I{number}", "stockcode": "10000",
                     "invoice_date": "2020-01-01", "line_value": 10., "country": "United Kingdom",
                     "source_sheet": "test", "source_row": number + 2, **row})
    frame = pd.DataFrame(rows)
    frame["invoice_date"] = pd.to_datetime(frame.invoice_date, format="mixed")
    return frame


def empty_reversals(clean):
    return clean.iloc[:0].assign(cancellation_invoice_date=pd.Series(dtype="datetime64[ns]"))


def test_cutoff_and_label_endpoint_are_inclusive_calendar_days():
    clean = make_lines([{"invoice_date": "2020-01-01"},
                        {"invoice_date": "2020-01-05 23:59", "line_value": 20.},
                        {"invoice_date": "2020-01-10 23:59", "line_value": 30.},
                        {"invoice_date": "2020-01-11", "line_value": 1000.}])
    reverse = empty_reversals(clean)
    features = build_features(clean, reverse, "2020-01-05")
    labels = build_labels(clean, reverse, features.index, "2020-01-05", 5)
    assert features.loc["1", ["frequency", "recency", "T", "monetary_value"]].tolist() == [1, 4, 4, 20]
    assert labels.loc["1", ["actual_purchased", "actual_purchases", "actual_spend"]].tolist() == [1, 1, 30]


def test_daily_aggregation_cap_gaps_and_country():
    clean = make_lines([{"invoice_date": "2020-01-01", "line_value": 30.},
                        {"invoice_date": "2020-01-02", "line_value": 20.},
                        {"invoice_date": "2020-01-02 12:00", "line_value": 30.},
                        {"invoice_date": "2020-01-04", "line_value": 70., "country": None}])
    result = build_features(clean, empty_reversals(clean), "2020-01-05", cap=60).loc["1"]
    assert result.frequency == 2
    assert result.monetary_value == 55
    assert result.total_spend == 140
    assert result.last_purchase_value == 60
    assert result.std_gap_days == 0.5
    assert result.mean_gap_days == 1.5
    assert result.is_uk == 0


def test_future_reversals_are_restored_only_until_observed():
    clean = make_lines([{"invoice_date": "2020-01-01"}])
    reversed_lines = make_lines([{"invoice_date": "2020-01-02 23:59", "invoice": "reversed"}])
    reversed_lines["cancellation_invoice_date"] = pd.to_datetime(["2020-01-03 00:01"])
    assert build_features(clean, reversed_lines, "2020-01-02").loc["1", "frequency"] == 1
    assert build_features(clean, reversed_lines, "2020-01-03").loc["1", "frequency"] == 0


def test_features_cap_and_fits_do_not_see_future_data():
    histories, _ = simulate_bgnbd(n=2000)
    rng = np.random.default_rng(42)
    cutoff = pd.Timestamp("2020-01-01")
    records = []
    for customer, row in histories.iterrows():
        first = cutoff - pd.Timedelta(days=int(row["T"]))
        mean = 6 / rng.gamma(4, 1 / 100)
        days = np.unique(np.rint(np.linspace(0, row.recency, int(row.frequency) + 1)).astype(int))
        for day in days:
            records.append({"customer_id": str(customer), "invoice_date": first + pd.Timedelta(days=int(day)),
                            "line_value": rng.gamma(6, mean / 6)})
    past = make_lines(records)
    future = make_lines([{"invoice_date": "2020-02-01", "line_value": 1e9,
                          "customer_id": "future_customer"}])
    full = pd.concat([past, future], ignore_index=True)
    reverse = empty_reversals(past)
    left = build_features(full, reverse, cutoff)
    right = build_features(past, reverse, cutoff)
    assert_frame_equal(left, right)
    assert purchase_cap(full, reverse, cutoff) == purchase_cap(past, reverse, cutoff)
    assert fit_bgnbd(left).parameters == fit_bgnbd(right).parameters
    assert fit_gamma_gamma(left).parameters == fit_gamma_gamma(right).parameters


def test_reconciliation_checks_membership_and_uncapped_money():
    clean = make_lines([{}, {"invoice_date": "2020-01-02", "line_value": 50.}])
    reverse = empty_reversals(clean)
    features = build_features(clean, reverse, "2020-01-03")
    rfm = features[["frequency", "recency", "T", "monetary_value"]].reset_index()
    rfm["cutoff_date"] = pd.Timestamp("2020-01-03").date()
    assert reconcile_rfm(clean, reverse, rfm)["max_differences"]["monetary_value"] == 0
    rfm.loc[0, "monetary_value"] += 1
    with pytest.raises(ModelError, match="monetary_value mismatches"):
        reconcile_rfm(clean, reverse, rfm)


def test_undefined_means_stop_instead_of_clipping():
    features = pd.DataFrame({"frequency": [0, 1], "monetary_value": [0., 10.],
                             "recency": [0, 2], "T": [5, 5]})
    with pytest.raises(ModelError, match="q<=1"):
        predict_order_value(Fit({"p": 2, "q": 0.9, "gamma": 5}, {}), features)
    with pytest.raises(ModelError, match="singular"):
        predict_bgnbd(Fit({"r": 0.6, "alpha": 8, "a": 1., "b": 2.5}, {}), features, 90)
