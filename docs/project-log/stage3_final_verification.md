# Stage 3 final verification

Completed on 2026-10-24. Runtime implementation is commit 20a9727; this milestone adds documentation and verification evidence without changing service behavior. Budget-constrained contact selection remains stage 4 work.

## Built and verified

- One-shot model service with cutoff-safe features, two baselines, BG/NBD, Gamma-Gamma value, standardized logistic regression and histogram gradient boosting.
- Three temporal runs and uncapped A sensitivity. Exactly three schema-qualified modeling tables; no persisted feature matrix. Source data remains in public.
- Calibration bins and mean bias, classification and business metrics, count/value errors, explainability, paired bootstrap differences and sensitivity deltas.
- Stable per-run replacement, exact repeatability checks, saved-output checks and complete transactional rollback tests.
- Methodology: 900 words approximately; print-preview checked at two A4 pages with 11-point body text and 18 mm side margins. README documents execution, reruns, SQL, metric interpretation, dependencies and tests.

## Full Compose verification

Executed the requested foreground command:

```sh
docker compose --env-file .env.example up --build
```

| Service | Final state | Health / exit | Container runtime |
| --- | --- | --- | --- |
| api | running | healthy | long-running |
| dashboard | running | healthy | long-running |
| etl | exited | exit 0 | 36.252 s |
| model | exited | exit 0 | 21.113 s |
| postgres | running | healthy | long-running |

- API /health returned HTTP 200 and {"status":"ok","database":"ok"}; dashboard returned HTTP 200.
- The ETL rebuilt the workbook tables before the model started. Source row counts remained: raw 1,067,371; clean 786,895; reversed 1,292; RFM customers 5,851. Feature/RFM reconciliation was exact.
- Model runtime from Docker start to exit was 21.113 seconds, including imports; its internal four-run total was 20.076 seconds. Image building, ETL and tests are excluded from the model-runtime budget. The ten-minute model budget passed.
- Model suite: **17 passed in 53.09 seconds**, in the pinned model container with temporary development dependencies. ETL suite: **39 passed in 1.37 seconds**. Tests include fixed-seed simulation recovery, four-run idempotence, saved-output equality, and full rollback after an intentional duplicate.
- Post-rebuild verification read 101,265 predictions and 1,558 metrics back from Postgres. Every metric and prediction aggregate matched milestone 3 exactly. No reserved test runs remained. The README SQL example executed successfully and returned 20 rows.
- PostgreSQL, API and dashboard remain running; ETL and model remain successfully exited. No push was made and no OpenAI API was called.

## Run A test comparison

Eligible customers: 5,254; positive customers: 2,286. Training base rate 32.06%; test base rate 43.51%. Revenue ranking uses probability times shared Gamma-Gamma value.

| Model | AUC | AP | Log loss | Brier | Lift top 10% | Revenue top 10% | Revenue top 20% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_const | 0.5000 | 0.4351 | 0.7133 | 0.2589 | 1.071 | 50.50% | 62.16% |
| baseline_recent | 0.7627 | 0.6859 | 0.6543 | 0.2177 | 1.796 | 53.42% | 66.11% |
| bgnbd | 0.8008 | 0.7745 | 0.5524 | 0.1862 | 2.110 | 57.84% | 72.74% |
| logreg | 0.7927 | 0.7680 | 0.5900 | 0.1982 | 2.110 | 57.05% | 72.28% |
| gboost | 0.7990 | 0.7751 | 0.5818 | 0.1952 | 2.132 | 57.45% | 72.43% |

Gamma-Gamma is a shared value model rather than another classifier. Its Run A order-value MAE is GBP 198.47, WAPE 42.53%, and median absolute percentage error 32.34%. Frequency-bucket errors and the three runs side by side appear in [the milestone 3 report](stage3_milestone3_results.md).

## Run A parameters and convergence

| Cutoff | BG/NBD (r, alpha, a, b) | Gamma-Gamma (p, q, gamma) | BG/NBD fit time | Gamma-Gamma fit time |
| --- | --- | --- | --- | --- |
| train | (0.682733, 66.621984, 0.154590, 3.315974) | (2.328066, 3.775141, 471.493424) | 0.1766 s | 0.0292 s |
| test | (0.641845, 63.638781, 0.174016, 2.738587) | (2.171352, 3.778588, 497.887958) | 0.1652 s | 0.0329 s |

- All four starts converged with status 0 for every fit in the full batch. All fitted a values were below one; all q values exceeded one. No singular/invalid-mean stop condition triggered.
- Run A Gamma-Gamma frequency–monetary Spearman correlation was 0.2497 at training and 0.2710 at test, challenging independence.
- Original 50,000-customer recovery parameter errors: BG/NBD 0.03%–0.86%, Gamma-Gamma 0.99%–1.81%; BG/NBD aggregate purchase/purchaser errors 0.33%/1.12%.
- At the exact fitted low-a test parameters, a fixed-seed 100,000-customer simulation recovered all parameters within 6.26%. Aggregate purchase/purchaser errors were 0.97%/0.29%, and 0.32%/0.74% among 37,476 zero-repeat customers. These checks passed again in the final suite; numerical integration separately verifies the finite-horizon expression below a=1.

## No-cap sensitivity

Deltas are A_no_cap minus capped A. BG/NBD probabilities and counts remain exactly unchanged; its expected values can change through Gamma-Gamma.

| Model | Delta AUC | Delta AP | Delta log loss | Delta Brier | Delta revenue top 20% (pp) |
| --- | --- | --- | --- | --- | --- |
| baseline_const | +0.000000 | +0.000000 | +0.000000 | +0.000000 | -0.2726 |
| baseline_recent | +0.000000 | +0.000000 | +0.000000 | +0.000000 | -0.0052 |
| bgnbd | +0.000000 | +0.000000 | +0.000000 | +0.000000 | -0.1089 |
| logreg | -0.000431 | -0.001949 | -0.004907 | -0.000056 | -0.2227 |
| gboost | +0.000102 | -0.000016 | -0.000234 | -0.000078 | -0.1513 |

- Gamma-Gamma MAE improves from GBP 198.47 to 191.39, and WAPE from 42.53% to 41.01%. Top-20% revenue capture decreases slightly for all models. The capped primary specification was retained; the test set did not select the cap.

## Limits and unverified claims

- Observed BG/NBD count bias is -23.95% in A, +14.21% in C and -2.69% in B. This pattern is consistent with seasonality or other population changes, but the experiments do not establish the cause.
- Correct simulation recovery does not validate real-world stationarity, daily aggregation of a continuous-time model, true acquisition dates or the Gamma-Gamma independence assumption. Zero-repeat customers have limited information.
- Bootstrap intervals condition on fitted models and do not quantify parameter-estimation uncertainty. Comparisons have no multiplicity correction, and test windows overlap across experiments.
- In Run A, paired intervals favor BG/NBD over logistic regression on AUC and AP. Both comparisons with boosting include zero; a clear BG/NBD advantage over boosting is not established there.
- This is historical backtesting on one retailer. Future deployment performance and incremental retention revenue are unverified. The API/dashboard remain placeholders; no hybrid classifier, contact selection or stage 4 optimization was added.
- Markdown has no intrinsic pagination. The two-page methodology limit was verified under the stated A4 preview settings; other renderers may paginate differently.
