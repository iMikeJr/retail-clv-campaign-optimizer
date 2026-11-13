# Stage 5: reduced Phase 2

The authorized reduced Phase 2 is complete in one local commit after `31fb6ea`. **STOP; no further phase has begun.** Nothing has been pushed. Work started at **2026-10-26 04:25 UTC**, within the requested approximately 90-minute window. The final verification time is recorded below.

## Delivered scope

- **UK headline:** the amount and share are read from `/api/sales/by-country`, displayed as **United Kingdom: £6,550,865 (82.1% of net sales)** for the current snapshot. The amount is rounded to whole pounds for presentation; the source amount is £6,550,864.61.
- **Partial December:** the sales note is computed from API totals, cutoff day and the preceding calendar-month grid: **December is incomplete (1-9 Dec): £339k in 9 days, or £37.7k per day. An average day in the previous months was £22.0k.** Returns notes use the same plain comparison style. They describe observed partial-period totals/rates; there is no extrapolation. Complete-month charts still end in November.
- **Monthly country selector:** defaults to All countries and controls only the monthly series, y-axis and December note. Product country remains independent. Country choice and actual series also remain consistent after Retry local data. Unknown countries return 422. All full-history countries are available, including countries absent from the annual product ranking.
- **Campaign:** Coupon is the default action filter; Email, No contact and All are available. Each page has 15 rows sorted by unrounded expected gain descending, then customer ID. Counts, Previous/Next and go-to-page controls cover the full plan. CSV exports every row of the current action filter, with the table's six fields and two-decimal currency. Empty filters show a clear message and disabled paging controls.
- **Loyalty:** Customer loyalty ranking pages all 5,851 accounts, 10 rows at a time, using the existing score and customer-ID tie break. Previous/Next, counts and go-to-page work through the final one-row page. Exact customer-ID search jumps to its ranked page and highlights the row; an unknown numeric ID gives a clear message. The first ten IDs/values are unchanged. A short one-line footnote remains, with the longer definition in its info tooltip.

No map, probability-of-not-buying column, product-browser expansion or shared top-of-section country selector was added. This follows the reduced scope, which supersedes the earlier broader Phase 2 plan.

## API and cache behavior

The existing API loads PostgreSQL data once inside its read-only repeatable-read startup snapshot. A Python-standard-library **in-memory SQLite index** now holds that snapshot's country/month facts, complete loyalty rows, and the assignments produced by cached campaign solves. It is not a persistent database or new source schema. All country, exact-ID, action, solution, limit and offset values are SQL parameters; composed SQL fragments are fixed constants. GET views only read the cache.

No ETL, model, optimizer, dependency, Dockerfile or production Compose source was changed. No model fitting, ETL batch or production model job was run. No credentials were printed or committed. The API/dashboard images alone were rebuilt against the existing data.

| Endpoint | Parameters / response |
| --- | --- |
| `/api/sales/monthly` | `country=''` means all; a known country returns the same month grid with zeros where needed. Response includes the available full-history countries. Unknown/overlong values: 422. |
| `/api/customers/loyalty-heatmap` | `limit=10`, `offset=0`, optional `customer_id=''`, optional `year` (2010 or 2011, default 2011; changes only the monthly columns, not the ranking). Limit 1–100; offset 0–1,000,000; ID up to 64 digits. Returns total, effective offset, found flag and highlight ID. Search overrides offset to the containing ranked page. Unknown numeric IDs return 200 / `found:false` and no highlight. Invalid inputs: 422. |
| `/api/campaign/customers` | Required `solution_id`, `action=coupon`, `limit=15`, `offset=0`. Same integer bounds; actions `coupon`, `email`, `none`, `all`. Invalid values or missing/unknown/expired solution: 422. |
| `/api/campaign/export` | Required `solution_id`, `action=coupon`. Attachment for **all** matching rows, in the same order as paging. Invalid action/solution: 422. |

`POST /api/optimize` adds an opaque solution identifier. It still returns at most 15 `top_selected` rows and does not return the full assignments. Paging/export cannot invoke the optimizer: they read the exact plan identified by that response. Concurrent identical solves retain the already-published plan instead of replacing its row identity. When the existing 256-entry cache evicts a plan, its indexed rows are removed too. API restart clears the cache; refresh the proposal if a solution expires.

The selected action's order value/gain remain the optimizer's unchanged `v`/`net_value`. Descriptive days-since-purchase and expected 90-day spend remain the current PROD/BG-NBD snapshot, with its date explicitly returned as `context_as_of` (also when inspecting a historical cached plan). CSV columns map to the UI as follows:

