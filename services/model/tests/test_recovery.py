"""Independent event simulation, fixed seed 42; never search seeds for passing tests."""

import json

import numpy as np
import pandas as pd
from numpy.testing import assert_allclose
from scipy.integrate import quad
from scipy.special import hyp2f1

from probabilistic import Fit, fit_bgnbd, fit_gamma_gamma, predict_bgnbd, predict_order_value


def simulate_bgnbd(n=50_000, seed=42, window=90, parameters=None):
    """Simulate actual arrivals and dropout, without using prediction formulas."""
    rng = np.random.default_rng(seed)
    parameters = parameters or {"r": 0.6, "alpha": 8, "a": 1.2, "b": 2.5}
    rates = rng.gamma(parameters["r"], 1 / parameters["alpha"], n)
    dropout = rng.beta(parameters["a"], parameters["b"], n)
    ages = rng.uniform(100, 400, n)
    rows, future = [], []
    for rate, death_probability, age in zip(rates, dropout, ages):
        x, recency, count, clock = 0, 0.0, 0, 0.0
        while True:
            clock += rng.exponential(1 / rate)
            if clock > age + window:
                break
            if clock <= age:
                x += 1
                recency = clock
            else:
                count += 1
            if rng.random() < death_probability:
                break
        rows.append((x, recency, age))
        future.append(count)
    return pd.DataFrame(rows, columns=["frequency", "recency", "T"]), np.asarray(future)


def check_fitted_low_a_recovery(parameters):
    """Predeclared n=100,000 and seed=42; also validate the zero-repeat subgroup.

    Larger n reduces Monte Carlo uncertainty in the subgroup. Truth comes from
    the actual cutoff fit, not rounded report values or a selected simulation fit.
    """
    histories, future = simulate_bgnbd(n=100_000, parameters=parameters)
    fit = fit_bgnbd(histories)
    _, probabilities, counts = predict_bgnbd(fit, histories, 90)
    errors = {key: abs(fit.parameters[key] / value - 1) for key, value in parameters.items()}
    segments = {}
    for name, mask in (("overall", np.ones(len(histories), dtype=bool)),
                       ("frequency_0", histories.frequency.eq(0).to_numpy())):
        actual_count = int(future[mask].sum())
        actual_buyers = int((future[mask] > 0).sum())
        expected_count = float(counts[mask].sum())
        expected_buyers = float(probabilities[mask].sum())
        segments[name] = {"n": int(mask.sum()), "actual_purchases": actual_count,
                          "expected_purchases": expected_count, "actual_purchasers": actual_buyers,
                          "expected_purchasers": expected_buyers,
                          "counts_relative_error": abs(expected_count / actual_count - 1),
                          "purchasers_relative_error": abs(expected_buyers / actual_buyers - 1)}
    report = {"seed": 42, "window_days": 90, "true_parameters": parameters,
              "fitted_parameters": fit.parameters, "parameter_relative_errors": errors,
              "segments": segments, "diagnostics": fit.diagnostics}
    print("BG_LOW_A_RECOVERY", json.dumps(report), flush=True)
    assert max(errors.values()) < 0.15
    for segment in segments.values():
        assert segment["counts_relative_error"] < 0.03
        assert segment["purchasers_relative_error"] < 0.03
    return report


def test_bgnbd_simulation_recovery():
    histories, future = simulate_bgnbd()
    truth = {"r": 0.6, "alpha": 8, "a": 1.2, "b": 2.5}
    fit = fit_bgnbd(histories)
    _, probabilities, counts = predict_bgnbd(fit, histories, 90)
    errors = {k: abs(fit.parameters[k] / value - 1) for k, value in truth.items()}
    counts_error = abs(counts.sum() / future.sum() - 1)
    purchasers_error = abs(probabilities.sum() / (future > 0).sum() - 1)
    print("BG_RECOVERY", json.dumps({"n": len(histories), "seed": 42,
          "parameters": fit.parameters, "relative_errors": errors,
          "counts_relative_error": counts_error, "purchasers_relative_error": purchasers_error,
          "expected_count": counts.sum(), "actual_count": int(future.sum()),
          "expected_purchasers": probabilities.sum(), "actual_purchasers": int((future > 0).sum()),
          "diagnostics": fit.diagnostics}))
    assert max(errors.values()) < 0.15
    assert counts_error < 0.03
    assert purchasers_error < 0.03


def test_gamma_gamma_simulation_recovery():
    rng = np.random.default_rng(42)
    n = 50_000
    x = rng.integers(1, 21, n)
    rates = rng.gamma(4, 1 / 100, n)
    # Sum x independent Gamma(p, rate) purchases using Gamma additivity.
    money = rng.gamma(6 * x, 1 / rates) / x
    features = pd.DataFrame({"frequency": x, "monetary_value": money})
    fit = fit_gamma_gamma(features)
    truth = {"p": 6, "q": 4, "gamma": 100}
    errors = {k: abs(fit.parameters[k] / value - 1) for k, value in truth.items()}
    print("GG_RECOVERY", json.dumps({"n": n, "seed": 42, "parameters": fit.parameters,
                                   "relative_errors": errors, "diagnostics": fit.diagnostics}))
    assert max(errors.values()) < 0.15
    single = pd.DataFrame({"frequency": [0], "monetary_value": [0.]})
    assert_allclose(predict_order_value(fit, single),
                    fit.parameters["p"] * fit.parameters["gamma"] / (fit.parameters["q"] - 1))


def test_finite_horizon_counts_below_one_agree_with_integral():
    # Independent finite integral verifies analytic continuation at a<1.
    fit = Fit({"r": 0.6, "alpha": 8, "a": 0.7, "b": 2.5}, {})
    features = pd.DataFrame({"frequency": [0, 1, 5], "recency": [0, 80, 95], "T": [100] * 3})
    alive, _, counts = predict_bgnbd(fit, features, 90)
    reference = []
    for x, pa in zip(features.frequency, alive):
        # E[lambda exp(-lambda*p*t) | alive] integrated over t in [0,N].
        rate = (0.6 + x) / 108
        integral, _ = quad(lambda t: rate * hyp2f1(1.6 + x, 0.7, 3.2 + x, -t / 108), 0, 90)
        reference.append(pa * integral)
    assert_allclose(counts, reference, rtol=1e-9)
