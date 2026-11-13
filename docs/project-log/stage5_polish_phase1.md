# Stage 5: bounded presentation polish, Phase 1

Phase 1 is complete in one local commit. **Stop here; Phase 2 awaits the user's go-ahead.** Nothing has been pushed. The prior [full-stack/offline verification](stage5_final_verification.md) remains historical evidence; this polish pass rebuilt only the dashboard against the existing healthy API/database.

## Changes delivered

1. The revenue-versus-profit footnote is inside Net sales. The top assumption banner is removed. The headline campaign card is lighter, dashed and tagged **Scenario (assumption-based)**.
2. Section 04 starts with the exact quiet inline note: “The response to each offer and the margin are assumptions, not estimated from data; an A/B test would estimate them.”
3. **Return on investment (ROI)** displays **£5.43 profit per £1 invested** for the default proposal. The denominator remains expected actual cost, not the budget ceiling.
4. All KPI cards (including proposed-action counts and historical-check cards), all 11 headers across the two customer tables, and every campaign limit/advanced assumption have info icons. All **33 icons** support hover and keyboard focus. All **16 numeric inputs/sliders** also show the corresponding help directly on hover/focus; Escape dismisses the tooltip. The [full tooltip inventory](stage5_polish_phase1_tooltips.md) contains every icon's exact text and location.
5. The PROD/BG-NBD footnote under Customers to reactivate is removed. Context values remain the same exact-ID lookups as before.
6. Monthly sales and all Returns charts end in **Nov 2011**. **Dec (1-9)** is a separate short note with its total and daily average beside the complete-history average. The comparison period is explicitly **Dec 2009–Nov 2011, 730 calendar days**. No extrapolation or replacement of the observed December values is used. For the return-share chart, the note gives the observed percentage plus return invoices/day and the previous period's combined invoice share; percentages are not divided by days.
7. **United Kingdom 82.1% of net sales** is a headline. The remaining nine leading countries and Other are charted under **Excluding the United Kingdom** on their own linear scale starting at £0. Shares remain shares of overall annual net sales.
8. Who is likely to buy? shows **10 compact rows**, expected spend descending by default, numeric probability plus an inline bar, and First/Previous/Next/Last/Go to page. To preserve Phase 1's API boundary, the frontend combines at most two existing 25-row API pages and slices the required ten rows. Page 3 tests the boundary; the final page has one customer (page 586).
9. The loyalty heatmap shows the **top 10 customers** from the existing endpoint, retaining all 12 columns and original-value hover/focus.

No map or probability-of-not-buying column was added. No API, ETL, model, optimizer, dependency, Dockerfile or Compose source was changed. Credentials were neither printed nor staged.

## Verification

All existing suites ran in disposable containers using the pinned Linux service images; development dependencies were installed only in those containers:

| Suite | Result |
| --- | --- |
| API / optimizer / executive | 81 passed in 0.96 s |
| ETL | 39 passed in 0.83 s |
| Model, including Postgres integration | 21 passed in 56.72 s |
| Total | **141 passed, no skips** |

Model integration exercises reserved test runs and cleans them up; no ETL or production model batch was launched. JavaScript syntax checks and `git diff --check` pass.

The final Playwright/Chromium pass completed **36 positive interactions**, all **33 icon hover/keyboard checks**, all **16 input/slider hover/focus checks**, and independent reproduction of the December notes from HTTP values. It also covers:

- Existing country product filtering, customer-ID search, empty results, all six sort keys, and exact context values for all 15 proposed contacts.
- Ten-row pagination, page-boundary continuity, last/first/go-to-page behavior and disabled controls during loading/empty results.
- Budget/coupon changes, all six advanced assumptions, zero coupons, reset, lazy historical evidence, calibration, alternate campaign scoring, optional extra investment and sensitivity.
- Deliberate 503 injection and recovery for customer context, campaign, products and initial data loading. Expected injected error logs are separate from normal-operation results.
- Both localhost origins, no page-level overflow at **1280×800** and **390×844**, **zero normal console errors**, and **zero external page requests**. Non-loopback page traffic was blocked and recorded.

Evidence: [browser result](stage5_polish_phase1_browser.json), [read-only SQL reconciliation and preserved historical hashes](stage5_polish_phase1_reconciliation.json). Annual net sales remain **£7,983,782.90**, full-history net sales **£16,411,916.58**; default detailed expected campaign profit remains **£9,122.55**.

Only the dashboard image/service was rebuilt. Full-stack clean startup and Docker network isolation were not repeated for these presentation changes; the earlier final report records those checks. Initial Docker/Playwright sandbox cache errors were resolved with approved outside-workspace execution; no application change was needed for them.

## Refreshed screenshots

The overview, campaign, customer ranking, Returns, heatmap, tooltip and mobile views were visually inspected. Earlier screenshots remain historical artifacts.

- [Overview](screenshots/stage5-polish-phase1-overview.png)
- [Full page](screenshots/stage5-polish-phase1-full-page.png)
- [Campaign / ROI / inline note](screenshots/stage5-polish-phase1-campaign.png)
- [Customer table / pager / inline probability](screenshots/stage5-polish-phase1-customer-ranking.png)
- [Returns / December comparisons](screenshots/stage5-polish-phase1-returns.png)
- [Top 10 loyalty heatmap](screenshots/stage5-polish-phase1-loyalty-heatmap.png)
- [Original-value heatmap hover](screenshots/stage5-polish-phase1-heatmap-hover.png)
- [All 15 proposed contacts](screenshots/stage5-polish-phase1-selected-customers.png)
- [Help on hover](screenshots/stage5-polish-phase1-tooltip-hover.png)
- [Help on keyboard focus](screenshots/stage5-polish-phase1-tooltip-focus.png)
- [Expanded advanced assumptions](screenshots/stage5-polish-phase1-advanced-assumptions.png)
- [Mobile full page](screenshots/stage5-polish-phase1-mobile.png)
- [Expanded Method and evidence](screenshots/stage5-polish-phase1-method-evidence.png)
- [Deliberate error state](screenshots/stage5-polish-phase1-error-state.png)

The full browser check is reproducible from the repository root using the Playwright CLI (`playwright-cli`):

```sh
playwright-cli --session polish open http://127.0.0.1:8080
playwright-cli --session polish run-code --filename services/dashboard/verify_dashboard.js
```

The main script refreshes the ten primary captures. Additional tooltip, expanded-assumptions and mobile captures were taken separately in the same browser session. The runtime stack remains healthy with the polished dashboard. Phase 2 has not begun.
