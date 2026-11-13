# Stage 5 final verification

Historical full-stack/offline verification record. The subsequent presentation-only changes and refreshed screenshots are in [Phase 1 polish](stage5_polish_phase1.md); the earlier startup evidence below remains unchanged.

The three requested dashboard refinements and final verification are complete.
Runtime refinement commit: `e6f47fd`, following accepted E2 `06890c4`. The final
local evidence/documentation commit follows it (`git log -2 --oneline`). Nothing
was pushed. Stages 1–4 and accepted E1/E2 definitions/results are preserved.

## Dashboard changes

1. Sales and return-rate lines mark incomplete **Dec (1-9)** with a dotted
   connecting segment and hollow marker. Return-count/value bars use hollow,
   dotted outlines. Short notes explain partial coverage. Values, rates, axes,
   dates and hover amounts are unchanged; no extrapolation is introduced.
2. **Who is likely to buy?** initially requests `expected_spend_90d` descending
   across all accounts, before pagination. Customer-ID search, every sort key,
   ascending/descending controls and 25-row pagination remain available. The
   API default itself remains customer ID ascending.
3. **Customers to reactivate** adds days since last purchase and expected spend
   over 90 days beside action/gain. Existing `/api/customers?search=ID` data is
   matched to exact customer IDs and cached in the page. Both context fields use
   PROD/BG-NBD, explicitly labeled even when another campaign model is chosen.
   The optimizer's top-15 order, action and gain are unchanged. Missing context
   displays loading/unavailable rather than a fabricated zero, retries on the
   next proposal update, and cannot replace a newer proposal's rows.

No source changes to `services/api`, `services/etl`, `services/model`, runtime
requirements, `docker/postgres` or production `docker-compose.yml`. No ETL rule,
model, fitted parameter, optimizer equation, API default or endpoint changed.
The extra Python/Compose files in docs are verification tools only; no service
image bundles them.

## Tests

| Suite, in pinned Linux service image | Final result | Exit code |
| --- | --- | ---: |
| API / optimizer / executive | 81 passed in 0.90 s | 0 |
| ETL | 39 passed in 0.65 s | 0 |
| Model, including real Postgres integration | 21 passed in 60.97 s | 0 |
| Total | **141 passed, no skips** | 0 |

Also passed: `node --check` for app.js and verify_dashboard.js, Python compilation
of the offline access helper, and `git diff --check`. Model integration covers
all-run exact repeatability, saved-output equality and transactional rollback;
reserved test runs were cleaned up.

Development dependencies were installed only in disposable test containers.
API/model tests mount their test directory and development lock into the image.
ETL tests import `services.etl`, so mount `services/etl` at `/repo/services/etl`
and use workdir `/repo` with `python -m pytest services/etl/tests -q -x`.

Two initial invocation errors were corrected: ETL initially lacked the repository
import path (exit 2), and model integration initially started before the fresh
ETL completed (exit 1). Complete corrected suites passed; no application change
or tolerance relaxation addressed these setup errors. Evidence:
[tests](stage5_final_tests.json).

## Clean online build and startup

The original project's containers were stopped to free ports; its database
volume was retained. Verification used `COMPOSE_PROJECT_NAME=clv-final`,
with no pre-existing verification volume or containers, and the exact command:

```sh
COMPOSE_PROJECT_NAME=clv-final docker compose --env-file .env.example up --build
```

All five images built. The local ignored PostgreSQL-port override was present
for this online pass; no credentials or `.env` contents are included in evidence.
Prepared images exclude pytest and require no runtime downloads.

| Service | Online state | Offline state |
| --- | --- | --- |
| PostgreSQL | running, healthy | running, healthy |
| ETL | exited 0; 34.59 s | exited 0; 32.93 s |
| Model, A/B/C/A_no_cap/PROD | exited 0; 21.48 s | exited 0; 20.56 s |
| API | running, healthy; health HTTP 200 | running, healthy; health HTTP 200 |
| Dashboard | running, healthy; HTTP 200 | running, healthy; HTTP 200 |

Long-running service `State.ExitCode=0` is not presented as a completed batch;
health is checked separately. The foreground `up` command remains attached while
services run. Offline foreground shutdown returns 0, recorded separately from
ETL/model exits. Evidence: [online command / clean-state record](stage5_final_online_command.json),
[online startup](stage5_final_online_startup.json),
[offline startup](stage5_final_offline_startup.json),
[offline command](stage5_final_offline_command.json).

## Startup with application networking disabled

A second fresh database volume and containers were started with the **same five
image IDs**. No build or image pull was permitted. The verification override
[stage5_offline.compose.yml](stage5_offline.compose.yml) makes the sole application
network internal; all five services have exactly that network. ETL reads the
local workbook, the complete model batch executes, and API/dashboard become
healthy with external egress unavailable.

Docker Desktop suppresses published port bindings on an internal network.
For browser access, the verification override explicitly clears API/dashboard
host bindings and [stage5_offline_access.py](stage5_offline_access.py) forwards
localhost HTTP via `docker exec`/stdio to the containers' own HTTP servers.
It preserves response status/body and CORS-related headers, uses no public
upstream, adds no container network and changes no application asset or backend.
Offline browser latency includes this verification transport and is not a normal
localhost performance benchmark.

Reproduction after preparing the images and freeing localhost ports:

