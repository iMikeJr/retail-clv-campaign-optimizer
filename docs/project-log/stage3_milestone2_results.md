# Milestone 2: Run A verified results

Status: Run A completed and persisted; pause before B, C, and A_no_cap. The README, full methodology document, and full-stack Compose run remain milestone 4 work.

## Data and protocol

- Training cutoff: 2011-06-12; test cutoff: 2011-09-10; window: 90 days.
- Training customers: 4,950; positives: 1,587; base rate: 32.0606%.
- Test customers: 5,254; positives: 2,286; base rate: 43.5097%. Shift: 11.4491 percentage points.
- Purchase-value cap: GBP 3,679.502, estimated at the training cutoff and reused at the test cutoff. Labels and realized spend remain uncapped.
- clean_transactions already excludes quick reversals. Historical features restore rows from reversed_purchases if the cancellation occurs after the feature cutoff. Label purchases use the window endpoint as their observation cutoff.
- ETL reconciliation: all 5,851 customers at its stored cutoff matched exactly for frequency, recency, T, and uncapped monetary_value.
- Persisted run: `A:2011-09-10:90`; 26,270 prediction rows; 337 metric rows; exactly three modeling tables.

## Test comparison

Revenue capture ranks by expected_value_N; lift ranks by propensity. Gamma-Gamma is the shared value model, so its errors appear separately rather than as classifier scores.

| Model | ROC AUC | AP | Log loss | Brier | Lift top 10% | Revenue top 10% | Revenue top 20% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_const | 0.5000 | 0.4351 | 0.7133 | 0.2589 | 1.071 | 50.50% | 62.16% |
| baseline_recent | 0.7627 | 0.6859 | 0.6543 | 0.2177 | 1.796 | 53.42% | 66.11% |
| bgnbd | 0.8008 | 0.7745 | 0.5524 | 0.1862 | 2.110 | 57.84% | 72.74% |
| logreg | 0.7927 | 0.7680 | 0.5900 | 0.1982 | 2.110 | 57.05% | 72.28% |
| gboost | 0.7990 | 0.7751 | 0.5818 | 0.1952 | 2.132 | 57.45% | 72.43% |

Bootstrap percentile 95% intervals: 200 paired customer resamples, seed 42.

| Model | AUC interval | AP interval |
| --- | --- | --- |
| baseline_const | [0.5000, 0.5000] | [0.4209, 0.4496] |
| baseline_recent | [0.7504, 0.7763] | [0.6669, 0.7086] |
| bgnbd | [0.7886, 0.8125] | [0.7593, 0.7919] |
| logreg | [0.7810, 0.8050] | [0.7516, 0.7864] |
| gboost | [0.7870, 0.8113] | [0.7593, 0.7934] |

Chosen hyperparameters: logistic C=0.1; boosting depth=2, learning_rate=0.1, iterations=62. Selection used training-customer validation log loss only; boosting refit uses the selected iteration count and all training rows.

## Fits and convergence

| Cutoff | r | alpha (days) | a | b | Fit seconds | Statuses of four starts |
| --- | --- | --- | --- | --- | --- | --- |
| train | 0.682733 | 66.621984 | 0.154590 | 3.315974 | 0.1650 | [0, 0, 0, 0] |
| test | 0.641845 | 63.638781 | 0.174016 | 2.738587 | 0.1569 | [0, 0, 0, 0] |

| Cutoff | p | q | gamma (GBP) | Spearman rho | Fit seconds | Statuses of four starts |
| --- | --- | --- | --- | --- | --- | --- |
| train | 2.328066 | 3.775141 | 471.493424 | 0.249681 | 0.0280 | [0, 0, 0, 0] |
| test | 2.171352 | 3.778588 | 497.887958 | 0.271010 | 0.0298 | [0, 0, 0, 0] |

All 16 starts converged with optimizer status 0; no selected fit reached the numerical bounds. Fit times include all four starts. Full iteration counts, objective values, status messages and starting values are stored in model_runs.params and printed by the service.

## Simulation validation at the fitted a < 1

True parameters are the exact unrounded Run A test-cutoff fit. Simulated 100,000 independent customers, ages uniform over 100–400 days, a 90-day future window, and seed 42. Sample size and seed were fixed before executing the check.

| Parameter | True | Recovered | Relative error |
| --- | --- | --- | --- |
| r | 0.641845 | 0.642558 | 0.11% |
| alpha | 63.638781 | 63.291326 | 0.55% |
| a | 0.174016 | 0.179437 | 3.12% |
| b | 2.738587 | 2.910050 | 6.26% |