| UI column | CSV field |
| --- | --- |
| Customer | `customer_id` |
| Recommended action | `action` (`none` = No contact) |
| Days since last purchase | `days_since_last_purchase` |
| Expected spend · 90 days | `expected_spend_90d` |
| Typical order value | `order_value` |
| Expected gain | `expected_gain` |

## Tests and reconciliation

| Suite in pinned Linux service image | Result |
| --- | --- |
| API / executive / optimizer | **120 passed** in 2.24 s (81 existing + 39 new) |
| ETL | **39 passed** in 0.88 s |
| Model, including real Postgres integration | **21 passed** in 60.85 s |
| Total | **180 passed; no skips** |

Existing pytest files were not modified. New tests cover all new parameters/routes, invalid types/bounds/enums/IDs, 422 responses, month-by-month country sums, historical-only countries, first-ten preservation, paging beyond the old 25-row cap, exact-ID jump/missing ID, campaign ordering/counts, independent cached plans, no solve during paging/export, and full/empty CSV filters. Model integration uses and cleans up reserved test runs. JavaScript syntax, Python compilation and `git diff --check` also pass.

The independent live HTTP audit additionally verifies:

- **41 countries × 25 months:** country-filtered gross sales, returns and net sales add to the unfiltered series month by month, to within floating-point tolerance.
- **5,851 loyalty rows:** every page combined has exactly the complete sorted set, no duplicate or missing IDs; the first ten match the existing ranking. Last-customer search jumps to its final page.
- **Campaign:** each paginated action set has the same total/order as its full CSV; every row's current customer context matches the unchanged account endpoint.

| Default filter | Paginated rows | CSV rows |
| --- | ---: | ---: |
| Coupon | 146 | 146 |
| Email | 5,617 | 5,617 |
| No contact | 88 | 88 |
| All | 5,851 | 5,851 |

Annual net sales remain **£7,983,782.90**, full-history net sales **£16,411,916.58**, and default interactive expected campaign profit **£9,122.55**. Read-only SQL reproduces the accepted totals and unchanged historical metric/prediction hashes.

Evidence: [suite results](stage5_phase2_tests.json), [complete HTTP audit/timings](stage5_phase2_http.json), [independent SQL reconciliation](stage5_phase2_reconciliation.json).

## Measured latency

Measurements use local HTTP on the prepared stack, including response reading. The HTTP audit skips already-cached probe budgets until it has ten uncached samples, so it can be rerun without falsely calling cached responses uncached. Actual sample budgets and payload sizes are saved in the JSON.

| Route / operation | Requests | Median | Maximum |
| --- | ---: | ---: | ---: |
| Monthly sales | 42 | 1.61 ms | 20.44 ms |
| Loyalty paging/search | 588 | 0.98 ms | 5.72 ms |
| Campaign paging | 786 | 2.92 ms | 6.74 ms |
| Campaign CSV | 4 | 7.76 ms | 14.99 ms |
| Uncached interactive optimize | 10 | 173.12 ms | 257.26 ms |
| Cached interactive optimize | 6 | 1.42 ms | 2.55 ms |

All measured new read requests are below 300 ms, and all ten sampled uncached interactive solves are below 1 second. The final browser budget-slider action took 367 ms, including its 350 ms debounce, with a cached response; uncached HTTP samples are listed separately above. Optimize responses remain approximately 9 KB with a 15-row preview, rather than transferring all 5,851 assignments. These are measured local samples, not a universal concurrent-load guarantee.

## Browser checks and visual review

The full Chromium script passes **53 interactions** with **zero normal console errors and zero external page requests**, retaining the prior UI regression checks and adding monthly filtering/y-axis/note updates, filter independence, country preservation after local retry, loyalty paging/search/highlight/missing/final page, campaign paging/action filters, and all four full-filter CSV downloads. Actual downloaded files were independently parsed and their row counts reconciled with the endpoint totals. All 50 info icons and all 16 paired number/slider controls retain hover/focus help. Existing collapsed defaults, account search/sorts/pager, three-row gain arithmetic, baseline consistency, model evidence, assumptions and error recovery remain checked.

Separate layout checks pass at **1280**, **1440**, and **390 px**: no page-level overflow, equal section widths, no action/Run A icon overlap, usable narrow-screen controls, and neutral sensitivity status. Wide tables/heatmap/country bars scroll within their panels. Longer plain Returns comparisons occupy two readable lines at desktop widths.

