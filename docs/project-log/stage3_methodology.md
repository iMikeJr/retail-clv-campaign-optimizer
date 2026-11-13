# Stage 3 methodology

## Definitions and timeline

A purchase is one customer-day: filter eligible lines, sum invoices, then combine
invoices on the same calendar date, matching the ETL. Value sums `line_value` in
GBP. A customer is eligible after their first observed purchase. At inclusive
cutoff `c`, frequency `x` is purchases minus one; recency `t_x` is first-to-last
purchase days; `T` is first-purchase-to-cutoff days. Monetary value averages repeat
purchase values, excluding the entire first day; it is zero when `x=0`. Daily
values 30, 50, 70 give `x=2` and monetary value 60. Labels record any purchase,
purchase count and spend in `(c, c+N]`.

| Run | Training cutoff | Test cutoff | N (days) | Test-window end |
| --- | --- | --- | --- | --- |
| A | 2011-06-12 | 2011-09-10 | 90 | 2011-12-09 |
| B | 2010-12-14 | 2011-06-12 | 180 | 2011-12-09 |
| C | 2011-01-30 | 2011-04-30 | 90 | 2011-07-29 |

Training labels end at the test cutoff; test labels start strictly afterward.
Windows never overlap within an experiment. A_no_cap repeats A without capping.
Windows overlap across experiments, so these are not independent replications.

## Features and leakage controls

Features are frequency, recency, T, days since last purchase, monetary value,
mean and population-standard-deviation purchase gaps, purchase counts in the
last 90/180 days, total spend, last purchase value, distinct products and UK
status. Mean gap is recency/frequency, zero without repeats; standard deviation
is zero with fewer than two gaps. Trailing counts use `(c-days,c]`. UK status
uses the latest observed country; missing country gives zero.

`clean_transactions` already excludes quick reversals retrospectively. Historical
features restore `reversed_purchases` whose cancellation was not yet observed.
Labels use cleaning as observed at the window endpoint. Uncapped features must
reproduce stored ETL RFM for every customer before modeling; mismatches stop execution.

Cap daily purchases at the training-cutoff 99th percentile before computing
monetary value, total spend and last purchase value. Freeze this cap for test
features; labels remain uncapped. Tuning holds out 20% of training customers,
seed 42. Standardization uses development customers during tuning. Selected models
are refitted on all training rows. Probabilistic parameters are estimated
separately from histories at each cutoff, without test labels or future transactions.

## Models

**baseline_const** predicts the training positive rate, testing whether a model
adds useful discrimination beyond training prevalence.

**baseline_recent** ranks by minus days since last purchase. A monotone sigmoid
fitted on training labels supplies probabilities for calibration and value.

**bgnbd** combines heterogeneous purchase rates with dropout after purchases.
NumPy/SciPy maximum likelihood uses log parameters and four starting points;
every convergence status is recorded. Outputs are probability alive, expected
counts and probability of any purchase. Integrating the alive-conditioned Gamma
purchase rate gives `p_alive * [1-((alpha+T)/(alpha+T+N))^(r+x)]`.
Finite-horizon counts can be valid at `a<1` ([derivation correction](https://www.brucehardie.com/notes/041/));
the code stops near the singular `a=1` expression or invalid counts, without clipping.

**gamma_gamma** uses the same likelihood strategy on customers with positive
frequency and monetary value. It shrinks individual order values toward the
population mean, like giving a short history less weight. Zero-repeat customers
receive that mean. An undefined mean (`q<=1`) stops execution. Spearman
frequency–monetary correlation diagnoses its independence assumption.

**logreg** standardizes features and uses L2 regularization. Validation log loss
selects C from 0.01, 0.1, 1 and 10; test labels never select C.

**gboost** uses HistGradientBoostingClassifier: depths 2/3/4, rates 0.03/0.1,
400 maximum iterations and minimum leaf size 50. Development-only early stopping
selects an iteration count; refitting uses all training rows at that count.
No hybrid BG/NBD classifier is fitted.

Every propensity shares Gamma-Gamma order value. `expected_value_N` is purchase
probability times order value; BG/NBD additionally stores expected counts times
order value as `bgnbd_clv_N`. The former values one purchase occasion; the latter
allows repeats. Neither estimates incremental revenue from contacting someone.

## Reading evidence and limitations

AUC measures ranking; average precision measures positive-customer retrieval
and depends on prevalence. Lower log loss and Brier indicate better probability
predictions. Compare mean probability with observed rate and ten quantile bins
for calibration. Lift compares the top decile's purchase rate with the base rate;
revenue capture is realized spend from the top 10%/20% by expected value.
BG/NBD totals and customer MAE assess volume error. Order-value MAE is in GBP;
WAPE aggregates absolute errors relative to actual customer means; median absolute
percentage error describes the typical relative miss. MAPE is not used.

All runs use 200 customer-bootstrap resamples for AUC/AP intervals and paired
BG/NBD differences. These condition on fitted models, without multiplicity
adjustment. Permutation importance measures test AUC loss over ten repeats;
standardized logistic coefficients describe conditional associations, not causes.

Count bias is approximately -24% in A, +14% in C and -2.7% in B. This changing
bias is consistent with seasonality or other population changes; these runs do
not establish seasonality as its cause. Continuous-time BG/NBD approximates daily
observations; first observed purchases may not be true acquisitions. Single-purchase
customers have limited history; BG/NBD assigns them probability alive one, while
their purchase probability can still be low. Positive frequency–monetary correlation challenges
Gamma-Gamma independence. Capping suppresses extremes such as customer 15749;
uncapped sensitivity shows its effect without choosing the cap on test results.

PyMC-Marketing 0.19.4 with pandas 3.1.0, PyMC 5.28.5 and Pydantic 2.14.1 installed, but import failed: Pydantic SchemaError, 'cls' must be valid as the first argument to 'isinstance'.
Container build: 46.80 s; probe failed during import after 1.98 s, before either fit. NumPy/SciPy maximum likelihood was explicitly selected instead; dependency pins were not investigated.
