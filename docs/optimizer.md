# Campaign optimizer

This is a scenario calculator, not an estimated treatment-effect model. **tau and
margin are assumptions, not estimated from data; an A/B test would estimate tau.**
All monetary amounts are GBP. The retailer has no randomized campaign experiment.
The optimizer values one purchase occasion over the chosen forecast horizon,
not all future repeat spending or an empirically established retention effect.

## Definitions and objective

Customers are i; actions a are in {0 none, e email, c coupon}. pi_i is the
probability of any purchase; v_i is Gamma-Gamma expected order value (in this
project, one customer-day purchase occasion). Assumptions are m (margin), tau_a
(the share of customers who would NOT buy that action a converts), f_e and f_c
(fixed costs), d (discount), B (budget), and K (maximum coupons).

The exact scenario equations are:

```text
Delta_pi_ia = tau_a * (1 - pi_i);   R_ia = m * v_i * Delta_pi_ia
c_i0 = 0;  c_ie = f_e;  c_ic = f_c + d * v_i * (pi_i + Delta_pi_ic)
g_ia = R_ia - c_ia   (g_i0 = 0)
```

With binary x_ia, solve the multiple-choice knapsack:

```text
maximize sum_i sum_a g_ia x_ia
subject to sum_a x_ia = 1                    for every i
           sum_i sum_a c_ia x_ia <= B
           sum_i x_ic <= K
           x_ia in {0,1}
```

Implementation uses email/coupon Boolean variables with their sum <= 1; none is
implicitly one minus that sum. This is equivalent to the three-action equality.
Coupon cost includes discount redemption by customers who would buy anyway,
which can make coupons to high-probability customers unprofitable. For example,
with pi=0.9 and v=400, default coupon incremental margin is only GBP 1.80 while
expected cost is GBP 37.60. High expected purchase value alone is not a good
criterion for incremental campaign value under these assumptions.

## Defaults and numerical policy

| Input | Default | Valid range |
| --- | ---: | --- |
| m | 0.30 | [0,1] |
| tau_e | 0.02 | [0,1] |
| tau_c | 0.15 | [0,1] |
| f_e | 0.05 | [0,1000000] GBP |
| f_c | 1.00 | [0,1000000] GBP |
| d | 0.10 | [0,1] |
| B | 1682 | [0,1000000000] GBP |
| K | 300 | integer [0,1000000] |

All are editable assumptions, including the budget and coupon capacity. The
frozen default model/run are bgnbd/PROD. The best integer campaign without a
budget constraint, still respecting K=300, costs GBP 3,364.48 conservatively.
Half, rounded down to whole pounds, gives **B=GBP 1,682**. This is a moderate
resource restriction relative to the same scenario's unconstrained campaign;
it nearly exhausts budget and an extra GBP 100 increases value. It is not an
estimated optimal business budget. The fixed email cost and assumed conversion
make email profitable for most customers, explaining the very broad selection.

Costs scale with `ceil(cost * 100 - 1e-9)`; the tiny tolerance keeps an exact
GBP 10.40 from becoming GBP 10.41 through floating noise. Budget scales downward
with `floor(B * 100 + 1e-9)`. Gains scale to nearest penny, with half-penny ties
away from zero. Baseline and optimizer use the same conservative costs.

Results include raw expected GBP totals, scaled totals and their discrepancies.
Feasibility is conservative for raw costs, up to the stated floating tolerance.
**Optimality and monotonicity guarantees refer to the integer-pence objective.**
This is an approximation to optimizing unrounded expectations: total gain
rounding error is at most half a penny per selected customer, and each action's
cost is conservatively increased by less than a penny. Raw gain differences can
be slightly negative between integer-tied campaigns; raw and scaled values are
kept separate throughout.

## Solver and returned evidence

OR-Tools 9.15.6755 installed and solved successfully under Python 3.12 with pinned
pandas 3.1.0, on macOS and in the Linux API image. The initial compatibility check
completed within the ten-minute limit. No SciPy fallback was needed.

