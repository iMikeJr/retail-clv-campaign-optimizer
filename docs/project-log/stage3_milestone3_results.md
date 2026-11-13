# Milestone 3: temporal experiments and uncapped sensitivity

Completed and paused before milestone 4. All outputs below were read back from Postgres after a successful one-shot execution; they are not proposed or simulated results unless explicitly marked. Code commit: 20a9727.

## Runs and reconciliation

| Item | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| Training cutoff | 2011-06-12 | 2010-12-14 | 2011-01-30 | 2011-06-12 |
| Test cutoff | 2011-09-10 | 2011-06-12 | 2011-04-30 | 2011-09-10 |
| Window (days) | 90 | 180 | 90 | 90 |
| Training customers | 4,950 | 4,292 | 4,381 | 4,950 |
| Test customers | 5,254 | 4,950 | 4,795 | 5,254 |
| Training positives | 1,587 | 1,969 | 1,474 | 1,587 |
| Test positives | 2,286 | 2,568 | 1,698 | 2,286 |
| Training base rate | 32.06% | 45.88% | 33.65% | 32.06% |
| Test base rate | 43.51% | 51.88% | 35.41% | 43.51% |
| Base-rate shift (pp) | +11.45 | +6.00 | +1.77 | +11.45 |
| Purchase cap (GBP) | 3,679.502 | 3,790.730 | 3,775.396 | None |

- A reconciles to 5,254 eligible customers and 2,286 positives; C to 4,795 and 1,698, exactly matching the earlier SQL counts. Historical feature restoration did not change these totals.
- ETL reconciliation still matches all 5,851 customers exactly at its stored cutoff. No ETL code or public table was changed.
- There are exactly three modeling tables, with 101,265 prediction rows and 1,558 metric rows across the four runs. All 337 original Run A metrics match milestone 2 exactly.
- All runs use seed 42, the same specified grids, and 200 paired customer-bootstrap resamples. No test labels were used to tune models or alter the design. A_no_cap uses the same labels, split and seed as A, with fresh fitting/tuning.

## Classification, side by side

### ROC AUC

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| baseline_recent | 0.7627 | 0.7697 | 0.7645 | 0.7627 |
| bgnbd | 0.8008 | 0.8112 | 0.8127 | 0.8008 |
| logreg | 0.7927 | 0.7966 | 0.8062 | 0.7923 |
| gboost | 0.7990 | 0.8033 | 0.8061 | 0.7991 |

### Average precision

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | 0.4351 | 0.5188 | 0.3541 | 0.4351 |
| baseline_recent | 0.6859 | 0.7654 | 0.6126 | 0.6859 |
| bgnbd | 0.7745 | 0.8362 | 0.7372 | 0.7745 |
| logreg | 0.7680 | 0.8248 | 0.7250 | 0.7661 |
| gboost | 0.7751 | 0.8308 | 0.7290 | 0.7751 |

### Log loss

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | 0.7133 | 0.6997 | 0.6507 | 0.7133 |
| baseline_recent | 0.6543 | 0.6567 | 0.5597 | 0.6543 |
| bgnbd | 0.5524 | 0.5269 | 0.4979 | 0.5524 |
| logreg | 0.5900 | 0.5641 | 0.5071 | 0.5851 |
| gboost | 0.5818 | 0.5616 | 0.5065 | 0.5815 |

### Brier score

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | 0.2589 | 0.2533 | 0.2290 | 0.2589 |
| baseline_recent | 0.2177 | 0.2267 | 0.1892 | 0.2177 |
| bgnbd | 0.1862 | 0.1768 | 0.1634 | 0.1862 |
| logreg | 0.1982 | 0.1933 | 0.1677 | 0.1982 |
| gboost | 0.1952 | 0.1914 | 0.1674 | 0.1952 |

BG/NBD has the lowest log loss and Brier score in all three temporal runs. A and B have the same test-window end; windows overlap across experiments, so these are not independent replications. Average precision changes with base rate, which differs substantially across windows.

## Calibration in the large

Cells are mean predicted probabilities. The observed row supplies the comparison for every classifier in that column. Gamma-Gamma is a shared order-value model and has no classifier probability. The signed calibration gap stored in model_metrics is mean prediction minus observed rate.

