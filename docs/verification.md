# Verification and results

This page collects the measured results and how they were checked. Every number
below is copied from the linked report in the [project log](project-log/README.md),
which also holds the raw JSON evidence. Nothing here is re-rounded.

## Running the tests

```sh
make venv   # one-off: local virtual environments from the pinned dev locks (needs uv)
make test   # ETL, model and API unit tests
make lint   # Compose config validation and Python byte-compilation
```

Without `POSTGRES_*` variables, the model's database integration cases skip.
The CI workflow ([tests.yml](../.github/workflows/tests.yml)) runs the ETL and
model unit tests on Python 3.12 with the pinned `requirements-dev.txt` files.
The full suites, including real-Postgres model integration, run inside the
service images; the commands are in [model.md](model.md#dependencies-and-tests)
and [optimizer.md](optimizer.md).

Last recorded full run, in the pinned Linux service images:
**180 passed, no skips** (API/executive/optimizer 120, ETL 39, model including
Postgres integration 21). Source:
[views verification report](project-log/stage5_phase2_results.md). Tests have
been added in later commits.

## Data and ETL

| Result | Value | Source |
| --- | --- | --- |
| Raw source lines loaded | 1,067,371 (525,461 + 541,910) | [etl.md](etl.md#source-and-tables) |
| Customers in RFM at 2011-12-09 | 5,851 | [etl.md](etl.md#verified-default-window-results) |
| Quick-reversal purchase lines removed (24 h window) | 1,292 lines, GBP 391,167.69 | [etl.md](etl.md#verified-default-window-results) |

## Propensity models (temporal backtests)

Runs A, B and C use different training/test cutoffs and windows (see
[model.md](model.md#temporal-experiments)). Their windows overlap, so they are
not independent replications.

| Model | ROC AUC A | ROC AUC B | ROC AUC C | Log loss A | Log loss B | Log loss C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_recent | 0.7627 | 0.7697 | 0.7645 | 0.6543 | 0.6567 | 0.5597 |
| logreg | 0.7927 | 0.7966 | 0.8062 | 0.5900 | 0.5641 | 0.5071 |
| gboost | 0.7990 | 0.8033 | 0.8061 | 0.5818 | 0.5616 | 0.5065 |
| **bgnbd** | **0.8008** | **0.8112** | **0.8127** | **0.5524** | **0.5269** | **0.4979** |

BG/NBD has the lowest log loss and Brier score in all three temporal runs.
Source: [temporal experiments report](project-log/stage3_milestone3_results.md).

BG/NBD aggregate purchase-count error is **-23.95%** (A), **-2.69%** (B) and
**+14.21%** (C): good ranking does not guarantee correct aggregate counts, and
the sign changes between windows. Source: same report.

## Campaign optimizer

| Result (PROD, budget GBP 1,682, at most 300 coupons) | Value | Source |
| --- | --- | --- |
| Raw expected net value, exact solve | GBP 9,122.74 | [optimizer results](project-log/stage4_m2_results.md) |
| ROI (net / cost), exact solve | 5.4260 | [optimizer results](project-log/stage4_m2_results.md) |
| Actions: none / email / coupon | 106 / 5,598 / 147 | [optimizer results](project-log/stage4_m2_results.md) |
| Raw expected net value, interactive default | GBP 9,122.55 | [latency and browser report](project-log/stage4_m4_results.md) |
| Interactive certified optimality gap | 0.003289% | [latency and browser report](project-log/stage4_m4_results.md) |
| Improvement over ratio-greedy heuristic (interactive plan) | GBP 0.55 | [presentation report](project-log/stage5_polish_fix.md) |

All values are scenario outputs under assumed offer responses, margin and costs,
not estimated campaign effects. The tiny gain over ratio greedy is the honest
comparison; the much larger gain over the naive baseline is not.

## Performance and startup

- All measured read requests stay below 300 ms, and all ten sampled uncached
  interactive solves stay below 1 second.
  Source: [views verification report](project-log/stage5_phase2_results.md).
- A clean online build and a network-isolated startup from prepared images both
  reached healthy services with unchanged outputs.
  Source: [startup verification](project-log/stage5_final_verification.md).
