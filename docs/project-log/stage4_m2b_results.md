# M2b: stronger comparisons and interactive latency

No new dependencies. The exact M2 solution is unchanged. Interactive requests use
one solve by default: `include_extra_100=false`, `interactive=true`. CP-SAT has a
0.5% relative-gap target and a 1.8-second total solve allowance. Status, actual
bound/gap and proof flag are always reported; its native OPTIMAL status at a
nonzero gap is relabeled FEASIBLE_GAP_TARGET. The exact Python default remains
available. API sensitivity will cap grids at 15 solves, use the same relaxed gap,
cache by the complete parameter set and preload the default grid at startup.

## PROD action economics (exact)

| Action | Customers | Cost (GBP) | Net value (GBP) |
| --- | ---: | ---: | ---: |
| none | 106 | 0.00 | 0.00 |
| email | 5,598 | 279.90 | 7,617.16 |
| coupon | 147 | 1,401.39 | 1,505.59 |

## Stronger baselines (exact PROD comparison)

| Baseline | Net value (GBP) | Optimizer improvement (GBP) |
| --- | ---: | ---: |
| naive | -1,673.69 | 10,796.43 |
| email_only | 7,997.77 | 1,124.98 |
| ratio_greedy | 9,122.00 | 0.74 |

The ratio greedy campaign is within GBP 0.74 of the exact optimizer. The large
naive-baseline improvement should not be interpreted as evidence that a complex
solver adds substantial business value over a sensible heuristic here.

Email-only sends email to every customer with positive raw email net value. It
is reported literally, with a feasibility flag if budget cannot fund all emails.
Ratio greedy starts from the best **budget-feasible** email assignment (uniform
email cost, highest net gain first), then upgrades emailed customers using the
requested raw incremental gain/cost ratio and conservative penny constraints.
Profitable zero/negative-cost upgrades go first; nonpositive-gain upgrades are
skipped. Ties use customer ID. Ratio greedy is always budget/K feasible.

## Run A: covering almost every customer

The contacted 5,183 / 5,254 customers (98.65%) account for **83.66%** of eligible
realized spend (GBP 2,347,028.30). This covers almost every customer; it is not a
selective-campaign success metric or a measured campaign effect.

| Group | Customers | Mean predicted pi | Observed purchase rate | Mean realized spend (GBP/customer) |
| --- | ---: | ---: | ---: | ---: |
| coupon | 144 | 5.42% | 9.72% | 37.83 |
| email_only | 5,039 | 34.95% | 43.70% | 464.69 |
| none | 71 | 97.79% | 98.59% | 6,458.21 |
| all_eligible | 5,254 | 34.99% | 43.51% | 533.99 |

These are descriptive comparisons of action groups selected under assumptions.
The coupon group is mostly low-propensity customers; its outcomes do not measure
treatment response. All-eligible is the same eligible-population denominator as
M2; new customers acquired after cutoff are excluded.

## Measured single-solve latency

Linux API image, `--network none`, six runs per dataset; full Python calculation
includes all baselines and summaries but excludes the optional GBP 100 solve:

| Run | Median (s) | Maximum (s) | Last actual gap |
| --- | ---: | ---: | ---: |
| A | 0.174 | 0.203 | 0.26774% |
| PROD | 0.557 | 0.561 | 0.00329% |

44 optimizer tests passed, including action totals, stronger baselines, budget
feasibility, grouped backtests and the optional interactive path. Actual HTTP
and sensitivity timings will be added after M3. Full evidence is in
[the M2b benchmark](stage4_m2b_benchmark.json).