| Model / observation | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| Observed positive rate | 43.51% | 51.88% | 35.41% | 43.51% |
| baseline_const | 32.06% | 45.88% | 33.65% | 32.06% |
| baseline_recent | 28.97% | 34.58% | 29.53% | 28.97% |
| bgnbd | 34.99% | 51.61% | 38.81% | 34.99% |
| logreg | 31.35% | 43.64% | 32.29% | 31.53% |
| gboost | 31.09% | 41.84% | 31.56% | 31.11% |

Signed calibration gaps in percentage points:

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | -11.45 | -6.00 | -1.77 | -11.45 |
| baseline_recent | -14.54 | -17.30 | -5.88 | -14.54 |
| bgnbd | -8.52 | -0.26 | +3.40 | -8.52 |
| logreg | -12.16 | -8.24 | -3.12 | -11.98 |
| gboost | -12.42 | -10.04 | -3.85 | -12.40 |

BG/NBD is close to calibrated in the large in B, too low in A, and too high in C. All supervised models underestimate the overall positive rate in these runs; this is reported without test-set recalibration.

## Purchase counts

| Run | BG/NBD expected | Actual | Signed relative error | Per-customer MAE |
| --- | --- | --- | --- | --- |
| A | 3,737.93 | 4,915 | -23.95% | 0.6955 |
| B | 7,475.73 | 7,682 | -2.69% | 1.0341 |
| C | 3,765.59 | 3,297 | +14.21% | 0.5971 |
| A_no_cap | 3,737.93 | 4,915 | -23.95% | 0.6955 |

Good ranking and correct simulation recovery do not guarantee correct real-world aggregate counts. The direction of count error changes between A and C. Frequency-bucket counts and errors are stored for every run.

## Paired BG/NBD differences

Each estimate is BG/NBD minus the comparator. Each interval is the 2.5th–97.5th percentile of differences on the same 200 resampled customer indices, not a subtraction of marginal interval endpoints. All 200 draws were valid for each comparison. Intervals condition on the fitted models; no model is refit during resampling.

| Run | Comparator | Delta AUC | 95% interval | Delta AP | 95% interval |
| --- | --- | --- | --- | --- | --- |
| A | logreg | +0.00804 | [+0.00392, +0.01230] | +0.00645 | [+0.00190, +0.01072] |
| A | gboost | +0.00173 | [-0.00234, +0.00598] | -0.00065 | [-0.00590, +0.00378] |
| B | logreg | +0.01455 | [+0.00809, +0.01985] | +0.01136 | [+0.00508, +0.01672] |
| B | gboost | +0.00794 | [+0.00103, +0.01444] | +0.00542 | [-0.00086, +0.01103] |
| C | logreg | +0.00646 | [+0.00218, +0.01124] | +0.01220 | [+0.00440, +0.02192] |
| C | gboost | +0.00656 | [+0.00076, +0.01168] | +0.00818 | [+0.00142, +0.01548] |
| A_no_cap | logreg | +0.00847 | [+0.00431, +0.01213] | +0.00840 | [+0.00334, +0.01287] |
| A_no_cap | gboost | +0.00163 | [-0.00237, +0.00587] | -0.00064 | [-0.00599, +0.00372] |

Run A favors BG/NBD over logistic regression on both metrics. Both Run A comparisons with boosting include zero. B favors BG/NBD over boosting on AUC, while its AP interval includes zero; C favors BG/NBD on both. These exploratory intervals have no multiple-comparison adjustment.

## Business ranking

### Lift in the top 10%

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | 1.071 | 1.009 | 1.100 | 1.071 |
| baseline_recent | 1.796 | 1.639 | 1.965 | 1.796 |
| bgnbd | 2.110 | 1.861 | 2.547 | 2.110 |
| logreg | 2.110 | 1.881 | 2.512 | 2.119 |
| gboost | 2.132 | 1.869 | 2.518 | 2.132 |

### Revenue capture in the top 10%

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | 50.50% | 53.89% | 54.11% | 50.13% |
| baseline_recent | 53.42% | 57.44% | 58.35% | 53.48% |
| bgnbd | 57.84% | 58.99% | 62.86% | 57.76% |
| logreg | 57.05% | 54.28% | 61.46% | 56.93% |
| gboost | 57.45% | 58.14% | 60.96% | 57.29% |

### Revenue capture in the top 20%

| Model | A | B | C | A_no_cap |
| --- | --- | --- | --- | --- |
| baseline_const | 62.16% | 65.91% | 66.60% | 61.88% |
| baseline_recent | 66.11% | 68.50% | 68.45% | 66.10% |
| bgnbd | 72.74% | 73.45% | 77.02% | 72.63% |
| logreg | 72.28% | 72.90% | 76.10% | 72.05% |
| gboost | 72.43% | 73.51% | 76.35% | 72.28% |

