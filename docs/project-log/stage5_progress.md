# Stage 5 progress and resumption guide

## Current checkpoint: reduced Phase 2

The authorized reduced Phase 2 is complete in one local commit after `31fb6ea`; **STOP**. Nothing has been pushed. See [results and screenshot review](stage5_phase2_results.md), [HTTP reconciliation/timings](stage5_phase2_http.json), [browser checks](stage5_phase2_browser.json), and [layout checks](stage5_phase2_layout.json).

New runtime work is confined to the API's read-only cache/views and dashboard: country-filtered monthly series, 15-row campaign action paging and full-filter CSV from the same cached plan, and 10-row full loyalty ranking with exact-ID jump/highlight. SQL parameters are bound in an in-memory SQLite snapshot index; no persistent schema/table changes or dependencies. ETL/model/optimizer/Compose sources remain unchanged. All 141 earlier tests plus 39 new cases pass (180 total); browser checks cover retained behavior and the new controls. Current screenshots use `dashboard-*`.

The prior request's broader product browsing/shared country selector/extra heatmap rows were superseded by the reduced scope. No further phase is authorized. Cached `solution_id` values expire with the existing 256-entry cache or an API restart; refresh the proposal to obtain a current ID.

## Prior checkpoint: Phase 1 small fix pass

The [small fix pass](stage5_polish_fix.md) follows Phase 1 commit `530800a` in **one extra local commit**. STOP; Phase 2 has not begun. No API/backend, ETL, model, optimizer, dependency or Compose source changes were needed: selected rows already return order value as `v`. Nothing has been pushed.

Current screenshots use `stage5-polish-fix-*`. All 141 tests pass; full browser verification and separate 1280/1440 layout checks pass with no normal console errors/external requests. Every refreshed screenshot was visually reviewed. The report records the review and fixes, three expected-gain calculations, and why interactive £0.55 and exact £0.74 improvements differed. All current UI improvement figures use the interactive proposal consistently. Current [tooltip inventory](stage5_polish_fix_tooltips.md).

## Prior checkpoint: presentation polish Phase 1

Phase 1 is complete in one local commit; **STOP before Phase 2** until the user gives the go-ahead. Nothing has been pushed. See [Phase 1 report](stage5_polish_phase1.md), [all tooltip texts](stage5_polish_phase1_tooltips.md), and [browser evidence](stage5_polish_phase1_browser.json). The current screenshots use `stage5-polish-phase1-*`.

The API, ETL, model and optimizer sources remain unchanged. Customer-table pages and the heatmap show 10 rows in the dashboard using existing API responses. December 1–9 appears in chart notes with daily comparisons; complete-month charts end at November. The UK share is a headline above other-country bars. Campaign assumptions are a quiet inline note in section 04. All 141 existing tests pass.

Phase 2 is pending: shared country selector, product browsing, extra heatmap customers, and campaign filtering/pagination/export with additive API changes. Its requested whole-phase rollback gate has not been exercised because Phase 2 has not begun.

## Prior checkpoint: final full-stack verification

2026-10-25: **E1, E2, the three final dashboard refinements and final verification
are complete.** The previous E2 stop is superseded by the user's explicit final
verification request. Nothing has been pushed.

Runtime refinement commit: `e6f47fd` (on top of accepted E2 `06890c4`). The local
documentation/evidence commit follows it; use `git log -2 --oneline` for both IDs.
See [final verification](stage5_final_verification.md) for commands, results,
limitations and the full evidence index. E1/E2 reports retain their historical
checkpoint statements and measurements.

## Final page changes

- Sales and return-rate charts distinguish incomplete **Dec (1-9)** using a
  dotted segment and hollow marker. Return-count/value bars use hollow dotted
  outlines. Notes explain partial coverage; numerical values remain unchanged.
- **Who is likely to buy?** starts with expected 90-day spend descending across
  all 5,851 accounts. Search, all six sort keys and 25-row pagination remain.
  The API's own default remains customer ID ascending.
- **Customers to reactivate** shows days since last purchase and expected spend
  over 90 days next to action/gain. These fields use existing PROD/BG-NBD
  customer data and exact ID matching, independently of the campaign model.
  Loading/unavailable values and retry are verified; gain/order/selection are
  still the unchanged optimizer's result.

## Final verification

- Complete pinned-image suites: **81 API/optimizer/executive + 39 ETL + 21 model
  = 141 passed**, with no skipped tests. Model cases include database integration,
  all-run idempotence, saved equality and rollback. JavaScript syntax/diff checks
  pass. Initial test invocation setup errors and corrected reruns are recorded.
- Clean project `clv-final`, initially absent database volume:
  `docker compose --env-file .env.example up --build`. ETL/model exit **0**;
  PostgreSQL/API/dashboard **healthy**; both localhost HTTP checks return **200**.
- Fresh volume/containers again, same prepared images, no build/pull, Docker
  default network `internal: true`. Complete ETL/model/startup succeeds offline.
  Direct external TCP probes fail with network-unreachable while the same host
  probe succeeds. This disables stack egress; host Wi-Fi remains enabled.
- All six public table contents, all model predictions/metrics, and stable
  model-run metadata match the original data exactly by saved digests after
  both fresh launches. Historical hashes/financial SQL independently reconcile.
  Original project volume is preserved. No API/ETL/model/optimizer/dependency or
  production Compose source was changed.
- Full browser script passes online and offline: **31 interactions per pass**,
  zero unexpected normal console errors/external requests, labels, all partial
  styles, default ranking, all 15 customer context values, tooltips, collapsed
  evidence, filters/sorts/pagination, campaign assumptions, historical evidence,
  sensitivity, injected errors/retry and responsive layouts.
- Updated screenshots use `docs/screenshots/stage5-final-*`; previous E2 images
  remain historical evidence. The overview, returns, account ranking and selected
  customer captures were visually inspected.

## Preserved definitions and limits

As of **2011-12-09**; KPI/ranking window **2010-12-10–2011-12-09**. Annual net
sales **GBP 7,983,782.90**, full-history net **GBP 16,411,916.58**; **4,260**
active / **5,851** retained accounts; return-invoice rate **15.62%**. Sales
exclude anonymous/non-product lines and restore quick reversals before credits.
Loyalty ranks rolling-year clean spend while the heatmap displays Jan–Dec 2011.
Definitions: [dashboard_metrics.md](../dashboard_metrics.md).

Default campaign: PROD/BG-NBD, budget GBP 1,682, max coupons 300; interactive
profit GBP 9,122.55, exact reference GBP 9,122.74. Responses/margin remain
assumptions; expected spend allows repeats, gain values one scenario purchase
occasion. Run A covers 98.65% of customers / 83.66% of eligible realized spend;
this is not campaign-effect evidence. Future calibration and causal response
remain unverified. Default host ports only were verified; host-wide network
shutdown, arbitrary concurrent workload and universal latency guarantees were
not tested. No new analysis or modeling is required by this checkpoint.

## Resume safely

- Read README, final report, metric definitions and `git status` first.
- Do not print credentials or edit `.env`; use `.env.example` for verification.
- The verification stack used a separate project name and an internal Docker
  network, then was removed. The normal stack is restored with its original
  database volume and the verified dashboard image.
- Use the recorded offline Compose environment when reproducing isolation; the
  final report gives exact commands and the local browser access helper. Rebuilding the dashboard alone does not
  require rerunning ETL/model. Restart API after intentionally republishing data.
- Browser reproduction: Playwright CLI `run-code --filename
  services/dashboard/verify_dashboard.js`; it saves final screenshots in docs.
- Preserve all backend outputs and scenario limitations. No messages are sent.
