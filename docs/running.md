# Running the stack

Configuration, start-up, service behavior and re-running individual jobs.
The [Makefile](../Makefile) wraps the most common commands (`make up`,
`make etl`, `make model`, `make down`).

## Start the stack

Requires Docker Engine with Docker Compose, or Docker Desktop, running locally.

1. Download `online_retail_II.xlsx` from the
   [UCI Machine Learning Repository](https://doi.org/10.24432/C5CG6D) and place it
   in `data/raw/`. The ETL does not download the dataset. This directory is ignored by Git and mounted read-only
   into the ETL container.
2. Copy `.env.example` to `.env` and set your local database credentials. If
   `.env` already exists, add the missing settings there instead of overwriting
   it. The example contains sample values only.
3. Start the services:

   ```sh
   docker compose up --build
   ```

Compose automatically reads `.env`. Required database settings fail validation
when missing or empty. `.env` is ignored by Git and is outside every service's
Docker build context. Keep credentials in `.env`; do not log or commit them.

The default URLs are:

- API health: <http://localhost:8000/health>
- API documentation: <http://localhost:8000/docs>
- Dashboard: <http://localhost:8080>

`API_PORT` and `DASHBOARD_PORT` in `.env` change the host ports. Both published
ports bind to localhost. PostgreSQL is available only inside the Compose network.

For background execution:

```sh
docker compose up --build -d
```

## Service behavior

- **PostgreSQL:** reports healthy using `pg_isready`; stores data in the named
  `postgres_data` volume.
- **ETL:** waits for healthy PostgreSQL, validates both sheets, replaces all six
  tables atomically, prints the data quality report, and exits with code `0`.
  It has `restart: "no"` and no healthcheck. A failure exits non-zero and prevents
  a new API container from starting.
- **API:** waits for healthy PostgreSQL and successful ETL/model completion. `/health`
  opens an authenticated PostgreSQL connection and executes `SELECT 1`. It
  returns HTTP `200` with `{"status":"ok","database":"ok"}` when successful,
  or HTTP `503` when the database is unavailable.
- **Model:** waits for healthy PostgreSQL and successful ETL completion, reconciles
  historical features with the ETL, runs A/B/C/A_no_cap/PROD, and replaces each run's
  outputs atomically in `modeling`. It exits `0` on success, has `restart: "no"`,
  and publishes no ports. `RANDOM_SEED` defaults to `42`. The API loads its saved
  results into a read-only startup snapshot and precomputes the default sensitivity
  grid; restart the API after a model rerun to refresh its snapshot and caches.
- **Dashboard:** serves local HTML/CSS/vanilla JS with inline SVG charts using
  Python's standard library, waits for API health, and reports healthy when it
  responds to HTTP requests. `API_PORT` is injected locally, so custom ports work.

Verify after startup:

```sh
docker compose ps --all
curl --fail http://localhost:8000/health
curl --fail http://localhost:8080/
```

Expected: PostgreSQL, API, and dashboard show `healthy`; ETL and model show
`Exited (0)`. Exited ETL/model containers are expected successful batch-job states.

Run the ETL again on demand:

```sh
docker compose run --rm etl
```

This creates a temporary ETL container, runs the full ETL once, and removes that
container afterward. The command returns exit code `0` on success. Source data
and the cutoff determine the table contents, so repeating a run replaces the
contents with the same results for the same reversal window. A failed database write rolls back the entire
replacement, preserving the previous committed tables.

For a historical cutoff, set `CUTOFF_DATE=2011-06-30` in `.env`, or override it
for one run:

```sh
docker compose run --rm -e CUTOFF_DATE=2011-06-30 etl
```

Blank `CUTOFF_DATE` defaults to the calendar date of the last raw `InvoiceDate`.
The whole cutoff day is included. The cutoff affects `customer_rfm` and its
cutoff-specific quality metrics; raw and cleaned tables retain the full history.

`REVERSAL_WINDOW_HOURS` defaults to `24`. It must be a finite nonnegative number;
`0` disables quick-reversal removal. For example, to use a one-hour window:

```sh
docker compose run --rm -e REVERSAL_WINDOW_HOURS=1 etl
```

Stop the stack while retaining the database volume:

```sh
docker compose down
```
