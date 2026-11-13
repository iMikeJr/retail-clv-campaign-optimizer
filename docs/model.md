# Predictive model

The model service builds cutoff-safe customer features from the ETL tables, fits
BG/NBD and Gamma-Gamma (NumPy/SciPy maximum likelihood) alongside logistic
regression, gradient boosting and two simple baselines, evaluates them on
three temporal backtests, and scores every customer at the latest cutoff
(PROD) for the campaign optimizer.

Production scoring runs as `--run PROD` and is part of the default model batch.
See the [production scoring report](project-log/stage4_m1_production.md) for the
2011-12-09 scores, dates, NULL outcomes and seasonal limitations. Historical
experiments keep their own definitions and outputs.

The [methodology](project-log/stage3_methodology.md) explains definitions, timeline,
leakage controls, models, metrics and limitations. The
[verified comparison report](project-log/stage3_milestone3_results.md) contains all runs,
calibration, paired bootstrap intervals, fitted parameters and sensitivity results.
The [final verification record](project-log/stage3_final_verification.md) records the full
Compose startup, tests, health checks and saved-output reconciliation.

## Temporal experiments

| Run | Test cutoff | Window | Training cutoff |
| --- | --- | ---: | --- |
| A | 2011-09-10 | 90 days | 2011-06-12 |
| B | 2011-06-12 | 180 days | 2010-12-14 |
| C | 2011-04-30 | 90 days | 2011-01-30 |
| A_no_cap | Same as A | 90 days | Same as A |

Once the ETL has completed, rerun the model without repeating it:

```sh
docker compose run --rm --no-deps model
docker compose run --rm --no-deps model python main.py --run B
docker compose run --rm --no-deps model python main.py --reconcile-only
```

`--run A`, `B`, or `C` selects one experiment. `--run A_no_cap` refreshes capped A
first, ensuring sensitivity uses the same input snapshot. `--run PROD` selects
production scoring. The default is all five runs.
Run the ETL first after changing source data or reversal settings. Changes to
`CUTOFF_DATE` affect the ETL reconciliation cutoff, not the model experiment dates.

Use `docker compose --env-file .env.example ...` for the sample-configuration
verification environment. This uses example credentials; `.env` remains private.
The full verification command is `docker compose --env-file .env.example up --build`.

## Output tables

The source schema (`public`) and model schema (`modeling`) are separate constants
in `services/model/db.py`. The model creates exactly three tables:

| Table | Contents |
| --- | --- |
| `modeling.model_runs` | Stable run ID, cutoffs, window, customer counts, train/test base rates, seed, timestamp and JSONB settings, package versions, fitted parameters and optimizer diagnostics. |
| `modeling.model_metrics` | Long-format classification, calibration, ranking, count/value error, coefficients, permutation importance, bootstrap intervals and uncapped-minus-capped differences. |
| `modeling.customer_predictions` | Five propensity models per eligible test customer, shared Gamma-Gamma order value, realized labels/counts/spend, and BG/NBD-only alive probability, expected counts and CLV. |

Features are reproduced from source tables and are never persisted. Historical
inputs combine `public.clean_transactions` with purchases from
`public.reversed_purchases` whose cancellation was not yet observed. Cleaned
transactions alone would leak retrospective reversal decisions into old features.

`expected_value_N` is probability times expected order value. `bgnbd_clv_N` is
expected purchase count times expected order value. They are different measures;
neither is a causal estimate of contacting a customer. Gamma-Gamma is evaluated
as a value model rather than stored as another propensity classifier. BG/NBD-only
prediction columns are NULL for other classifiers. Columns containing `_N` use
that exact mixed case and must be quoted in SQL:

```sql
SELECT r.run_name, p.model, p.customer_id, p."p_purchase_N",
       p.expected_order_value, p."expected_value_N", p."bgnbd_clv_N"
FROM modeling.customer_predictions AS p
JOIN modeling.model_runs AS r USING (run_id)
WHERE r.run_name = 'A' AND p.model = 'bgnbd'
ORDER BY p."expected_value_N" DESC, p.customer_id
LIMIT 20;
```

Metric segments are `overall`, frequency buckets, calibration-bin numbers,
feature names, `train`/`test`, or `vs_logreg`/`vs_gboost`. Calibration metrics
`mean_predicted_probability`, `observed_positive_rate` and `calibration_gap` use
prediction minus observation for the signed gap. Paired differences are BG/NBD
minus comparator; sensitivity metrics ending `_difference_vs_capped` are uncapped
minus capped. WAPE and capture values are fractions, not percentage points.
Constant predictions form one calibration bin; other ties may reduce the bin count.

A run is fully computed before its existing rows are deleted and rewritten inside
one transaction. A failed replacement preserves the prior committed run; earlier
successful runs in the batch remain committed. Reruns preserve metrics and
predictions with identical inputs and seed; timestamps and fit times can change.
Undefined Gamma-Gamma means, singular/invalid BG/NBD outputs, and ETL mismatches
stop the service without silently clipping model parameters.

## Verified results

Verified results: A has 5,254 eligible customers/2,286 positives; C has
4,795/1,698. All four runs produce 101,265 prediction rows and 1,558 metric rows.
The experiment batch took 19.67 seconds including startup, excluding image
building and tests. BG/NBD count bias changes from approximately -24% in A to
+14% in C and -2.7% in B. This is consistent with seasonality or other changes;
the experiments do not establish the cause. Parameter recovery and forecast
accuracy are distinct checks.

Final full-stack verification reran the workbook ETL and all four experiments:
ETL/model exited `0`; PostgreSQL/API/dashboard were healthy; both HTTP checks
passed. The model container took 21.11 seconds from start to exit. All 1,558
metrics and prediction aggregates matched the recorded experiment results exactly.

## Dependencies and tests

NumPy/SciPy implement BG/NBD and Gamma-Gamma by maximum likelihood with four
log-parameter starts and per-start convergence diagnostics. No PyMC, lifetimes or
external boosting library is used. Runtime dependencies are pinned;
pytest belongs only to the separate development lock:

```sh
uv pip compile services/model/requirements.in --python-version 3.12 --no-header --no-annotate --output-file services/model/requirements.txt
uv pip compile services/model/requirements-dev.in --python-version 3.12 --no-header --no-annotate --output-file services/model/requirements-dev.txt
uv pip install --python .venv/bin/python -r services/model/requirements-dev.txt
.venv/bin/python -m pytest services/model/tests -q
```

Without Postgres environment variables, the four database integration cases skip.
For the complete suite, after building the model and running the ETL:

```sh
docker compose run --rm --no-deps \
  -v "$PWD/services/model/tests:/app/tests:ro" \
  -v "$PWD/services/model/requirements-dev.txt:/tmp/model-requirements-dev.txt:ro" \
  model sh -c 'pip install --quiet --disable-pip-version-check -r /tmp/model-requirements-dev.txt && python -m pytest tests -q -x -o cache_dir=/tmp/model-pytest-cache'
```

Development dependencies are installed in this temporary container only. The 17
tests include cutoff boundaries, future-data invariance, fixed-seed simulation
recovery, low-a and zero-repeat validation, paired differences, bucket metrics,
and per-run idempotence, saved-output equality and rollback. Integration cases
replace and clean up reserved `__stage3_pytest__:*` runs; public data is read-only.
