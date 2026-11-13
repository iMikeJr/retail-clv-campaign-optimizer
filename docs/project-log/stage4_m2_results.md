# Stage 4 M2: optimizer results and mandatory stop

M1 and M2 are complete. Stop before API endpoints (M3). No push was made.
These results use PROD/bgnbd and Run A/bgnbd read from saved Postgres predictions,
with B=GBP 1,682, K=300 and the documented default assumptions. They are scenario
expectations for one purchase occasion, not measured campaign effects.

## Saved Linux-image solutions

| Quantity | PROD | Run A |
| --- | ---: | ---: |
| Eligible customers | 5,851 | 5,254 |
| None | 106 | 71 |
| Email | 5,598 | 5,039 |
| Coupon | 147 | 144 |
| Raw expected cost (GBP) | 1,681.29 | 1,681.27 |
| Conservative cost (GBP) | 1,681.99 | 1,681.97 |
| Raw expected net value (GBP) | 9,122.74 | 8,612.63 |
| Integer objective (GBP) | 9,122.86 | 8,612.72 |
| ROI (net / cost) | 5.4260 | 5.1227 |
| Baseline raw net value (GBP) | -1,673.69 | -1,654.60 |
| Improvement over baseline (GBP) | 10,796.43 | 10,267.23 |
| Extra GBP 100: additional raw net value (GBP) | 55.20 | 51.52 |

All base and B+100 solves proved **OPTIMAL**, with **zero integer optimality gap**.
Percent improvement over the baseline is undefined because baseline net value
is negative. The requested baseline buys only eight coupons, targeting expensive
customers who are already very likely to buy. The no-contact alternative has
zero cost and zero incremental value. Baseline losses are not observed losses;
they follow from the same scenario equations as the optimized values.

The default is half the GBP 3,364.48 conservative cost of the no-budget optimum,
rounded down to GBP 1,682. The conservative PROD spend is GBP 1,681.99, leaving
one penny. The extra-budget value confirms budget is economically restrictive.
K is an upper limit, so exhausting coupons is not required. The six repeated
solutions had identical assignments within the pinned deployment environment.
Across platforms, tied integer optima can have slightly different assignments;
these published numbers use Linux, not the exploratory macOS run.

## Run A: what was at stake, not campaign effect

The optimizer's contacted customers had **GBP 2,347,028.30**
realized spend in (2011-09-10, 2011-12-09], **83.66%** of the
**GBP 2,805,561.26** realized spend among all eligible
scored customers. The coupon-only baseline selected customers with
GBP 436,816.05, or 15.57% of the same denominator.

These totals describe actual purchases without the proposed campaign. They are
not incremental retention value, campaign revenue, or evidence that contacting
these customers would change their behavior. New customers in the window are
outside the eligible-population denominator. PROD has no realized outcomes.

## Verification and timings

- OR-Tools **9.15.6755**, pandas **3.1.0**, Python **3.12.12** in the Linux image.
  Installation, import and a small solve succeeded within the ten-minute check;
  SciPy fallback was unnecessary. CP-SAT is the integer solver, aided by a GLOP
  relaxation and an exact-integer dual certificate for safe variable fixing.
- Final Linux optimizer suite: **42 passed in 0.26 s**. Includes the exact
  three-customer result (cost GBP 10.50, net GBP 7.17, all-email GBP 3.48), random
  exhaustive enumeration through eight customers, exact bound checks including
  large currency scales, constraints, budget monotonicity, determinism, edge
  cases and input validation.
- M1 verification remains **21 model tests passed** (including original 17) and
  **39 ETL tests passed**. No model/ETL implementation changed in M2.
- Final benchmarks ran with Docker **`--network none`**, using read-only exported
  prediction fixtures. Each dataset ran in a fresh Python process: one first
  solve plus five warm repeats. Imports and data loading are excluded. All 24
  integer solves (base and extra-budget) were OPTIMAL. Individual solves met the
  under-three-second target; a full campaign calculation contains two solves.

| Run | First base solve (s) | Warm median base solve (s) | Slowest individual solve (s) | Warm median full calculation (s) |
| --- | ---: | ---: | ---: | ---: |
| PROD | 1.850 | 1.817 | 1.850 | 3.081 |
| A | 0.099 | 0.097 | 0.123 | 0.234 |

The full calculation includes baseline, both solves, assignment summaries and
break-even thresholds. Timings are local measurements, not a deployment SLA.
Complete status, bounds, timings, top selected customers and scenario outputs
are in [the benchmark evidence](stage4_m2_benchmark.json).

## Delivery and limits

- Pure Python optimizer, immutable input types, structured results, pinned runtime
  and development dependency locks, read-only benchmark command and equations in
  [optimizer documentation](../optimizer.md). API image includes these modules;
  the server retains only its original health endpoint until M3.
- Historical metrics and prediction hashes still match the pre-M1 snapshot:
  `04598d662434c62e47d08fd2d3f8f6fa` and
  `b8d6623b46afe8035bb884c132667dbb`. Only A, B, C, A_no_cap and PROD runs remain;
  integration-test reserved runs were cleaned up.
- All parameters are assumptions. Broad email selection and high scenario ROI
  follow from those assumptions. Seasonal probability calibration, actual
  conversion response and campaign profitability remain unverified.
- Integer-pence optimality is distinct from exact optimization of unrounded
  expectations; raw and scaled totals are both reported. Only repeatability in
  the pinned environment is verified; tied optima need not match across platforms.
- **Not built or verified yet:** M3 API endpoints/HTTP latency, M4 dashboard and
  screenshots, M5 clean full-stack/offline Compose startup. No OpenAI API was called.
