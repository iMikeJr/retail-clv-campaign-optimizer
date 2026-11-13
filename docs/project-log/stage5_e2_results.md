# Stage 5 E2: executive dashboard and browser verification

Historical E2 record: the subsequent three refinements and deferred final gate
are now complete. See [final verification](stage5_final_verification.md) and
[updated screenshots](screenshots/stage5-final-overview.png). The stop/pending
statements below describe the E2 checkpoint, not the current project status.

E2 is complete. **Stop here with screenshots**, before the deferred final
full-stack/network-disabled startup check. E1 remains accepted. The progress
checkpoint was written first in commit `fc84f85`; the runtime page replacement
is commit `1039509`. Nothing was pushed. Resumption guide:
[stage5_progress.md](stage5_progress.md).

## Executive page

The old technical-first page is replaced by Sales, Customers, Returns and a
budget-constrained proposed campaign. The header asks the business question,
shows **Data as of 09 Dec 2011**, and uses these accepted labels:

- Net sales last 12 months: **GBP 7,983,783** (whole-pound display of the accepted
  GBP 7,983,782.90 metric).
- **Customers: 4,260**, purchased in the last 12 months, with **5,851 total
  accounts** as a small footnote. The account table still lists all accounts.
- **Returns: 15.62%**, as a share of eligible invoices, partial returns included.
  The unchanged API route remains `/api/cancellations/monthly`.
- **Expected profit from the campaign: GBP 9,123**, paired with
  **invest £1,682, expect £9,123 in profit**. This is rounded expected scenario
  profit, not observed sales profit. The investment shown is the available
  budget; actual expected cost is GBP 1,681.29 in the campaign panel.

The visible population note is **Sales to identified customers only (about 77%
of lines)**. The visible response/margin assumption banner is retained verbatim.
**Dec (1-9)** labels the partial final month in the heatmap and all monthly charts.
No AUC, pi, tau, solver, gap or log-loss vocabulary appears above the fold.

Sales includes country bars (top ten plus Other, with shares), whole-history
monthly net sales and two country-filtered product top tens (revenue/units).
Customers includes the 25×12 spend heatmap with original-value hover/focus,
and customer-ID search, all six sort keys and fixed 25-row pagination over all
5,851 retained accounts. Returns shows monthly document counts, value and rates.

Campaign exposes only budget and maximum coupons by default. Margin, response
to email/coupon, costs and discount are in a collapsed **Advanced assumptions**
drawer with plain labels. Counts are proposed actions, not a claimed number of
reactivations. The panel shows actual expected cost, profit, profit per pound,
and all 15 highest-gain selected customers without fixed-height clipping.
The headline investment/profit updates with the proposal. Requests debounce
350 ms; customer search debounces 250 ms; stale responses are discarded.

**Method and evidence** is collapsed at the bottom. It retains historical model
comparison, calibration, campaign-model selection, actual status/gap, the naive,
email-only and ratio-greedy comparisons, action economics, sensitivity, optional
extra-GBP-100 calculation and grouped Run A backtest/order-value diagnostics.
Technical evidence requests are lazy: zero comparison/calibration/sensitivity
requests occur before this section first opens. The campaign stays on PROD;
the account forecast table stays on PROD/BG-NBD. This changes presentation only.

## Verification actually run

- Built only the dashboard image and updated only the dashboard service against
  the existing API/Postgres data; no ETL/model job was rerun.
- JavaScript syntax checks passed for app.js and verify_dashboard.js.
- Pinned Linux API/optimizer/executive suite: **81 passed in 0.73 seconds**.
  No backend, ETL, model, optimizer or dependency source was changed in E2.
  The E1 **21 model / 39 ETL** passes remain prior evidence; those unchanged
  suites were not unnecessarily rerun for frontend-only work.
- Headless Playwright/Chromium verification passed **30 positive interactions**:
  country filter/reset, customer next/previous pages, exact and empty search,
  sorting every numeric column and customer ID, budget slider, zero coupon cap
  (verified zero coupons), coupon limit, all six advanced assumptions, resets,
  historical comparison/calibration, campaign scoring model, optional additional
  investment and the 15-point sensitivity chart.
