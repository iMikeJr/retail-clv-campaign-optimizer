import numpy as np
import pandas as pd
import pytest

from data import FEATURES
from evaluation import evaluate, sensitivity_differences


def test_constant_calibration_and_business_denominators():
    customers = pd.Index([str(i) for i in range(20)], name="customer_id")
    features = pd.DataFrame(0., index=customers, columns=FEATURES)
    predictions = pd.DataFrame({"customer_id": customers, "model": "bgnbd",
                                "p_purchase_N": 0.5, "expected_order_value": 20.,
                                "expected_purchases_N": 0.6, "expected_value_N": 10.,
                                "actual_purchased": [1, 0] * 10,
                                "actual_purchases": [1, 0] * 10,
                                "actual_spend": [10., 0.] * 10})
    metrics = evaluate(predictions, features, {}, 42, bootstrap=True)
    indexed = metrics.set_index(["model", "metric", "segment"]).value
    assert indexed["bgnbd", "roc_auc", "overall"] == 0.5
    assert indexed["bgnbd", "calib_n", "1"] == 20
    assert indexed["bgnbd", "calib_observed_rate", "1"] == 0.5
    assert indexed["bgnbd", "mean_predicted_probability", "overall"] == 0.5
    assert indexed["bgnbd", "observed_positive_rate", "overall"] == 0.5
    assert indexed["bgnbd", "calibration_gap", "overall"] == 0
    assert indexed["bgnbd", "expected_purchases_sum", "overall"] == pytest.approx(12.)
    assert indexed["gamma_gamma", "order_value_mae", "overall"] == 10
    assert indexed["gamma_gamma", "order_value_wape", "overall"] == 1
    assert indexed["gamma_gamma", "order_value_median_ape", "overall"] == 1
    assert not metrics.duplicated(["model", "metric", "segment"]).any()
    assert metrics.loc[metrics.metric.eq("calib_n"), "value"].sum() == 20
    assert np.isfinite(metrics.loc[metrics.value.notna(), "value"]).all()


def test_order_value_buckets_use_cutoff_frequency_and_customer_mean_values():
    customers = pd.Index(["a", "b", "c", "d"], name="customer_id")
    features = pd.DataFrame(0., index=customers, columns=FEATURES)
    features["frequency"] = [1, 2, 5, 9]
    predictions = pd.DataFrame({"customer_id": customers, "model": "bgnbd",
                                "p_purchase_N": 0.5, "expected_order_value": 20.,
                                "expected_purchases_N": 0.6, "expected_value_N": 10.,
                                "actual_purchased": 1, "actual_purchases": [1, 2, 1, 2],
                                "actual_spend": [10., 40., 30., 80.]})
    # Shuffle to ensure the buckets align by customer identity rather than row order.
    metrics = evaluate(predictions.iloc[::-1], features, {}, 42)
    indexed = metrics.set_index(["model", "metric", "segment"]).value
    for bucket, error, wape in (("1", 10, 1), ("2-3", 0, 0), ("4-7", 10, 1/3), ("8+", 20, 0.5)):
        assert indexed["gamma_gamma", "order_value_n", bucket] == 1
        assert indexed["gamma_gamma", "order_value_mae", bucket] == error
        assert indexed["gamma_gamma", "order_value_wape", bucket] == pytest.approx(wape)
    assert indexed["gamma_gamma", "order_value_n", "0"] == 0
    assert np.isnan(indexed["gamma_gamma", "order_value_mae", "0"])


def test_paired_bootstrap_differences_share_customer_resamples():
    customers = pd.Index([str(i) for i in range(20)], name="customer_id")
    features = pd.DataFrame(0., index=customers, columns=FEATURES)
    y = np.array([1, 0] * 10)
    bg = pd.DataFrame({"customer_id": customers, "model": "bgnbd",
                       "p_purchase_N": np.where(y, 0.8, 0.2), "expected_order_value": 20.,
                       "expected_purchases_N": 0.9, "expected_value_N": 10.,
                       "actual_purchased": y, "actual_purchases": y, "actual_spend": y * 10.})
    predictions = pd.concat([bg, bg.assign(model="logreg", p_purchase_N=0.5),
                             bg.assign(model="gboost").iloc[::-1]], ignore_index=True)
    metrics = evaluate(predictions, features, {}, 42, bootstrap=True)
    indexed = metrics.set_index(["model", "metric", "segment"]).value
    rng = np.random.default_rng(42)
    samples = [rng.integers(0, len(y), len(y)) for _ in range(200)]
    expected_ap_diffs = [1 - y[index].mean() for index in samples if len(np.unique(y[index])) == 2]
    low, high = np.quantile(expected_ap_diffs, [0.025, 0.975])
    assert indexed["bgnbd", "roc_auc_difference", "vs_logreg"] == 0.5
    assert indexed["bgnbd", "roc_auc_difference_ci_lower", "vs_logreg"] == 0.5
    assert indexed["bgnbd", "average_precision_difference_ci_lower", "vs_logreg"] == pytest.approx(low)
    assert indexed["bgnbd", "average_precision_difference_ci_upper", "vs_logreg"] == pytest.approx(high)
    for metric in ("roc_auc", "average_precision"):
        for suffix in ("difference", "difference_ci_lower", "difference_ci_upper"):
            assert indexed["bgnbd", f"{metric}_{suffix}", "vs_gboost"] == 0
    assert indexed["bgnbd", "average_precision_difference_bootstrap_valid_n", "vs_logreg"] == 200


def test_uncapped_differences_are_uncapped_minus_capped_and_preserve_segments():
    capped = pd.DataFrame([("bgnbd", "roc_auc", "overall", 0.8),
                           ("gamma_gamma", "order_value_mae", "1", 100.)],
                          columns=["model", "metric", "segment", "value"])
    uncapped = capped.copy()
    uncapped["value"] = [0.79, 130.]
    differences = sensitivity_differences(capped, uncapped).set_index(["model", "metric", "segment"]).value
    assert differences["bgnbd", "roc_auc_difference_vs_capped", "overall"] == pytest.approx(-0.01)
    assert differences["gamma_gamma", "order_value_mae_difference_vs_capped", "1"] == 30
    assert capped.value.tolist() == [0.8, 100.]
