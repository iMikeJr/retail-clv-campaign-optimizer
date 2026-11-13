# Phase 1: small fix pass

One extra local commit after `530800a`. **Stop here; Phase 2 has not begun.** Nothing has been pushed. All runtime changes are UI text/layout; no API, ETL, model, optimizer, dependency, Dockerfile or Compose source changes were needed. No credentials were printed or staged.

## Delivered fixes

1. **Excluding the United Kingdom** is a chart title directly above the bars, using the other chart titles' weight. **Other countries (combined)** is lighter and separated by a thin divider. Country bars retain the same linear zero-based scale and values.
2. The sales partial-month comparison appears immediately below its title at normal text size: **Dec 1–9 is a partial month: £37.7k per day vs £22.0k per day on average.**
3. Proposed-action cards reserve space for their info icons. Dedicated checks/captures at 1280 and 1440 px verify that icons do not intersect numbers or labels. The expanded Run A KPI cards have the same reservation.
4. **Time as customer (days)** is the UI label; the API/sort key remains `customer_age_days`. Contacted-customer realized spend has the exact requested tooltip: “What these customers actually spent in the historical period, before any campaign. It is a reference point, not a result.”
5. Long chart/table notes are now in info tooltips. Each Returns chart has one short comparison (41–44 characters), rendered on one line at the checked desktop widths and readable on mobile. The invoice-share note is **Dec 1–9: 14.9% of invoices vs 16.6% average.** The previous average covers Dec 2009–Nov 2011 (730 calendar days); the percentage is the ratio of summed invoice counts. Exact December totals and definitions remain in the tooltip. The ten highest-spend customers have probabilities from 98.7% to 99.9%, so the saturated bars were removed; all percentages remain.
6. **Typical order value** displays the existing `top_selected[].v` returned by the optimizer. The exact requested tooltip explains its role in gain. No new API field or calculation was introduced. Browser checks compare all three audited rows with the response and reproduce their expected gains.
7. Both visible improvement figures now refer to the current interactive proposal. The historical static £0.74 note was replaced with an explanation in the baseline info tooltip. Precise reconciliation is below.
8. Product country is initialized explicitly to All countries in page state and applied after the options load, with form autocomplete disabled. Browser verification selects Brazil, reloads and verifies that both selector and tables return to All countries. The previous code read the live DOM selection while rebuilding options; this pass does not claim to identify which browser-state mechanism produced the user's Brazil selection.
9. Method and evidence uses **Solved to within 0.5% of the best possible plan** when the returned bound meets that target; the fallback wording does not claim success if it does not. Raw status/native status and actual gap are in its help tooltip. Legend entries are **Coupon response 5% / 15% / 25%**; the historical column is **Average predicted probability**, retaining **Observed purchase rate**. The previous-assumptions note uses neutral muted text. Returns has the same section width as Sales, Customers and Campaign.

## Expected-gain arithmetic

All three default selected actions below are coupons. The assumed extra probability of buying is `0.15 × (1 − pi)`. Expected coupon cost is `1 + 0.10 × v × (pi + extra probability)`. Gain uses the original, unrounded fields: `0.30 × v × extra probability − cost`; only the result is formatted to pennies.

| Customer | v (GBP) | Extra probability | Cost (GBP) | Gain arithmetic (GBP), rounded at end |
| --- | ---: | ---: | ---: | --- |
| 13902 | 2751.729661465119 | 0.148502874606464 | 44.6104327216283 | 0.30 × 2751.729661465119 × 0.148502874606464 − 44.6104327216283 = **77.98** |
| 12482 | 2302.602234018914 | 0.148445866883604 | 37.5668787288901 | 0.30 × 2302.602234018914 × 0.148445866883604 − 37.5668787288901 = **64.98** |
| 16754 | 2078.056565409350 | 0.149980239812910 | 32.1941173934995 | 0.30 × 2078.056565409350 × 0.149980239812910 − 32.1941173934995 = **61.31** |

Each matches both the UI's expected gain and the optimizer's `net_value_pence` (7798, 6498 and 6131). Order values in the table are displayed to two decimals; the verification uses the full response precision. The model's per-customer value and assumed offer response remain distinct: a low expected 90-day spend does not mean a small typical order.

## Why £0.55 and £0.74 differed

These were **different selected plans under different solve modes**, not a rounding error:

| Plan | Unrounded expected profit (GBP) | Same ratio-greedy profit (GBP) | Difference shown to pennies |
| --- | ---: | ---: | ---: |
| Current interactive proposal | 9122.550711942204 | 9122.003019999462 | **0.55** (raw 0.547691942742) |
| Exact reference | 9122.742858723526 | 9122.003019999462 | **0.74** (raw 0.739838724065) |

Interactive mode accepts a feasible plan within its 0.5% target; it need not choose the exact reference plan. Its measured gap is about 0.00329% for the optimizer's penny-rounded objective. Business profit and the greedy comparison above use unrounded expected values, then format the difference. The current UI's headline comparison and baseline row both use `baselines.ratio_greedy.improvement` from the same response and update with the assumptions. The old static note mixed this current interactive comparison with an exact historical comparison; it is no longer displayed.

Full precision and the three independent calculations: [economics evidence](stage5_polish_fix_economics.json).

## Tests and browser verification

| Existing suite, pinned Linux service image | Result |
| --- | --- |
| API / executive / optimizer | 81 passed in 0.86 s |
| ETL | 39 passed in 0.77 s |
| Model, including Postgres integration | 21 passed in 57.21 s |
| Total | **141 passed, no skips** |