| Group | Customers | Expected purchases | Simulated purchases | Error | Expected purchasers | Simulated purchasers | Error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| overall | 100000 | 74449.80 | 73733 | 0.97% | 37481.23 | 37374 | 0.29% |
| frequency_0 | 37476 | 7862.42 | 7888 | 0.32% | 6209.78 | 6256 | 0.74% |

Every parameter error is below 15%; both aggregate errors are below 3%, including the zero-repeat subgroup. An additional independent quadrature test agrees with the finite-horizon count formula at a=0.7 to relative tolerance 1e-9.

The evidence supports numerical validity of the implemented finite-horizon closed form at the fitted a<1. It does not establish forecasting accuracy on real customers. [Fader and Hardie, note 041](https://www.brucehardie.com/notes/041/) explains why the expectation equations remain correct although the original derivation did not cover the entire parameter space. The code stops near the singular a=1 expression or on non-finite/inconsistent counts; it never clips a.

For the at-least-one-purchase probability, condition on being alive: the purchase rate has Gamma(r+x, alpha+T) distribution, so its Laplace transform gives the no-arrival probability ((alpha+T)/(alpha+T+N))^(r+x). Multiplying its complement by p_alive gives the requested formula. Dropout occurs after a purchase: like a shopper who can leave only after checking out, it cannot prevent the first future checkout.

Original 50,000-customer recovery checks (seed 42):

| Model | Parameter relative errors | Aggregate purchases error | Aggregate purchasers error |
| --- | --- | --- | --- |
| BG/NBD | r=0.15%, alpha=0.86%, a=0.47%, b=0.03% | 0.33% | 1.12% |
| Gamma-Gamma | p=1.81%, q=1.06%, gamma=0.99% | n/a | n/a |

## Gamma-Gamma order-value errors

Only customers purchasing in the test window enter these metrics. Buckets use repeat frequency at the test cutoff. Actual order value is each customer’s window spend divided by their window purchase count; WAPE is sum of absolute customer-mean errors divided by sum of actual customer means.

| Frequency | Buyers | MAE (GBP) | WAPE | Median absolute percentage error |
| --- | --- | --- | --- | --- |
| overall | 2286 | 198.47 | 42.53% | 32.34% |
| 0 | 344 | 224.59 | 58.96% | 54.03% |
| 1 | 291 | 166.70 | 47.39% | 44.71% |
| 2-3 | 459 | 160.81 | 41.87% | 34.98% |
| 4-7 | 524 | 190.21 | 38.38% | 28.21% |
| 8+ | 668 | 231.21 | 38.87% | 24.18% |

Relative errors are largest for zero-repeat and low-frequency buyers. These descriptive differences quantify error heterogeneity; they do not identify how much error was caused by the observed frequency–monetary correlation. The positive Spearman correlation is a warning about the independence assumption, not an automatic model rejection.

## Counts, runtime, and limitations

- BG/NBD predicts 3,737.93 purchases versus 4,915 realized (-23.95%); per-customer MAE is 0.6955. This underprediction is material despite correct simulation recovery.
- Standalone service command wall time: 6.727 seconds, including Compose/container startup and Python imports. Internal processing and persistence: 5.777 seconds. Build and test times are excluded.
- A rough four-times wall-time projection is 26.9 seconds, comfortably below ten minutes. This is an estimate; B, C and sensitivity have not run.
- Full model container suite: 12 passed in 17.84 seconds; existing ETL suite: 39 passed. Rollback deliberately injects a duplicate, accepts either the psycopg or SQLAlchemy integrity exception, and compares the complete saved rows in all three tables before and after failure.
- No-cap sensitivity, off-peak/long-window evaluation, completed methodology/README and the full docker compose up --build run are pending later milestones.
- Expected_value_N values one purchase occasion, whereas bgnbd_clv_N includes expected repeat counts. Neither estimates incremental revenue caused by a retention action.
- BG/NBD assumes continuous-time arrivals while observations are aggregated to calendar days; synthetic recovery tests validate the continuous-time likelihood and predictions, not this approximation or seasonality. Observed first purchases may not be true acquisition dates.
- The cap reduces large historical values while actual spending remains uncapped. Bootstrap intervals condition on fitted models and do not include parameter-estimation uncertainty. Test metrics describe one seasonal window, not guaranteed future performance.