Lift ranks by propensity; revenue capture ranks by expected_value_N. All models share Gamma-Gamma order values. Thus the constant-probability baseline still has a varying value ranking. Stable customer-ID tie-breaking is used at the selection boundary.

## Gamma-Gamma value errors

Errors are measured among customers who purchase in the label window. Buckets are repeat frequency at the test cutoff. The target is each customer’s actual mean daily purchase value, not total spend. WAPE divides the sum of absolute customer-mean errors by the sum of actual customer means.

| Run | Frequency | Buyers | MAE (GBP) | WAPE | Median APE |
| --- | --- | --- | --- | --- | --- |
| A | overall | 2286 | 198.47 | 42.53% | 32.34% |
| A | 0 | 344 | 224.59 | 58.96% | 54.03% |
| A | 1 | 291 | 166.70 | 47.39% | 44.71% |
| A | 2-3 | 459 | 160.81 | 41.87% | 34.98% |
| A | 4-7 | 524 | 190.21 | 38.38% | 28.21% |
| A | 8+ | 668 | 231.21 | 38.87% | 24.18% |
| B | overall | 2568 | 185.54 | 41.75% | 31.92% |
| B | 0 | 421 | 229.85 | 62.54% | 56.51% |
| B | 1 | 361 | 169.67 | 48.35% | 46.08% |
| B | 2-3 | 569 | 152.77 | 38.88% | 33.49% |
| B | 4-7 | 605 | 177.33 | 37.69% | 27.17% |
| B | 8+ | 612 | 203.03 | 35.32% | 21.74% |
| C | overall | 1698 | 186.70 | 43.92% | 33.98% |
| C | 0 | 229 | 215.32 | 68.27% | 68.93% |
| C | 1 | 203 | 165.56 | 51.92% | 52.00% |
| C | 2-3 | 351 | 191.87 | 47.25% | 39.88% |
| C | 4-7 | 433 | 187.56 | 42.93% | 30.55% |
| C | 8+ | 482 | 177.47 | 33.79% | 22.70% |
| A_no_cap | overall | 2286 | 191.39 | 41.01% | 32.19% |
| A_no_cap | 0 | 344 | 226.83 | 59.55% | 54.49% |
| A_no_cap | 1 | 291 | 166.21 | 47.25% | 44.34% |
| A_no_cap | 2-3 | 459 | 159.28 | 41.47% | 34.46% |
| A_no_cap | 4-7 | 524 | 186.21 | 37.57% | 28.39% |
| A_no_cap | 8+ | 668 | 210.24 | 35.34% | 23.85% |

These describe error differences across frequency groups, not the causal contribution of the frequency–monetary dependence. The independence diagnostic remains a limitation.

## Uncapped sensitivity

Every delta below is A_no_cap minus capped A. Negative log-loss/Brier deltas mean smaller errors; revenue deltas are percentage points. The database also holds 86 sensitivity differences, including count and value-bucket metrics.