```sh
# Remove only this disposable verification project's generated volume.
docker compose -p clv-final --env-file .env.example down --volumes
COMPOSE_PROJECT_NAME=clv-final \
COMPOSE_FILE=docker-compose.yml:docs/project-log/stage5_offline.compose.yml \
docker compose --env-file .env.example up --pull never
# In another terminal, once services are ready:
python3 docs/project-log/stage5_offline_access.py
# Then run the browser verification command below.
```

There is **no `--build`** in offline startup. `--pull never` additionally prevents
registry access. This checks offline operation with prepared images, not offline
image building or installation of development dependencies.

Direct external TCP probes to `1.1.1.1:443` fail for every service/image on that
network; API/dashboard are probed in their live containers, ETL/model use the
same prepared images on the same network after their successful batch exits.
PostgreSQL is also probed in its live container. The host positive control to
that same destination succeeds. Thus egress is blocked by the application
network, rather than by a coincidentally unavailable remote target.
[Network evidence](stage5_final_offline_network.json).

Initial internal startup succeeded but native localhost bindings were
unavailable. A bridge option disabling masquerading was rejected because egress
still succeeded on Docker Desktop. An early forwarding-harness attempt conflicted
with Docker's attempted port reservation; the final verification override clears
those bindings. These setup attempts are not accepted browser passes; the final
isolated fresh launch and full browser pass succeeded. Earlier attempt evidence:
[initial startup](stage5_final_offline_internal_startup.json),
[initial command](stage5_final_offline_initial_command.json),
[port-access attempt](stage5_final_offline_access_attempt.json).

## Data and backend preservation

Before startup, all six original ETL tables and complete model outputs were
fingerprinted. After both the clean online and final isolated launches:

- All six public tables match exactly by row counts and order-independent row
  content digests, including all **1,067,371 raw**, **786,895 clean**, **1,292
  reversed** rows and **5,851 RFM** customers.
- All **130,520 prediction rows**, **1,568 metric rows** and five model-run
  records match. Model-run comparison excludes `created_at` and timing keys;
  all remaining model settings, parameters and diagnostics are compared exactly.
- Independently reproduced historical metric/prediction hashes remain
  `04598d662434c62e47d08fd2d3f8f6fa` /
  `b8d6623b46afe8035bb884c132667dbb`.
- Independent SQL reconciles annual net sales **GBP 7,983,782.90**, full-history
  net sales **GBP 16,411,916.58**, returns and invoice counts. Production outcomes
  remain NULL. Campaign assumptions/results are unchanged.

Evidence: [original baseline](stage5_final_baseline.json),
[complete comparisons and digest method](stage5_final_output_comparison.json),
[online independent SQL](stage5_final_data_reconciliation.json),
[offline independent SQL](stage5_final_offline_reconciliation.json).

## Browser checks and screenshots

The complete headless Chromium script passes online and on the isolated stack,
with **31 positive interactions per pass**, zero unexpected normal console
errors and zero external page requests. Non-loopback page traffic is blocked.
It verifies all three refinements, all 15 customer context values against HTTP
responses, initial numeric ranking and sort indicator, labels, 300 heatmap cells,
original-value hover, country filters, search/sort/pagination, campaign controls
and assumptions, collapsed defaults/lazy evidence, historical comparisons,
calibration, baselines, optional extra investment and 15-point sensitivity.

Deliberate failures separately verify context lookup retry, campaign/product
recovery, delayed customer loading/disabled pagination and startup Retry local
data. Expected injected 503 console logs are distinct from the zero-error normal
pass. Both localhost origins and no page-level horizontal overflow at 1280×800
and 390×844 pass. Wide content scrolls inside its panel.

```sh
playwright-cli --session final open http://127.0.0.1:8080
playwright-cli --session final run-code --filename services/dashboard/verify_dashboard.js
```

Evidence: [online browser](stage5_final_browser_online.json),
[offline browser](stage5_final_browser_offline.json),
[restored normal-stack browser](stage5_final_browser_restored.json). The restored
normal stack also passes all 31 interactions; saved screenshots reflect this
final normal-stack pass.
Updated screenshots, with the key refinements visually inspected:

- [Overview / partial sales month](screenshots/stage5-final-overview.png)
- [Default customer ranking](screenshots/stage5-final-customer-ranking.png)
- [Returns / partial month styling](screenshots/stage5-final-returns.png)
- [All 15 reactivation rows and added context](screenshots/stage5-final-selected-customers.png)
- [Full page](screenshots/stage5-final-full-page.png)
- [Heatmap](screenshots/stage5-final-loyalty-heatmap.png), [hover](screenshots/stage5-final-heatmap-hover.png)
- [Campaign](screenshots/stage5-final-campaign.png)
- [Method and evidence](screenshots/stage5-final-method-evidence.png)
- [Deliberate error state](screenshots/stage5-final-error-state.png)

Element captures hide sticky navigation to avoid screenshot overlays. The live
page is unchanged by screenshot styling. Earlier stage screenshots remain
historical artifacts.

## Limits and handoff

Offline here means **external networking disabled for the Docker application
stack**, with internal database/service and local browser access retained. Host
Wi-Fi was not disabled. A whole-host network shutdown, native published-port
browser access on Docker Desktop's internal network, custom host ports and
arbitrary concurrent workloads are not claimed as verified.

Future forecast calibration, true offer response/margin and causal campaign
profit remain unverified. No new analysis or campaign is executed. The normal
stack is restored with the original database volume and updated dashboard;
verification containers and the local forwarding harness are stopped afterward.
The original database full snapshot remains unchanged on restoration.
[Restoration evidence](stage5_final_restored_stack.json).
