"""Small, explicit grids. Validation customers are never used to fit candidates."""

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from data import ModelError


def fit_recent(features, y):
    """Monotone sigmoid of the specified recency score; no tuning grid."""
    score = -features.days_since_last.to_numpy(dtype=float) / 100

    def objective(theta):
        z = theta[0] + theta[1] * score
        loss = np.mean(np.logaddexp(0, z) - y * z)
        residual = expit(z) - y
        return loss, np.array([residual.mean(), np.mean(residual * score)])

    result = minimize(objective, [0., 1.], jac=True, method="L-BFGS-B",
                      bounds=[(None, None), (0, None)])
    if not result.success:
        raise ModelError(f"Recent-baseline sigmoid failed: status={result.status}.")
    return result.x, {"intercept": float(result.x[0]), "slope_per_100_days": float(result.x[1]),
                      "success": bool(result.success), "status": int(result.status)}


def predict_recent(coefficients, features):
    return expit(coefficients[0] - coefficients[1] * features.days_since_last.to_numpy() / 100)


def fit_supervised(features, labels, seed):
    y = labels.actual_purchased.to_numpy()
    development, validation = train_test_split(np.arange(len(features)), test_size=0.2,
                                               random_state=seed)
    X = features.to_numpy(dtype=float)
    if len(np.unique(y[development])) != 2 or len(np.unique(y[validation])) != 2:
        raise ModelError("Development and validation must both contain both label classes.")
    models, parameters = {}, {}
    trials = []
    for C in (0.01, 0.1, 1, 10):
        candidate = make_pipeline(StandardScaler(), LogisticRegression(C=C, l1_ratio=0.0,
                                  max_iter=2000, random_state=seed))
        candidate.fit(X[development], y[development])
        loss = log_loss(y[validation], candidate.predict_proba(X[validation])[:, 1], labels=[0, 1])
        trials.append({"C": C, "validation_log_loss": float(loss)})
    chosen = min(trials, key=lambda row: row["validation_log_loss"])
    model = make_pipeline(StandardScaler(), LogisticRegression(C=chosen["C"], l1_ratio=0.0,
                          max_iter=2000, random_state=seed))
    model.fit(X, y)
    if np.any(model[-1].n_iter_ >= 2000):
        raise ModelError("Logistic regression reached the iteration limit.")
    models["logreg"] = model
    parameters["logreg"] = {"C": chosen["C"], "grid": trials}
    trials = []
    for depth in (2, 3, 4):
        for rate in (0.03, 0.1):
            candidate = HistGradientBoostingClassifier(max_depth=depth, learning_rate=rate,
                         max_iter=400, early_stopping=True, min_samples_leaf=50,
                         scoring="loss", random_state=seed)
            candidate.fit(X[development], y[development])
            loss = log_loss(y[validation], candidate.predict_proba(X[validation])[:, 1], labels=[0, 1])
            trials.append({"max_depth": depth, "learning_rate": rate,
                           "iterations": int(candidate.n_iter_), "validation_log_loss": float(loss)})
    chosen = min(trials, key=lambda row: row["validation_log_loss"])
    model = HistGradientBoostingClassifier(max_depth=chosen["max_depth"],
                learning_rate=chosen["learning_rate"], max_iter=chosen["iterations"],
                early_stopping=False, min_samples_leaf=50, random_state=seed)
    model.fit(X, y)
    models["gboost"] = model
    parameters["gboost"] = {**chosen, "grid": trials, "refit_early_stopping": False}
    parameters["validation"] = {"development_n": len(development), "validation_n": len(validation),
                                "split": "random_customer_80_20", "random_seed": seed}
    return models, parameters
