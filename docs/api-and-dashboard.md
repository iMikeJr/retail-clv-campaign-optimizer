# API and dashboard

A FastAPI service serves model outputs, executive metrics and an interactive
campaign optimizer from a read-only startup snapshot; a static HTML/CSS/vanilla
JS dashboard consumes it. Metric definitions are in
[dashboard_metrics.md](dashboard_metrics.md); optimizer equations are in
[optimizer.md](optimizer.md).

## Campaign optimizer

The API hosts a pure Python [campaign optimizer](../services/api/optimizer.py),
with [equations and assumptions](optimizer.md), [measured results](project-log/stage4_m2_results.md)
and [benchmark evidence](project-log/stage4_m2_benchmark.json). At the default GBP 1,682
budget and 300-coupon limit, the pinned Linux PROD/bgnbd solution has GBP 9,122.74
raw expected net value. This is an assumption-driven incremental value for one
purchase occasion, not an estimated campaign effect or total future spend.
The dashboard is an executive view with technical evidence collapsed at the
bottom; see the [overview screenshot](screenshots/dashboard-overview.png).
Offline startup uses prepared images; the [final verification](project-log/stage5_final_verification.md)
records clean online and externally isolated full-stack launches.

## Campaign API

`GET /api/runs` lists cutoffs and horizons; `GET /api/metrics?run=A` provides model
comparison; `GET /api/calibration?run=A&model=bgnbd` provides calibration bins;
`GET /api/defaults` gives assumptions and ranges. `POST /api/optimize` accepts
`run`, `model`, `B`, `K`, `m`, `tau_e`, `tau_c`, `f_e`, `f_c`, `d`,
`interactive` (default true) and `include_extra_100` (default false). Invalid
inputs return 422. `POST /api/sensitivity` also accepts `budgets` and
`tau_c_values`, with at most 15 grid points. See the [API latency report](project-log/stage4_m3_results.md).

## Dashboard

The dashboard starts with net sales, **4,260 customers who bought in the last
12 months** (5,851 total accounts), **Returns** as a share of invoices, and expected
campaign profit alongside the available investment. It clearly labels sales as
identified-customer product sales only (about 77% of raw lines); revenue is not
profit. Monthly sales and Returns charts end at **Nov 2011**. The sales chart places its partial-December total, number of covered days and daily comparison directly below the title, computed from API values. Its own country selector defaults to All countries and updates both the series/y-axis and the December note. Returns charts use the same plain comparison style; exact totals and longer definitions remain available in info tooltips. The return-share note compares invoice shares rather than dividing percentages by days. The loyalty heatmap retains its partial-December column.

The executive panels show the United Kingdom amount and share as a headline and other countries on their own linear scale starting at zero, sales trends through November, country-filtered product top tens, a loyalty heatmap with 10 customers per page over the full ranking, all-account customer-ID search/sorting/10-row pagination (highest expected 90-day spend first), monthly returns, and a proposed campaign. The customer pager includes first, previous, next, last and go-to-page controls; probabilities keep their percentages; the saturated first-page bars were removed. The API keeps its existing 25-row pages; the dashboard combines and slices those pages for presentation. The reactivation table adds days since last
purchase and expected 90-day spend from the existing PROD/BG-NBD customer data,
alongside the recommended action, typical order value already returned by the optimizer, and assumed incremental gain. The campaign table filters Coupon (default), Email, No contact or All, pages 15 rows by expected gain, and exports every row of the current action filter. The loyalty ranking supports Previous/Next, go-to-page and exact customer-ID search that jumps to and highlights the customer. Unknown IDs have a clear message.
Only budget and maximum coupons are visible campaign inputs by default; margin,
offer responses, costs and discount are under **Advanced assumptions**. A quiet inline note at the top of the campaign section states that offer responses and margin are assumptions requiring an A/B test. The headline campaign card has a lighter dashed style and a **Scenario (assumption-based)** tag. ROI reads **£5.43 profit per £1 invested** with the default proposal. Every KPI card, both customer tables’ headers, and campaign limit/assumption controls have plain-language hover and keyboard-focus help. The [complete current tooltip list](project-log/stage5_phase2_tooltips.md) records the exact wording.

**Method and evidence** is collapsed at the bottom. It retains historical A/B/C
model comparison and calibration, campaign-model selection, actual solver gap/
status, all three baselines, sensitivity, optional extra-GBP-100 calculation and
the grouped Run A backtest with the selected-customer order-value check. The
production campaign always uses PROD; the account table always uses PROD/BG-NBD.
UI percentages map to fractional API inputs. A 350 ms debounce updates the
campaign and its headline profit/investment; customer-ID search debounces 250 ms.
Sensitivity updates explicitly and marks prior assumptions stale. Its default
15-point grid is cached at API startup.