The integer solver is **CP-SAT**, with one worker, seed 42 and a five-second
solve allowance including preprocessing time (small return/cleanup overhead can
extend measured wall time). OR-Tools GLOP first solves the LP relaxation, capped
at one second. Think of this relaxation as allowing a customer to receive a
fraction of a coupon: it can only improve the objective and supplies an upper
bound. A feasible rounded campaign supplies a lower bound. Reduced costs remove
choices that cannot bridge the gap. Budget/coupon dual multipliers are converted
to nonnegative integers at scale 10^9; customer multipliers and the bound are
rebuilt using exact integer arithmetic. Thus floating-point reduced-cost errors
cannot delete a better integer solution. If the LP is not solved optimally, its
fixing information is discarded.
Exact mode uses CP-SAT for integer search. A fractional LP solution is never
reported as a campaign; only a feasible assignment is returned. A matching
integer dual upper bound can itself certify that assignment as optimal.

Status, incumbent objective, upper bound, relative gap, LP bound, variable count
and elapsed seconds are returned. Relative gap is `(bound-value)/max(1,abs(value))`
in pence. The `optimality_proven` flag identifies proven optimality. A time-limited
feasible result keeps its actual gap; an UNKNOWN result returns the validated
feasible hint with an explicit status and a global bound from the integer dual
certificate (or the unconstrained per-customer bound if no LP certificate exists).
`cp_sat_bound_pence` remains NULL if CP-SAT supplied no search bound. Invalid/infeasible models raise
an error instead of being presented as successful campaigns.

Input sorting, seed and worker settings are fixed. Repeated deployment-image
solves returned identical assignments. Different platforms can choose different
integer-tied optima; published counts and results use the pinned Linux image.
No claim of identical assignments across platforms or wall-clock-interrupted
searches is made.

The requested baseline sorts by pi_i*v_i descending, with customer ID breaking
ties, and gives coupons whenever remaining budget and K permit. It continues
past unaffordable customers; everyone else receives none. It deliberately does
not filter unprofitable coupons. Improvement is optimizer raw net value minus
baseline raw net value. Percentage improvement is NULL when baseline value is
nonpositive, since a percentage comparison would be misleading.

ROI is raw net value / raw cost (NULL at zero cost). The extra-GBP-100 result
re-solves at B+100, using the original campaign as a feasible incumbent; it
reports the finite change in value and both solver statuses, not a derivative
or a guaranteed return from spending GBP 100 in reality.

Break-even tau is customer-specific, not one common threshold:

```text
tau_e* = f_e / (m * v_i * (1 - pi_i))
tau_c* = (f_c + d * v_i * pi_i) / ((m - d) * v_i * (1 - pi_i))
```

These set g_ia=0 before penny rounding. A zero cost intercept means zero is
already break-even. A positive intercept with nonpositive slope has no finite
threshold. Thresholds above one are returned as unattainable. Each assignment
includes both thresholds and attainability flags; the response also includes
all assignments and the 15 highest-net-value contacted customers.

When actual_spend exists for every customer, the backtest sums uncapped realized
spend for contacted customers, counting a customer once, and divides by total
realized spend among **eligible scored customers**. The denominator excludes
new customers who were not eligible at cutoff. Its label is **“What was at stake,
not campaign effect.”** Outcomes never enter the objective. PROD has no outcomes
and returns NULL for this backtest; partial outcomes are rejected.

## Python interface and reproduction

`Customer(customer_id, pi, v, actual_spend=None)` and `Assumptions(...)` are
immutable inputs to `optimize(customers, B, K=300, assumptions=None)`. The optimizer
module imports no web/database libraries and makes no network calls. It validates
probabilities in [0,1], positive finite values up to GBP 1 billion, unique IDs,
nonnegative realized spend and the ranges above.

Run the optimizer suite in a disposable API container:

```sh
docker compose --env-file .env.example build api
docker compose --env-file .env.example run --rm --no-deps \
  -v "$PWD/services/api/tests:/app/tests:ro" \
  -v "$PWD/services/api/requirements-dev.txt:/tmp/requirements-dev.txt:ro" \
  api sh -c 'pip install --quiet -r /tmp/requirements-dev.txt && python -m pytest tests -q -o cache_dir=/tmp/api-pytest-cache'
```

The development install requires network or cached packages during preparation;
pytest is not installed in the runtime image. Runtime dependencies are pinned.
The read-only benchmark uses the standard database environment and parameterized
SQL, or accepts a JSON fixture for completely network-disabled execution:

