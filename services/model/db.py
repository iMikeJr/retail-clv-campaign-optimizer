"""Schema constants and database I/O. Never print connection details."""

import os
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import URL, create_engine
from psycopg import sql

SOURCE_SCHEMA = "public"
MODEL_SCHEMA = "modeling"


def database_engine():
    url = URL.create("postgresql+psycopg", host=os.environ["POSTGRES_HOST"],
                     database=os.environ["POSTGRES_DB"], username=os.environ["POSTGRES_USER"],
                     password=os.environ["POSTGRES_PASSWORD"])
    return create_engine(url, hide_parameters=True)


def load_inputs(engine):
    # One consistent snapshot prevents mixing tables across a simultaneous ETL commit.
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            clean = pd.read_sql_query(f'SELECT * FROM "{SOURCE_SCHEMA}"."clean_transactions"', connection)
            reversals = pd.read_sql_query(f'SELECT * FROM "{SOURCE_SCHEMA}"."reversed_purchases"', connection)
            rfm = pd.read_sql_query(f'SELECT * FROM "{SOURCE_SCHEMA}"."customer_rfm"', connection)
    for frame in (clean, reversals):
        frame["invoice_date"] = pd.to_datetime(frame.invoice_date)
    reversals["cancellation_invoice_date"] = pd.to_datetime(reversals.cancellation_invoice_date)
    return clean, reversals, rfm


def _copy_rows(table, connection, keys, rows):
    statement = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
        sql.Identifier(MODEL_SCHEMA), sql.Identifier(table.name),
        sql.SQL(", ").join(map(sql.Identifier, keys)))
    with connection.connection.driver_connection.cursor() as cursor:
        with cursor.copy(statement) as copy:
            for row in rows:
                copy.write_row(row)


def publish(engine, run, metrics, predictions):
    """A failed insert preserves the entire previous committed version of the run."""
    from sqlalchemy import text

    with engine.begin() as connection:
        schema = Path(__file__).with_name("schema.sql").read_text().format(schema=f'"{MODEL_SCHEMA}"')
        for statement in schema.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
        # Serialize replacements of the same run across concurrent service launches.
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext(:run_id))"), {"run_id": run["run_id"]})
        connection.execute(text(f'DELETE FROM "{MODEL_SCHEMA}".model_runs WHERE run_id=:run_id'),
                           {"run_id": run["run_id"]})
        columns = list(run)
        statement = (f'INSERT INTO "{MODEL_SCHEMA}".model_runs (' + ",".join(columns)
                     + ") VALUES (" + ",".join(":params" if c == "params" else f":{c}" for c in columns) + ")")
        # Bind JSON explicitly instead of interpolating any data into SQL.
        statement = statement.replace(":params", "CAST(:params AS JSONB)")
        connection.execute(text(statement), {**run, "params": json.dumps(run["params"], allow_nan=False)})
        for table, frame in (("model_metrics", metrics), ("customer_predictions", predictions)):
            frame = frame.assign(run_id=run["run_id"])
            frame.to_sql(table, connection, schema=MODEL_SCHEMA, if_exists="append", index=False,
                         method=_copy_rows, chunksize=10_000)