Only disposable test containers installed development dependencies. Model integration uses and cleans up reserved test runs; no ETL or production model batch was launched. JavaScript syntax checks for all three dashboard scripts and `git diff --check` pass.

The complete browser pass checks **36 positive interactions**, **50 info icons on hover and keyboard focus**, all 16 number/slider help interactions, customer search/sorts/pager, original heatmap values, all 15 selected customers' context, three gain calculations, consistency of both greedy comparisons, labels, new plain-language status/legend, collapsed defaults, lazy evidence, input changes and error recovery. Normal operation has **zero console errors and zero external page requests**; external page traffic is blocked and recorded. Deliberately injected 503s are separate error/recovery checks.

Additional verification opens Run A while measuring its cards at 1280 and 1440 px, checks that every action/Run A icon is separate from text, verifies equal section widths and single-line Returns notes, tests Brazil selection followed by reload, checks neutral sensitivity-note colour, and checks that narrow-screen campaign inputs fit inside their panel. Root horizontal overflow is absent at 1280×800, 1440×900 and 390×844. Wide tables, heatmap and the country bars scroll inside their panels on narrow screens.

Evidence: [suite results](stage5_polish_fix_tests.json), [full browser result](stage5_polish_fix_browser.json), [dedicated layout result](stage5_polish_fix_layout.json), [complete current tooltip texts](stage5_polish_fix_tooltips.md).

An initial browser check caught a missing heading target while moving a table footnote into help; it was corrected before the successful full pass. A heading assertion was then updated to account for the newly adjacent help button. No failed attempt is counted as a pass.

## Screenshot review and corrections

Every refreshed screenshot listed below (21 files) was opened and visually inspected. The full mobile image was also examined in readable crops. The review found and corrected these issues before delivery:

- Action-card and Run A icons competed with their text: reserved space now separates them; the dedicated captures and rectangle checks confirm it.
- The old £0.74 note contradicted the current £0.55 comparison: all visible figures now use the current interactive plan, with the distinction documented above.
- The overview viewport cut off the final country bar: its capture is now tall enough to include the combined countries and axis; a complete Sales capture is also supplied.
- A mobile section-heading icon wrapped onto its own line: the heading keeps the icon beside it and places section context below on narrow screens.
- Side-by-side mobile campaign controls clipped at the panel edge: they now stack at narrow widths, and all four primary input/slider bounds are checked.
- Country-label text became too small when squeezed into the mobile panel: the bars retain a readable minimum width and scroll within that panel.
- A focused tooltip obscured the budget in the deliberate-error screenshot: it is dismissed before that capture. The separate hover/focus captures intentionally show the help overlay.
- The expanded-assumptions capture needed a taller viewport to show its full panel: it is captured with adequate height.

After these corrections there are no outstanding unclear, unintentionally truncated, overlapping or contradictory elements identified in the reviewed captures. Narrow-screen internal scrolling is intentional; no table rows or columns are deleted to fit a viewport. Tooltips intentionally overlay nearby content while open and dismiss with Escape.

- [action cards 1280](screenshots/stage5-polish-fix-action-cards-1280.png) — visually reviewed.
- [action cards 1440](screenshots/stage5-polish-fix-action-cards-1440.png) — visually reviewed.
- [advanced assumptions](screenshots/stage5-polish-fix-advanced-assumptions.png) — visually reviewed.
- [campaign](screenshots/stage5-polish-fix-campaign.png) — visually reviewed.
- [customer ranking](screenshots/stage5-polish-fix-customer-ranking.png) — visually reviewed.
- [error state](screenshots/stage5-polish-fix-error-state.png) — visually reviewed.
- [full page](screenshots/stage5-polish-fix-full-page.png) — visually reviewed.
- [heatmap hover](screenshots/stage5-polish-fix-heatmap-hover.png) — visually reviewed.
- [loyalty heatmap](screenshots/stage5-polish-fix-loyalty-heatmap.png) — visually reviewed.
- [method evidence](screenshots/stage5-polish-fix-method-evidence.png) — visually reviewed.
- [mobile top](screenshots/stage5-polish-fix-mobile-top.png) — visually reviewed.
- [mobile](screenshots/stage5-polish-fix-mobile.png) — visually reviewed.
- [overview](screenshots/stage5-polish-fix-overview.png) — visually reviewed.
- [returns](screenshots/stage5-polish-fix-returns.png) — visually reviewed.
- [run a kpis 1280](screenshots/stage5-polish-fix-run-a-kpis-1280.png) — visually reviewed.
- [run a kpis 1440](screenshots/stage5-polish-fix-run-a-kpis-1440.png) — visually reviewed.
- [sales](screenshots/stage5-polish-fix-sales.png) — visually reviewed.
- [selected customers](screenshots/stage5-polish-fix-selected-customers.png) — visually reviewed.
- [sensitivity note](screenshots/stage5-polish-fix-sensitivity-note.png) — visually reviewed.
- [tooltip focus](screenshots/stage5-polish-fix-tooltip-focus.png) — visually reviewed.
- [tooltip hover](screenshots/stage5-polish-fix-tooltip-hover.png) — visually reviewed.


Reproduce from the repository root with the local stack running:

```sh
playwright-cli --session polish open http://127.0.0.1:8080
playwright-cli --session polish run-code --filename services/dashboard/verify_dashboard.js
playwright-cli --session polish run-code --filename services/dashboard/verify_polish_layout.js
```

Only the dashboard image/service was rebuilt. The normal stack is left healthy on the polished UI. No push; no Phase 2 work.
