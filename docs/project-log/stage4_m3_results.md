# Stage 4 M3: read-only API

Implemented `/api/runs`, `/api/metrics`, `/api/calibration`, `/api/defaults`,
`POST /api/optimize` and `POST /api/sensitivity`; retained `/health`.

## Behavior

- API startup loads runs, metrics and all five models' customer predictions in
  one REPEATABLE READ, READ ONLY Postgres transaction. SQL is static with bound
  parameters; user input never becomes SQL. The immutable in-memory snapshot is
  refreshed by restarting the API after a model rerun. Compose waits for the
  model to complete before API startup on a normal full-stack launch.
- Optimize accepts run/model, B/K and all six economic assumptions. Defaults are
  PROD/bgnbd, interactive=true, include_extra_100=false. Interactive CP-SAT uses
  a 0.5% gap target and a 1.8-second solve allowance; exact mode remains available.
  Actual status, bound, gap and optimality_proven are always returned. Nonzero-gap
  native OPTIMAL is relabeled FEASIBLE_GAP_TARGET, not claimed as an exact optimum.
- All ranges are published by `/api/defaults`. Invalid ranges, unknown fields,
  nonfinite values and grids over 15 points return 422 without echoing submitted
  values. Unavailable saved runs/models return 404. Database failures use generic
  messages; credentials are not logged.
- Sensitivity forces interactive mode, omits the extra-budget solve, and allows
  at most 15 unique budget/tau combinations. Each point uses the same bounded
  256-entry LRU cache as optimize, keyed by every typed request parameter. The
  default 5-budget x 3-tau PROD/bgnbd grid is computed before startup completes.
- Cache lookup/write locks are brief; a sensitivity batch does not hold a lock
  across its solves. Interactive calls can run while another grid is calculating.
  This is a local single-user demo, not a multi-tenant latency SLA.
- CORS permits only `http://127.0.0.1:${DASHBOARD_PORT}` and
  `http://localhost:${DASHBOARD_PORT}`. API/dashboard published ports remain bound
  to 127.0.0.1. The existing local Postgres override also binds to 127.0.0.1.

## Verification and measured HTTP latency

Built the image, started the API against existing saved runs without rerunning
ETL/model, and checked real endpoints. Linux suite: **62 passed in 0.48 seconds**
(44 optimizer cases and 18 ASGI API cases using a small fixture, no new dependency).
Tests cover endpoints, validation/422, unavailable runs, CORS, calibration absence
on PROD, optional extra-budget solve, startup precomputation and cache reuse.

- Uncached interactive optimize, six nearby budgets: median **1.136 s**,
  maximum **1.383 s**.
- Cached default optimize: median **1.47 ms**.
- Optional extra-GBP-100 request: **1.789 s** (two solves).
- Default-grid precomputation at startup: **8.401 s**.
- Default sensitivity after startup: **1.65 ms**, zero new solves.
- Uncached 15-point sensitivity: **10.385 s**;
  identical cached request: **2.61 ms**.

HTTP timings include serialization and localhost transport. Imports/startup are
excluded from request timings and measured separately. Full statuses, bounds,
gaps and individual times are in [the HTTP benchmark](stage4_m3_http_benchmark.json).
This benchmark is reproducible with `services/api/benchmark_http.py`.

Dashboard/browser verification is M4; clean full-stack/offline Compose startup
remains M5. No new Python runtime or development dependency was added.
