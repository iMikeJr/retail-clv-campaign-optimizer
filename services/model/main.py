"""One-shot predictive core: temporal experiments, sensitivity and production scoring."""

import argparse
from dataclasses import asdict
from importlib.metadata import version
import json
import os
import sys
import time

import numpy as np
import pandas as pd

from classifiers import fit_recent, fit_supervised, predict_recent
from data import (ModelError, build_features, build_labels, purchase_cap, reconcile_rfm)
from db import database_engine, load_inputs, publish
from evaluation import evaluate, sensitivity_differences
from probabilistic import fit_bgnbd, fit_gamma_gamma, predict_bgnbd, predict_order_value


# All experiment dates live here; training cutoff and window endpoint are derived.
EXPERIMENTS = {"A": ("2011-09-10", 90), "B": ("2011-06-12", 180), "C": ("2011-04-30", 90)}
EXPERIMENTS["A_no_cap"] = EXPERIMENTS["A"]


def run_experiment(cutoff, window_days, *, clean, reversals, seed=42, name="A", capped=True,
                   scoring=False):
    tick = time.perf_counter()
    cutoff = pd.Timestamp(cutoff).normalize()
    train_cutoff = cutoff - pd.Timedelta(days=window_days)
    required_end = cutoff if scoring else cutoff + pd.Timedelta(days=window_days)
    if window_days <= 0 or clean.invoice_date.max().normalize() < required_end:
        raise ModelError("Invalid window or incomplete test-label coverage.")
    cap = purchase_cap(clean, reversals, train_cutoff) if capped else None
    train = build_features(clean, reversals, train_cutoff, cap)
    test = build_features(clean, reversals, cutoff, cap)
    train_labels = build_labels(clean, reversals, train.index, train_cutoff, window_days)
    test_labels = (pd.DataFrame(np.nan, index=test.index,
                   columns=["actual_purchases", "actual_spend", "actual_purchased"])
                   if scoring else build_labels(clean, reversals, test.index, cutoff, window_days))
    params = {"backend": "numpy_scipy_mle", "purchase_cap": cap,
              "versions": {package: version(package) for package in (
                  "numpy", "scipy", "scikit-learn", "pandas", "SQLAlchemy", "psycopg")}}
    fits = {}
    for period, features in (("train", train), ("test", test)):
        fits[period] = {}
        for model, fitter in (("bgnbd", fit_bgnbd), ("gamma_gamma", fit_gamma_gamma)):
            fit = fitter(features)
            fits[period][model] = fit
            print(json.dumps({"event": "fit", "cutoff": str((train_cutoff if period == "train" else cutoff).date()),
                              "period": period, "model": model, **asdict(fit)}, allow_nan=False), flush=True)
        # Validate the means at both cutoffs, even though only test predictions persist.
        predict_bgnbd(fits[period]["bgnbd"], features, window_days)
        predict_order_value(fits[period]["gamma_gamma"], features)
    params["cutoff_fits"] = {period: {model: asdict(fit) for model, fit in values.items()}
                             for period, values in fits.items()}
    models, supervised_params = fit_supervised(train, train_labels, seed)
    params.update(supervised_params)
    recent, recent_params = fit_recent(train, train_labels.actual_purchased.to_numpy())
    params["baseline_recent"] = recent_params
    train_rate = float(train_labels.actual_purchased.mean())
    params["baseline_const"] = {"probability": train_rate}
    p_alive, bg_probability, bg_count = predict_bgnbd(fits["test"]["bgnbd"], test, window_days)
    order_value = predict_order_value(fits["test"]["gamma_gamma"], test)
    probabilities = {"baseline_const": np.full(len(test), train_rate),
                     "baseline_recent": predict_recent(recent, test), "bgnbd": bg_probability,
                     **{model: estimator.predict_proba(test.to_numpy(dtype=float))[:, 1]
                        for model, estimator in models.items()}}
    predictions = []
    for model, probability in probabilities.items():
        if not np.isfinite(probability).all() or np.any((probability < 0) | (probability > 1)):
            raise ModelError(f"Invalid probabilities for {model}.")
        frame = test_labels.copy()
        frame["model"] = model
        frame["p_purchase_N"] = probability
        frame["expected_purchases_N"] = bg_count if model == "bgnbd" else np.nan
        frame["expected_order_value"] = order_value
        frame["expected_value_N"] = probability * order_value
        frame["p_alive"] = p_alive if model == "bgnbd" else np.nan
        frame["bgnbd_clv_N"] = bg_count * order_value if model == "bgnbd" else np.nan
        predictions.append(frame.reset_index())
    predictions = pd.concat(predictions, ignore_index=True)
    metrics = (pd.DataFrame([(model, metric, "overall", value)
                for model, probability in probabilities.items()
                for metric, value in (("test_n", len(test)),
                                      ("mean_predicted_probability", float(probability.mean())))],
                columns=["model", "metric", "segment", "value"])
               if scoring else evaluate(predictions, test, models, seed, bootstrap=True))
    extra = []
    for period, values in fits.items():
        for model, fit in values.items():
            for parameter, value in fit.parameters.items():
                extra.append((model, f"fitted_{parameter}", period, value))
            if model == "gamma_gamma":
                for metric in ("n_fit", "spearman_rho", "spearman_pvalue"):
                    extra.append((model, metric, period, fit.diagnostics[metric]))
    if not scoring:
        metrics = pd.concat([metrics, pd.DataFrame(extra, columns=["model", "metric", "segment", "value"])],
                            ignore_index=True)
    params["compute_seconds"] = time.perf_counter() - tick
    if scoring:
        params.update(mode="scoring", horizon_end=str((cutoff + pd.Timedelta(days=window_days)).date()),
                      training_label_end=str(cutoff.date()))
    else:
        params["bootstrap"] = {"resamples": 200, "random_seed": seed, "method": "paired_customer_percentile"}
    run = {"run_id": f"{name}:{cutoff.date()}:{window_days}", "run_name": name,
           "test_cutoff": cutoff.date(), "train_cutoff": train_cutoff.date(), "window_days": window_days,
           "n_train": len(train), "n_test": len(test), "base_rate_train": train_rate,
           "base_rate_test": None if scoring else float(test_labels.actual_purchased.mean()), "random_seed": seed,
           "params": params}
    return run, metrics, predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconcile-only", action="store_true")
    parser.add_argument("--run", choices=[*EXPERIMENTS, "PROD", "all"], default="all")
    args = parser.parse_args()
    start = time.perf_counter()
    seed = int(os.environ.get("RANDOM_SEED", "42"))
    if not 0 <= seed < 2**32:
        raise ModelError("RANDOM_SEED must be in [0, 2**32).")
    engine = database_engine()
    try:
        clean, reversals, rfm = load_inputs(engine)
        reconciliation = reconcile_rfm(clean, reversals, rfm)
        print(json.dumps({"event": "etl_reconciliation", **reconciliation}), flush=True)
        if args.reconcile_only:
            return
        names = [*EXPERIMENTS, "PROD"] if args.run == "all" else [args.run]
        # Sensitivity always compares against a freshly capped A on this same snapshot.
        if "A_no_cap" in names and "A" not in names:
            names.insert(0, "A")
        computed_metrics = {}
        for name in names:
            tick = time.perf_counter()
            dates = ("2011-12-09", 90) if name == "PROD" else EXPERIMENTS[name]
            run, metrics, predictions = run_experiment(*dates, clean=clean,
                reversals=reversals, seed=seed, name=name, capped=(name != "A_no_cap"),
                scoring=name == "PROD")
            if name == "A_no_cap":
                metrics = pd.concat([metrics, sensitivity_differences(computed_metrics["A"], metrics)],
                                    ignore_index=True)
                run["params"]["sensitivity_reference"] = "A"
            computed_metrics[name] = metrics
            run["params"]["etl_reconciliation"] = reconciliation
            publish(engine, run, metrics, predictions)
            summary = metrics.loc[metrics.segment.eq("overall")].pivot(index="model", columns="metric", values="value")
            selected = ["roc_auc", "average_precision", "log_loss", "brier_score", "mean_predicted_probability",
                        "observed_positive_rate", "calibration_gap", "lift_top_10pct",
                        "revenue_capture_top_10pct", "revenue_capture_top_20pct"]
            if name == "PROD":
                summary["mean_order_value"] = predictions.groupby("model").expected_order_value.mean()
                selected = ["test_n", "mean_predicted_probability", "mean_order_value"]
            print(summary.reindex(index=["baseline_const", "baseline_recent", "bgnbd", "logreg", "gboost"],
                                  columns=selected).to_string(), flush=True)
            print(json.dumps({"event": "committed", "run_id": run["run_id"], "n_train": run["n_train"],
                              "n_test": run["n_test"], "base_rate_train": run["base_rate_train"],
                              "base_rate_test": run["base_rate_test"], "prediction_rows": len(predictions),
                              "metric_rows": len(metrics), "run_seconds": time.perf_counter() - tick}), flush=True)
        print(json.dumps({"event": "batch_completed", "runs": names,
                          "service_seconds": time.perf_counter() - start}), flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except ModelError as error:
        print(f"Model stopped: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Never print exception strings that could contain database credentials.
        print(f"Model failed ({type(error).__name__}); inspect inputs, database availability, "
              "and configured settings. No credentials are logged.", file=sys.stderr)
        sys.exit(1)
