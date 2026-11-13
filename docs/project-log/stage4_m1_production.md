# Stage 4 M1: production scoring

PROD shares the experiment fitting and prediction path; it does not evaluate an
unobserved future window. Training cutoff is 2011-09-10, with complete labels in
(2011-09-10, 2011-12-09]. Scoring cutoff is 2011-12-09, inclusive of that entire
day; the 90-day horizon is (2011-12-09, 2012-03-08].

The training-cutoff 99th-percentile customer-day purchase cap is GBP 3,766.0152.
It is frozen for scoring features. The two baselines and supervised models use
exactly Run A's training/tuning rules, with fresh training at the new cutoff.
BG/NBD and Gamma-Gamma are fitted separately at the training and scoring cutoffs.
All five propensity models share scoring-cutoff Gamma-Gamma expected order value.

## Saved results

Read back from Postgres after successful publication:

| Model | Eligible customers | Mean purchase probability | Mean order value (GBP) |
| --- | ---: | ---: | ---: |
| baseline_const | 5,851 | 0.43509707 | 390.829122 |
| baseline_recent | 5,851 | 0.45953911 | 390.829122 |
| bgnbd | 5,851 | 0.38176833 | 390.829122 |
| logreg | 5,851 | 0.46674712 | 390.829122 |
| gboost | 5,851 | 0.45338153 | 390.829122 |

Training customers: 5,254; training positive rate: 43.5097%. PROD has 29,255
prediction rows and 10 metric rows (customer count and mean probability per
model). Every actual_purchased, actual_purchases and actual_spend is NULL;
base_rate_test is NULL. Dates, fits, grids and package versions are in model_runs.
The nullable-column migration is idempotent; the same transactional replacement
and advisory lock used by historical runs protect PROD.

## Interpretation

The training label window includes the autumn/Christmas peak, while the scoring
horizon is off-peak. ML probabilities are therefore expected to be overestimated;
future outcomes are unavailable, so neither the magnitude nor the actual future
calibration is verified. No post-hoc probability adjustment was applied.
Expected order value concerns one customer-day purchase occasion. Probability
times that value is not total future spend; BG/NBD count times value allows
repeat purchases. Neither quantity estimates incremental retention impact.

## Verification

- Pinned Linux model-container suite: **21 passed in 59.77 s**, including the
  original 17 cases and four new PROD cases. Verified cutoff boundaries, complete
  training coverage, all-model future-data invariance, NULL outcomes, metric
  whitelist, exact rerun equality, saved-output equality and transactional rollback.
- Existing ETL suite: **39 passed in 0.67 s** in the local Python environment.
- Built the model image and ran `python main.py --run PROD` successfully.
- Complete historical metric and prediction hashes before and after matched:
  `04598d662434c62e47d08fd2d3f8f6fa` and
  `b8d6623b46afe8035bb884c132667dbb`, respectively. No Stage 3 result was rewritten.
- Full offline Compose startup remains the M5 verification; no such claim is
  made here. API and dashboard are still placeholders.
