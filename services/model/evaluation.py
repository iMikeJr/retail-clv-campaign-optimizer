"""All model evidence in one long-format metric vocabulary."""

import math

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (average_precision_score, brier_score_loss, log_loss,
                             mean_absolute_error, roc_auc_score)

from data import FEATURES


def evaluate(predictions, features, models, seed, bootstrap=False):
    rows = []

    def add(model, metric, value, segment="overall"):
        value = float(value) if value is not None and np.isfinite(value) else None
        rows.append({"model": model, "metric": metric, "segment": str(segment), "value": value})

    rng = np.random.default_rng(seed)
    # Paired resamples across all models; preserve class variation for AUC.
    resamples = [rng.integers(0, len(features), len(features)) for _ in range(200)] if bootstrap else []
    bootstrap_scores = {}
    point_scores = {}
    for model, frame in predictions.groupby("model", sort=True):
        frame = frame.set_index("customer_id").reindex(features.index)
        y = frame.actual_purchased.to_numpy()
        p = frame.p_purchase_N.to_numpy()
        two_classes = len(np.unique(y)) == 2
        base = y.mean()
        add(model, "roc_auc", roc_auc_score(y, p) if two_classes else None)
        add(model, "average_precision", average_precision_score(y, p) if y.sum() else None)
        add(model, "log_loss", log_loss(y, p, labels=[0, 1]))
        add(model, "brier_score", brier_score_loss(y, p))
        add(model, "test_n", len(y))
        add(model, "test_positives", y.sum())
        add(model, "test_base_rate", base)
        add(model, "mean_predicted_probability", p.mean())
        add(model, "observed_positive_rate", base)
        # Negative means probabilities are too low on average.
        add(model, "calibration_gap", p.mean() - base)
        if bootstrap:
            for metric, function in (("roc_auc", roc_auc_score), ("average_precision", average_precision_score)):
                samples = [function(y[index], p[index]) for index in resamples
                           if len(np.unique(y[index])) == 2]
                low, high = np.quantile(samples, [0.025, 0.975]) if samples else (None, None)
                add(model, f"{metric}_ci_lower", low)
                add(model, f"{metric}_ci_upper", high)
                add(model, f"{metric}_bootstrap_valid_n", len(samples))
                bootstrap_scores[model, metric] = np.asarray(samples)
                point_scores[model, metric] = function(y, p) if two_classes else None
        # qcut with duplicates='drop' yields no bins for a constant predictor.
        bins = pd.qcut(pd.Series(p), 10, labels=False, duplicates="drop")
        bins = bins.fillna(0).astype(int) + 1
        calibration = pd.DataFrame({"bin": bins, "p": p, "y": y})
        for number, group in calibration.groupby("bin"):
            add(model, "calib_n", len(group), number)
            add(model, "calib_mean_pred", group.p.mean(), number)
            add(model, "calib_observed_rate", group.y.mean(), number)
        ranking = frame.reset_index().sort_values(["p_purchase_N", "customer_id"], ascending=[False, True])
        top = ranking.head(math.ceil(0.1 * len(frame)))
        add(model, "lift_top_10pct", top.actual_purchased.mean() / base if base else None)
        ranking = frame.reset_index().sort_values(["expected_value_N", "customer_id"], ascending=[False, True])
        revenue = frame.actual_spend.sum()
        for fraction in (0.1, 0.2):
            selected = ranking.head(math.ceil(fraction * len(frame)))
            add(model, f"revenue_capture_top_{int(100*fraction)}pct",
                selected.actual_spend.sum() / revenue if revenue else None)
        if model == "bgnbd":
            buckets = pd.cut(features.frequency, [-1, 0, 1, 3, 7, np.inf],
                             labels=["0", "1", "2-3", "4-7", "8+"])
            for segment in ("overall", "0", "1", "2-3", "4-7", "8+"):
                group = frame if segment == "overall" else frame.loc[buckets.eq(segment)]
                add(model, "count_customers", len(group), segment)
                add(model, "expected_purchases_sum", group.expected_purchases_N.sum(), segment)
                add(model, "actual_purchases_sum", group.actual_purchases.sum(), segment)
                add(model, "purchases_mae", mean_absolute_error(group.actual_purchases,
                    group.expected_purchases_N) if len(group) else None, segment)
    if bootstrap:
        for other in ("logreg", "gboost"):
            for metric in ("roc_auc", "average_precision"):
                if (other, metric) not in bootstrap_scores:
                    continue
                # Subtract scores from the SAME resampled customers, not CI endpoints.
                differences = bootstrap_scores["bgnbd", metric] - bootstrap_scores[other, metric]
                low, high = np.quantile(differences, [0.025, 0.975]) if len(differences) else (None, None)
                point = (point_scores["bgnbd", metric] - point_scores[other, metric]
                         if point_scores["bgnbd", metric] is not None else None)
                add("bgnbd", f"{metric}_difference", point, f"vs_{other}")
                add("bgnbd", f"{metric}_difference_ci_lower", low, f"vs_{other}")
                add("bgnbd", f"{metric}_difference_ci_upper", high, f"vs_{other}")
                add("bgnbd", f"{metric}_difference_bootstrap_valid_n", len(differences), f"vs_{other}")
    # A shared spend model has one set of order-value metrics, not five duplicates.
    frame = predictions.loc[predictions.model.eq("bgnbd")].set_index("customer_id").reindex(features.index)
    buyers = frame.loc[frame.actual_purchased.eq(1)]
    # Segments use repeat frequency as of the test cutoff, never window frequency.
    buckets = pd.cut(features.frequency.reindex(buyers.index), [-1, 0, 1, 3, 7, np.inf],
                     labels=["0", "1", "2-3", "4-7", "8+"])
    for segment in ("overall", "0", "1", "2-3", "4-7", "8+"):
        group = buyers if segment == "overall" else buyers.loc[buckets.eq(segment)]
        actual = (group.actual_spend / group.actual_purchases).to_numpy()
        errors = np.abs(group.expected_order_value.to_numpy() - actual)
        add("gamma_gamma", "order_value_n", len(group), segment)
        add("gamma_gamma", "order_value_mae", errors.mean() if len(errors) else None, segment)
        add("gamma_gamma", "order_value_wape", errors.sum() / actual.sum() if len(actual) else None, segment)
        add("gamma_gamma", "order_value_median_ape", np.median(errors / actual) if len(actual) else None, segment)
    y = frame.actual_purchased.to_numpy()
    X = features.to_numpy(dtype=float)
    for name, model in models.items():
        if len(np.unique(y)) == 2:
            importance = permutation_importance(model, X, y, scoring="roc_auc", n_repeats=10,
                                                random_state=seed, n_jobs=1)
            for feature, mean, std in zip(FEATURES, importance.importances_mean, importance.importances_std):
                add(name, "permutation_importance_auc_mean", mean, feature)
                add(name, "permutation_importance_auc_std", std, feature)
        if name == "logreg":
            for feature, coef in zip(FEATURES, model[-1].coef_[0]):
                add(name, "standardized_coefficient", coef, feature)
            add(name, "intercept", model[-1].intercept_[0])
    return pd.DataFrame(rows)


def sensitivity_differences(capped, uncapped):
    """Uncapped minus capped; keep the same customer split and random seed."""
    metrics = {"roc_auc", "average_precision", "log_loss", "brier_score", "lift_top_10pct",
               "revenue_capture_top_10pct", "revenue_capture_top_20pct",
               "mean_predicted_probability", "observed_positive_rate", "calibration_gap",
               "expected_purchases_sum", "actual_purchases_sum", "purchases_mae",
               "order_value_mae", "order_value_wape", "order_value_median_ape"}
    keys = ["model", "metric", "segment"]
    joined = uncapped.loc[uncapped.metric.isin(metrics)].merge(
        capped.loc[capped.metric.isin(metrics)], on=keys, suffixes=("_uncapped", "_capped"),
        validate="one_to_one")
    joined["value"] = joined.value_uncapped - joined.value_capped
    joined["metric"] += "_difference_vs_capped"
    return joined[keys + ["value"]]