```sh
docker compose --env-file .env.example run --rm --no-deps \
  -v "$PWD/docs/project-log:/evidence" api python benchmark_optimizer.py \
  --output /evidence/stage4_m2_benchmark.json
```

The suite covers the exact three-customer example (GBP 10.50 cost, GBP 7.17 net;
all-email GBP 3.48), 24 fixed-seed exhaustive enumerations up to 3^8 assignments,
exact dual-bound checks at ordinary and large currency scales, constraints,
budget monotonicity, deterministic ordering, free actions, zero
resources, break-even edge cases, missing outcomes and invalid inputs.
Saved measured results and limitations: [optimizer results report](project-log/stage4_m2_results.md) and
[benchmark evidence](project-log/stage4_m2_benchmark.json).

## Interactive interface and comparisons

See [baseline and backtest results](project-log/stage4_m2b_results.md) for action economics, stronger baselines,
grouped backtests and measured one-solve timings. `optimize` now accepts keyword
flags `include_extra_100` and `interactive`; the API defaults to false and
true respectively. Existing exact Python calls retain their behavior. Results
add `by_action`, `baselines` and backtest `groups`; the legacy `baseline` alias
still denotes the naive highest-expected-value coupon campaign.

## API latency and cache

The [API latency report](project-log/stage4_m3_results.md) documents endpoints, the optional
extra-budget flag, 0.5% interactive gap, 15-point sensitivity limit and measured
HTTP latency. Each typed request keys a bounded in-memory cache tied to the
immutable startup snapshot; restart the API after a model rerun to refresh it.
The default grid is precomputed before the API serves requests.


## Certified-gap fast path

Interactive mode now checks the feasible incumbent against the exact integer
LP-derived upper bound **before** starting CP-SAT. For feasible value L and
certified upper bound U, `L <= optimum <= U`; if `(U-L)/max(1,abs(L)) <= 0.005`,
no integer search is needed to meet the interactive target. For example, a
GBP 9,122.66 integer objective under a GBP 9,122.96 bound has only 30 pence of
unresolved value. The response identifies `NOT_RUN_CERTIFIED_GAP` and the
OR-Tools GLOP certificate rather than claiming CP-SAT ran. A zero certificate
gap is `OPTIMAL_BOUND_CERTIFICATE`; otherwise it is `FEASIBLE_GAP_TARGET`.

If the certificate is insufficient, CP-SAT uses the remaining 1.8-second
interactive allowance and returns its actual status and best available bound.
The reported bound is the tighter of the integer dual certificate and the
CP-SAT bound. Target failure is visible; no time-limited result is relabeled as
meeting the target. Exact mode still uses CP-SAT with the five-second allowance.
Ratio greedy is also considered as a feasible incumbent, so the solver starts
from the stronger of its available penny-valued heuristic campaigns.

The API omits the full assignment vector to keep interactive responses small;
it returns the top 15 selected customers with their break-even thresholds, all
action economics, baselines and grouped backtest. The pure Python interface
still returns every customer assignment and threshold. Final latency and browser
evidence: [latency and browser report](project-log/stage4_m4_results.md).

## Selected-customer order-value check

For Run A, each action group reports mean predicted v over the whole group,
mean predicted v among its buyers, and realized order value as the unweighted
mean of each buyer's actual_spend / actual_purchases, matching the model evaluation (not
pooled spend divided by all orders, and not mean customer spend).
Optimizing for high predicted value can select customers with overestimated
order values, so whole-group predictions and buyer-only outcomes are not
directly comparable; use the same-buyer prediction comparison when assessing
overestimation, and remember that nonbuyers' realized order values are unobserved.
For each action, the model assumes the same offer-response parameter tau for
dormant customers (pi close to 0) as for other customers.

The highest-value table renders all returned rows (up to 15), without a fixed
height clipping the final rows; its label reflects the number actually returned.
Clean full-stack and offline startup checks are recorded in [final verification](project-log/stage5_final_verification.md).
The selected-customer display now adds recency and stored expected 90-day spend
from the customer endpoint; optimizer inputs, equations and results are unchanged.