- Checked 4,260/5,851 labels, exact as-of/population/banner wording, profit with
  budget, Returns naming, all five partial-month chart/heatmap labels, 300
  heatmap cells and correct original GBP hover value. The tooltip remains
  correct after scrolling; an initial scroll-dismissal defect was fixed.
- Normal operation had **zero unexpected console errors** and **zero external
  page requests**. Non-loopback page traffic was blocked and recorded. Both
  127.0.0.1 and localhost origins worked. No page-level horizontal overflow at
  **1280×800** or **390×844**; wide tables/heatmap can scroll inside panels.
- Deliberate 503 injection verified campaign and product errors and recovery;
  delayed customer responses verified visible loading and disabled pagination;
  startup summary failure verified Retry local data recovery. Expected injected
  error logs are separate from the zero-error normal-operation checks.
- API/protected-source diff checks were clean. Independent read-only SQL again
  confirmed accepted annual/history sales, returns/invoice counts and unchanged
  historical model metric/prediction hashes; no source tables were written.

Full evidence: [browser verification](stage5_e2_browser_verification.json),
[data reconciliation](stage5_e2_data_reconciliation.json),
[campaign HTTP measurements](stage5_e2_campaign_http.json).

## Measured latency

- Uncached interactive optimize, six budgets: median **0.151 s**,
  maximum **0.268 s** (HTTP, no extra-budget solve).
- Cached default optimize: median **1.61 ms**.
- Optional extra-GBP-100 request: **0.225 s**.
- A new 15-point sensitivity grid: **2.200 s**;
  identical cached request **1.48 ms**.
- Browser budget-slider-to-response: **371 ms**, including
  350 ms debounce and browser interaction time, with a cached response in this
  final browser pass. Uncached HTTP requests were measured separately above.
  Other timings are in the JSON.

These local measurements are not a guarantee for every parameter/concurrent
workload. The actual certified solver status/gap remains in Method and evidence.
The default interactive profit is GBP 9,122.55 versus the earlier exact result
GBP 9,122.74; the algorithm and accepted results are not refitted or altered.

## Screenshots and reproduction

- [Executive overview](screenshots/stage5-e2-overview.png)
- [Full page, evidence collapsed](screenshots/stage5-e2-full-page.png)
- [Loyalty heatmap](screenshots/stage5-e2-loyalty-heatmap.png)
- [Original-value hover](screenshots/stage5-e2-heatmap-hover.png)
- [Returns](screenshots/stage5-e2-returns.png)
- [Campaign](screenshots/stage5-e2-campaign.png)
- [All 15 selected customers](screenshots/stage5-e2-selected-customers.png)
- [Expanded Method and evidence](screenshots/stage5-e2-method-evidence.png)
- [Deliberate error state](screenshots/stage5-e2-error-state.png)

Viewport captures reflect the normal page. Tall element-only captures suppress
sticky navigation to avoid screenshot overlays; that does not change runtime
assets or data. The heatmap element capture suppresses the floating tooltip;
the separate hover screenshot demonstrates its value.

From the repository root, with local services running:

```sh
playwright-cli --session executive open http://127.0.0.1:8080
playwright-cli --session executive run-code --filename services/dashboard/verify_dashboard.js
```

The CLI returns structured verification results and writes screenshots to
`docs/screenshots/`. It uses existing Playwright/Chromium tooling; no new project
runtime or test dependency was added. The frontend uses local assets, vanilla
JavaScript, inline SVG and system fonts; no CDN or external fonts.

## Remaining gate

The deferred clean full-stack `docker compose --env-file .env.example up --build`
verification, exit/health audit from a clean state, and startup with networking
disabled have **not** been run here. Prepared images/build layers are required
for that final offline check. Browser non-loopback blocking is not a substitute
for the full-stack test. E2 stops here as requested.

No real campaign is sent. Offer response and margin remain assumptions; future
calibration and incremental campaign effects remain unverified. No credentials
were exposed and no OpenAI API was called.
