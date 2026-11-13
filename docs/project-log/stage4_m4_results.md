# Stage 4 M4: dashboard and browser verification

Completed M2b, M3 and M4; stop before M5. The API and English dashboard are running
locally at http://127.0.0.1:8000 and http://127.0.0.1:8080. No push was made.

## Built

- Local HTML/CSS/vanilla JS with inline SVG charts, system fonts and no CDN.
  Standard-library serving injects API_PORT locally; CORS uses DASHBOARD_PORT.
  Dashboard waits for API health. All published ports remain on 127.0.0.1.
- Historical A/B/C model comparison: AUC, AP, log loss, Brier, lift at 10%, revenue
  capture at 20%, selectable calibration and explicit holdout dates/horizon.
  B's 180-day window is labeled; campaign selection uses only 90-day PROD/A/C.
- Campaign controls for budget, coupon capacity, margin, both tau values, fixed
  costs, discount, run and all five models. Changes debounce for 350 ms. Latest
  responses replace older ones; previous sensitivity curves are labeled stale
  until explicitly updated. Loading, invalid-input, API-error and retry states
  are visible. Extra GBP 100 is optional and off by default.
- None/email/coupon counts, cost/net/ROI, improvement over ratio greedy, optional
  extra-budget value, action economics, all three baselines, top 15 customers,
  15-point sensitivity chart and a grouped Run A backtest. The assumption banner
  and “what was at stake, not campaign effect” interpretation are prominent.
- Interactive optimization first uses a feasible campaign plus an exact integer
  dual certificate. If the certified gap is already <=0.5%, it returns immediately
  without CP-SAT search; the response names that path and reports its actual gap.
  Otherwise CP-SAT uses the remaining interactive allowance. Exact mode is retained.

Default interactive PROD shows GBP 9,122.55 raw expected net value versus the
exact M2b result GBP 9,122.74. Its integer objective is GBP 9,122.66 with an upper
bound GBP 9,122.96: a **0.003289%** gap. These are penny-formulation bounds, not
uncertainty intervals or estimated treatment effects. Small assignment/count
changes from exact mode are expected under the relaxed gap.

## Verification

- **63 optimizer/API tests passed in 0.45 s** in the Linux API image (45 optimizer,
  18 ASGI endpoint cases). This includes the certified interactive path avoiding
  CP-SAT when its bound already meets the requested gap. No new dependencies.
- **21 model tests passed in 57.44 s**, including the original 17; **39 ETL tests
  passed in 0.98 s**. No ETL/model implementation changed in M2b/M3/M4.
- Headless Playwright/Chromium: zero unexpected console errors during normal
  loading/interactions; **no external page requests**. All non-loopback page
  requests were intercepted and would have failed the check.
- Verified budget slider changes B from 1682 to 1683 and updates net value; all
  remaining scenario inputs, optional extra-budget checkbox, reset, campaign
  model/run selectors, A/B/C comparison selectors, calibration selection and
  sensitivity refresh respond. All tested optimization responses were HTTP 200.
- Verified both 127.0.0.1 and localhost origins; no horizontal page overflow at
  1280x800 or 390x844. Controlled 503 injection verifies visible campaign errors,
  stale-result labeling, recovery, and startup API-unavailable retry. Deliberate
  error responses are separate from the zero-error normal-loading check.
- Browser evidence: [verification JSON](stage4_m4_browser_verification.json).
  Reproduce with the Playwright CLI's (`playwright-cli`) `run-code --filename
  services/dashboard/verify_dashboard.js` from the repository root. It writes
  screenshots under docs/screenshots. The script is not bundled into the image.
- API/dashboard images built successfully and both running services are healthy.
  Complete historical metric/prediction hashes still match the pre-M1 values:
  `04598d662434c62e47d08fd2d3f8f6fa` and
  `b8d6623b46afe8035bb884c132667dbb`. PROD's actual_* columns remain entirely NULL.
  Only A/B/C/A_no_cap/PROD runs remain; reserved test runs were cleaned up.

## Final measured latency

Local HTTP timings include response serialization and transport. Startup, model
fitting and imports are excluded from request latency and measured separately.

| Measurement | Time |
| --- | ---: |
| Uncached interactive optimize, six nearby budgets: median | 0.144 s |
| Uncached interactive optimize: maximum | 0.173 s |
| Cached default optimize: median | 1.28 ms |
| Optional extra-GBP-100 request (two solves) | 0.247 s |
| Default 15-point grid precomputed at startup | 2.177 s |
| Cached default sensitivity (zero new solves) | 1.47 ms |
| New 15-point grid | 1.988 s |
| Same grid cached | 1.52 ms |

The browser's slider-to-response time includes its 350 ms debounce and is recorded
separately in the browser evidence. The requested ~2 s interactive target was met
on these scenarios; it is not a guarantee for every input or concurrent workload.
All default-grid gaps are reported, including the formerly time-limited point.
Final raw measurements: [HTTP benchmark](stage4_m4_http_benchmark.json). M3/M2b
reports preserve their earlier measurements before the certified-gap fast path.

## Screenshots

- [Default full page](screenshots/dashboard-default.png)
- [Campaign at laptop dimensions](screenshots/campaign-laptop.png)
- [After budget slider change](screenshots/campaign-slider-changed.png)
- [Grouped Run A backtest](screenshots/backtest-laptop.png)
- [Deliberate API-error state](screenshots/api-error-state.png)

## Remaining work and limits

M5's clean full-stack `docker compose --env-file .env.example up --build` and
complete offline startup verification have **not** been run. Existing ETL/model
batch containers still reflect the prior successful execution; tests used
separate disposable containers. This is not represented as a new clean launch.

Offline browser operation was checked with external page traffic blocked, and
M2/M2b optimizer calculations ran with Docker networking disabled. The normal
API connects only to local Compose Postgres. Prepared images/build layers are
still required for an offline build/start. Custom port plumbing is implemented;
only the default ports were exercised end to end in the browser.

All conversion rates, margins and campaign costs are assumptions. The exact
optimizer's GBP 0.74 improvement over ratio greedy is modest. Run A's 83.66%
spend coverage contacts 98.65% of customers and is not evidence of campaign effect.
Future calibration and actual incremental campaign performance remain unverified.
No OpenAI API was called.