| Model | Delta AUC | Delta AP | Delta log loss | Delta Brier | Delta lift | Delta revenue top 10% (pp) | Delta revenue top 20% (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_const | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | -0.3675 | -0.2726 |
| baseline_recent | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.0613 | -0.0052 |
| bgnbd | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | -0.0792 | -0.1089 |
| logreg | -0.000431 | -0.001949 | -0.004907 | -0.000056 | +0.008739 | -0.1219 | -0.2227 |
| gboost | +0.000102 | -0.000016 | -0.000234 | -0.000078 | +0.000000 | -0.1585 | -0.1513 |

Gamma-Gamma overall MAE changes from GBP 198.47 to 191.39; WAPE changes from 42.53% to 41.01%. BG/NBD probabilities and expected counts remain exactly unchanged, because their inputs are unaffected by value capping. Revenue capture changes through the order-value model.
Uncapping slightly improves some error metrics but reduces top-20% revenue capture for every model in this window. This is a sensitivity result, not a reason to retune the cap on test labels; the requested cap remains the primary specification.

## Fitted parameters, convergence and times

| Run | Cutoff | r | alpha (days) | a | b | Fit seconds | Start statuses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | train | 0.682733 | 66.621984 | 0.154590 | 3.315974 | 0.1649 | [0, 0, 0, 0] |
| A | test | 0.641845 | 63.638781 | 0.174016 | 2.738587 | 0.1567 | [0, 0, 0, 0] |
| B | train | 0.876815 | 72.336494 | 0.117648 | 63.912242 | 0.3229 | [0, 0, 0, 0] |
| B | test | 0.682733 | 66.621984 | 0.154590 | 3.315974 | 0.1693 | [0, 0, 0, 0] |
| C | train | 0.785091 | 72.278056 | 0.118864 | 11.926252 | 0.2580 | [0, 0, 0, 0] |
| C | test | 0.705037 | 68.755464 | 0.142328 | 3.468665 | 0.1885 | [0, 0, 0, 0] |
| A_no_cap | train | 0.682733 | 66.621984 | 0.154590 | 3.315974 | 0.1646 | [0, 0, 0, 0] |
| A_no_cap | test | 0.641845 | 63.638781 | 0.174016 | 2.738587 | 0.1571 | [0, 0, 0, 0] |

| Run | Cutoff | p | q | gamma (GBP) | Spearman rho | Fit seconds | Start statuses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | train | 2.328066 | 3.775141 | 471.493424 | 0.249681 | 0.0277 | [0, 0, 0, 0] |
| A | test | 2.171352 | 3.778588 | 497.887958 | 0.271010 | 0.0290 | [0, 0, 0, 0] |
| B | train | 2.169614 | 3.846903 | 542.429555 | 0.202210 | 0.0229 | [0, 0, 0, 0] |
| B | test | 2.331433 | 3.765129 | 469.414130 | 0.249713 | 0.0283 | [0, 0, 0, 0] |
| C | train | 2.158558 | 3.836310 | 538.547671 | 0.215967 | 0.0220 | [0, 0, 0, 0] |
| C | test | 2.241750 | 3.776257 | 495.700607 | 0.244795 | 0.0259 | [0, 0, 0, 0] |
| A_no_cap | train | 2.412137 | 3.555434 | 425.177376 | 0.250106 | 0.0266 | [0, 0, 0, 0] |
| A_no_cap | test | 2.243429 | 3.566540 | 451.350608 | 0.271415 | 0.0292 | [0, 0, 0, 0] |

All starts converged with status 0, all selected fits were away from numerical bounds, every fitted a is below one, and every q is above one. No singularity or non-finite prediction stop condition triggered. B’s training b is much larger than later estimates; parameter uncertainty and stability have not been quantified. Full optimizer attempts are stored in model_runs.params.

## Verification and runtime

| Run | Compute and persistence seconds |
| --- | --- |
| A | 4.376 |
| B | 4.214 |
| C | 4.356 |
| A_no_cap | 4.282 |

- Full four-run service wall time: **19.667 seconds** including Compose startup and Python imports; internal total: 18.609 seconds. Build and tests excluded. This is measured, below the ten-minute budget.
- Model suite: **17 passed in 48.61 seconds**, in the pinned Linux container. Each experiment was computed twice, compared exactly, saved twice, read back, and subjected to an intentional duplicate-insert failure with complete rollback verification.
- Paired-bootstrap unit tests check identical-score zero differences and independently calculated paired AP intervals; sensitivity tests check subtraction direction and bucket preservation.
- The fixed-seed recovery and fitted-low-a simulations passed again; no seed selection or tolerance changes were made.
- Independent saved-output checks verified all 101,265 prediction rows, 1,558 metric rows, calibration means, observed rates, calibration-bin totals, BG/NBD aggregates, paired point differences, all 86 sensitivity rows, and unchanged original Run A metrics.
- Default service entrypoint now runs all four experiments on one consistent input snapshot. `--run A`, `--run B`, and `--run C` select one; `--run A_no_cap` refreshes capped A first so sensitivity uses the same snapshot.
- Executed: `docker compose --env-file .env.example build model`, the complete model test suite in its image with development dependencies installed only in the temporary test container, and `docker compose --env-file .env.example run --rm --no-deps model`.
- Existing ETL code is unchanged; its 39 tests passed in milestone 2 and were not rerun in this milestone. Full methodology, README updates, and `docker compose --env-file .env.example up --build` remain milestone 4 work.
- Calibration summaries diagnose mean bias only; ten-bin tables provide more detail. No calibration correction, hybrid model, or budget-constrained selection was added. Expected values are not incremental retention effects.