Interactive results target a 0.5% relative gap and always show the actual gap
and status. If a feasible campaign already meets that gap against an exact
integer dual bound from OR-Tools' LP relaxation, it returns without CP-SAT search;
otherwise CP-SAT uses the remaining time allowance. Exact mode is still available
with `interactive=false`. The final [HTTP measurements](project-log/stage4_m4_http_benchmark.json)
and [browser verification](project-log/stage4_m4_browser_verification.json) separate
uncached, cached and optional second-solve timings.

All tau, margin and cost inputs are assumptions, not experimentally estimated
effects. The current interactive default improves on ratio greedy by GBP 0.55; the earlier exact solve improves by GBP 0.74. These are different plans under the same assumptions, not a rounding discrepancy. See the [reconciliation and three-row gain arithmetic](project-log/stage5_polish_fix.md).
Do not use the much larger naive-baseline improvement to claim a large advantage
over a sensible heuristic. Run A's 83.66% spend coverage contacts almost every
customer (98.65%) and describes what was at stake, not campaign effect.

## Executive metrics and endpoints

As of **09 Dec 2011**, rankings and annual KPIs use **10 Dec 2010–09 Dec 2011**.
Net sales restore quick-reversal purchases before subtracting overlap-deduplicated
valid product returns, preventing double subtraction. Missing customer IDs and
non-product codes are excluded. Monthly trends use the whole history. The
heatmap displays Jan–Dec 2011 while its loyalty ranking uses the rolling year,
including the preceding 10–31 Dec 2010. See [metric definitions](dashboard_metrics.md)
and the [endpoint verification report](project-log/stage5_e1_results.md).

Read-only cached JSON endpoints: `/api/exec/summary`, `/api/sales/by-country`,
`/api/sales/monthly?country=`, `/api/products/top?country=`, `/api/cancellations/monthly`,
`/api/customers/loyalty-heatmap?limit=10&offset=0&customer_id=`, and `/api/customers?search=&sort=&direction=&page=`.
The cancellations API path is retained for compatibility; the UI calls this
**Returns**, includes partial returns and does not claim that original orders
were fully cancelled. Expected customer spend allows repeat purchases and is
separate from assumed incremental campaign profit.

Monthly country names are validated against all countries in the full-history snapshot (unknown values return 422). Monthly filtering and both new paginated views use parameterized SQL against an in-memory SQLite index of the existing read-only startup snapshot and cached optimizer assignments. No ETL/model source table, model output or optimizer equation changes. No extra dependency is required.

`POST /api/optimize` adds an opaque `solution_id`; it still returns at most 15 `top_selected` rows and never the complete assignments. Use:

- `GET /api/campaign/customers?solution_id=...&action=coupon&limit=15&offset=0` for rows from that exact cached solution, descending expected gain then customer ID.
- `GET /api/campaign/export?solution_id=...&action=coupon` for all rows of that action filter as an attachment. CSV fields match the table: `customer_id`, `action`, `days_since_last_purchase`, `expected_spend_90d`, `order_value`, `expected_gain`; currency fields have two decimals. `none` means No contact.
- `GET /api/customers/loyalty-heatmap?limit=10&offset=0&customer_id=14500&year=2011` to jump to the page containing an exact ID. `year` is optional and must be 2010 or 2011 (default 2011, anything else returns 422); it changes only the 12 monthly columns and month labels (Jan–Dec of that year), never the ranking, order or totals. Lapsed customers legitimately return an all-zero row for a year without purchases. Ranking is unchanged, with customer-ID tie breaking. A missing numeric ID returns `found: false`; the UI gives a clear message.

Limits are integers 1–100, offsets 0–1,000,000; IDs are up to 64 digits. Actions are `coupon`, `email`, `none`, `all`. Invalid inputs return 422, as do unknown/expired solution identifiers. Cached solutions follow the existing 256-entry API cache and are lost on API restart; refresh the proposal if it expires. Customer context remains PROD/BG-NBD as of the snapshot date, exposed as `context_as_of`. The live report reconciles all 5,851 customers and every country/month; measured reads stay below 300 ms and sampled uncached interactive calls below 1 second. See the [views verification report](project-log/stage5_phase2_results.md) for exact measurements and limits.

## Browser verification

[`verify_dashboard.js`](../services/dashboard/verify_dashboard.js) and
[`verify_polish_layout.js`](../services/dashboard/verify_polish_layout.js) are
Playwright page functions (`async (page) => { ... }`) with no extra project
dependency. With the stack running, run them from the repository root with any
Playwright runner that executes a page function, for example the
Playwright CLI (`playwright-cli`):

```sh
playwright-cli --session dashboard open http://127.0.0.1:8080
playwright-cli --session dashboard run-code --filename services/dashboard/verify_dashboard.js
```

This checks labels, default collapsed sections, filters, search, sorting,
pagination, hover values, campaign controls, technical evidence and recovery
from deliberately injected failures; it writes screenshots under docs/screenshots.
All non-loopback page requests are blocked during verification. This browser
check is separate from the completed full-stack/offline startup test. See
[final results and reproduction](project-log/stage5_final_verification.md) for all tests,
container exits/health, unchanged-output hashes and offline network evidence.
