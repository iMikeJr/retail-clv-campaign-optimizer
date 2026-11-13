"""Vectorized BG/NBD and Gamma-Gamma maximum likelihood, in log parameters.

References: Fader, Hardie & Lee (2005), Hardie notes 039 and 041;
Fader & Hardie (2013), note 025. Gamma parameters use shape/rate conventions.
No regularization or restrictions a>1 / q>1 are imposed during estimation.
"""

from dataclasses import dataclass
import time

import numpy as np
from scipy.optimize import minimize
from scipy.special import betaln, gammaln, hyp2f1
from scipy.stats import spearmanr

from data import ModelError


@dataclass
class Fit:
    parameters: dict
    diagnostics: dict


def _multistart(objective, starts, names, scale_parameter=None, scale=1.0):
    tick = time.perf_counter()
    attempts = []
    candidates = []
    for start in starts:
        result = minimize(objective, np.log(start), method="L-BFGS-B",
                          bounds=[(-12, 12)] * len(start),
                          options={"maxiter": 1500, "ftol": 1e-12, "gtol": 1e-7})
        params = dict(zip(names, np.exp(result.x).tolist()))
        if scale_parameter:
            params[scale_parameter] *= scale
        boundary = bool(np.any(np.abs(result.x) > 12 - 1e-4))
        attempts.append({"start": dict(zip(names, map(float, start))),
                         "success": bool(result.success), "status": int(result.status),
                         "message": str(result.message), "iterations": int(result.nit),
                         "objective_mean_nll": float(result.fun), "parameters": params,
                         "numerical_boundary": boundary})
        if result.success and np.isfinite(result.fun) and not boundary:
            candidates.append((float(result.fun), len(attempts) - 1, params))
    if not candidates:
        raise ModelError(f"All likelihood starts failed or reached numerical bounds: {attempts}")
    _, chosen, params = min(candidates, key=lambda item: item[0])
    return Fit(params, {"method": "L-BFGS-B", "selected_start": chosen,
                        "fit_seconds": time.perf_counter() - tick, "attempts": attempts,
                        "normalization_scale": float(scale)})


def _bg_components(parameters, x, recency, age):
    r, alpha, a, b = parameters
    common = gammaln(r + x) - gammaln(r) + r * np.log(alpha) - betaln(a, b)
    alive = common + betaln(a, b + x) - (r + x) * np.log(alpha + age)
    dead = np.full_like(alive, -np.inf)
    repeat = x > 0
    dead[repeat] = (common[repeat] + betaln(a + 1, b + x[repeat] - 1)
                    - (r + x[repeat]) * np.log(alpha + recency[repeat]))
    return alive, dead


def fit_bgnbd(features):
    x = features.frequency.to_numpy(dtype=float)
    recency = features.recency.to_numpy(dtype=float)
    age = features["T"].to_numpy(dtype=float)
    if len(x) == 0 or np.any(age < recency) or np.any(recency < 0):
        raise ModelError("Invalid BG/NBD histories.")
    scale = max(float(age.max()), 1.0)
    recency, age = recency / scale, age / scale

    def objective(log_parameters):
        alive, dead = _bg_components(np.exp(log_parameters), x, recency, age)
        return -float(np.mean(np.logaddexp(alive, dead)))

    starts = [(0.6, 0.05, 1.2, 2.5), (1, 0.2, 0.5, 1),
              (0.3, 0.5, 2, 5), (2, 1, 1.5, 3)]
    return _multistart(objective, starts, ("r", "alpha", "a", "b"), "alpha", scale)


def predict_bgnbd(fit, features, window_days):
    """Predict alive, at least one purchase, and total future purchases.

    Alive-conditioned lambda is Gamma(r+x, alpha+T). Its Laplace transform
    gives P(no arrival | alive) = ((alpha+T)/(alpha+T+N))**(r+x).
    Dropout happens after an arrival, so it cannot prevent that first arrival.
    Therefore P(any arrival) = P(alive) * (1 - P(no arrival | alive)).

    The expected-count expression is also valid for a<1 by analytic continuation
    (Hardie note 041); the divergent infinite-horizon expectation does not imply
    divergent finite-horizon counts. At a=1 this particular form is singular:
    stop explicitly rather than modifying the fitted parameter.
    """
    r, alpha, a, b = (fit.parameters[k] for k in ("r", "alpha", "a", "b"))
    x = features.frequency.to_numpy(dtype=float)
    recency = features.recency.to_numpy(dtype=float)
    age = features["T"].to_numpy(dtype=float)
    alive_log, dead_log = _bg_components((r, alpha, a, b), x, recency, age)
    p_alive = np.exp(alive_log - np.logaddexp(alive_log, dead_log))
    log_survival = (r + x) * (-np.log1p(window_days / (alpha + age)))
    p_purchase = p_alive * (-np.expm1(log_survival))
    if abs(a - 1) < 1e-6:
        raise ModelError(f"BG/NBD expected-count expression singular near a=1: {fit.parameters}")
    hyper = hyp2f1(r + x, b + x, a + b + x - 1,
                  window_days / (alpha + age + window_days))
    counts = p_alive * (a + b + x - 1) / (a - 1) * (1 - np.exp(log_survival) * hyper)
    if (not np.isfinite(counts).all() or np.any(counts < -1e-10)
            or np.any(counts + 1e-8 < p_purchase)):
        raise ModelError(f"Invalid BG/NBD expected counts; parameters={fit.parameters}")
    return p_alive, p_purchase, counts


def fit_gamma_gamma(features):
    eligible = features.loc[features.frequency.gt(0) & features.monetary_value.gt(0)]
    if len(eligible) < 3:
        raise ModelError("Gamma-Gamma requires at least three positive repeat histories.")
    x = eligible.frequency.to_numpy(dtype=float)
    scale = float(eligible.monetary_value.mean())
    money = eligible.monetary_value.to_numpy(dtype=float) / scale

    def objective(log_parameters):
        p, q, gamma = np.exp(log_parameters)
        px = p * x
        log_density = (gammaln(px + q) - gammaln(px) - gammaln(q)
                       + px * np.log(x) + (px - 1) * np.log(money)
                       + q * np.log(gamma) - (px + q) * np.log(gamma + x * money))
        return -float(log_density.mean())

    starts = [(1, 3, 2), (3, 5, 4 / 3), (6, 2, 1 / 6), (0.5, 1.5, 1)]
    fit = _multistart(objective, starts, ("p", "q", "gamma"), "gamma", scale)
    corr = spearmanr(x, money)
    fit.diagnostics.update({"n_fit": len(eligible), "spearman_rho": float(corr.statistic),
                            "spearman_pvalue": float(corr.pvalue)})
    return fit


def predict_order_value(fit, features):
    p, q, gamma = (fit.parameters[k] for k in ("p", "q", "gamma"))
    if q <= 1:
        raise ModelError(f"Gamma-Gamma population mean undefined (q<=1): {fit.parameters}")
    x = features.frequency.to_numpy(dtype=float)
    money = features.monetary_value.to_numpy(dtype=float)
    value = p * (gamma + x * money) / (p * x + q - 1)
    if not np.isfinite(value).all() or np.any(value <= 0):
        raise ModelError(f"Invalid Gamma-Gamma expected value: {fit.parameters}")
    return value