Deliberate 503 checks are separate from the zero-error normal pass. Campaign-list failure disables export and recovers through Retry campaign list; campaign/product/startup errors and delayed customer loading retain their prior recovery checks. The initial CSV browser assertion used a response-inspector body that was empty even though the actual download contained all rows; the verifier now checks page-side bytes and saves/parses the actual download. This was a verification-transport issue, not a missing-row export.

Every refreshed screenshot listed below (28 files) was opened and visually inspected, including readable crops of the full mobile page. Review confirmed that the longer UK headline and monthly note fit, country/chart controls stay distinct, action filters/CSV/pagers are readable, and loyalty highlighting is clear. The overview capture includes complete country bars/axes; tooltip captures are positioned to keep the section heading visible. The local-retry chart/selector inconsistency found during review was corrected and regression-tested. The loyalty footnote was also shortened after mobile review so it stays on one line, with a regression check for that width. No unintended overlapping, truncated, unclear or contradictory element remains identified in the final captures; tooltip overlays and internal scrolling are intentional.

Evidence: [full browser result](stage5_phase2_browser.json), [dedicated layout checks](stage5_phase2_layout.json).

## Screenshots

- [action cards 1280](../screenshots/dashboard-action-cards-1280.png) — visually reviewed.
- [action cards 1440](../screenshots/dashboard-action-cards-1440.png) — visually reviewed.
- [advanced assumptions](../screenshots/dashboard-advanced-assumptions.png) — visually reviewed.
- [campaign all](../screenshots/dashboard-campaign-all.png) — visually reviewed.
- [campaign email](../screenshots/dashboard-campaign-email.png) — visually reviewed.
- [campaign empty](../screenshots/dashboard-campaign-empty.png) — visually reviewed.
- [campaign none](../screenshots/dashboard-campaign-none.png) — visually reviewed.
- [campaign](../screenshots/dashboard-campaign.png) — visually reviewed.
- [customer ranking](../screenshots/dashboard-customer-ranking.png) — visually reviewed.
- [error state](../screenshots/dashboard-error-state.png) — visually reviewed.
- [full page](../screenshots/dashboard-full-page.png) — visually reviewed.
- [heatmap hover](../screenshots/dashboard-heatmap-hover.png) — visually reviewed.
- [loyalty heatmap](../screenshots/dashboard-loyalty-heatmap.png) — visually reviewed.
- [loyalty not found](../screenshots/dashboard-loyalty-not-found.png) — visually reviewed.
- [loyalty search](../screenshots/dashboard-loyalty-search.png) — visually reviewed.
- [method evidence](../screenshots/dashboard-method-evidence.png) — visually reviewed.
- [mobile top](../screenshots/dashboard-mobile-top.png) — visually reviewed.
- [mobile](../screenshots/dashboard-mobile.png) — visually reviewed.
- [overview](../screenshots/dashboard-overview.png) — visually reviewed.
- [returns](../screenshots/dashboard-returns.png) — visually reviewed.
- [run a kpis 1280](../screenshots/dashboard-run-a-kpis-1280.png) — visually reviewed.
- [run a kpis 1440](../screenshots/dashboard-run-a-kpis-1440.png) — visually reviewed.
- [sales france](../screenshots/dashboard-sales-france.png) — visually reviewed.
- [sales](../screenshots/dashboard-sales.png) — visually reviewed.
- [selected customers](../screenshots/dashboard-selected-customers.png) — visually reviewed.
- [sensitivity note](../screenshots/dashboard-sensitivity-note.png) — visually reviewed.
- [tooltip focus](../screenshots/dashboard-tooltip-focus.png) — visually reviewed.
- [tooltip hover](../screenshots/dashboard-tooltip-hover.png) — visually reviewed.


## Reproduce and stopping point

```sh
# Against the prepared local stack; no model or ETL batch is needed.
python3 services/api/verify_phase2_http.py
playwright-cli --session phase2 open http://127.0.0.1:8080
playwright-cli --session phase2 run-code --filename services/dashboard/verify_dashboard.js
playwright-cli --session phase2 run-code --filename services/dashboard/verify_polish_layout.js
```

Browser downloads are saved to `/tmp/phase2-campaign-*.csv` for verification, not committed. Current [tooltip inventory](stage5_phase2_tooltips.md). Earlier phase reports/screenshots remain historical records.

Final verification completed at 2026-10-26 04:55:57 UTC (about 31 minutes after the recorded start).

The normal API/PostgreSQL/dashboard stack remains healthy. All requested verification gates passed, so the phase rollback gate was not triggered. The implementation, tests, docs and evidence are delivered in one local commit. No push; stop here.
