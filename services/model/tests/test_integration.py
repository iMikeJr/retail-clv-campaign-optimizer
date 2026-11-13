"""Real Postgres acceptance checks; run in the model container with pytest installed.

Only a reserved test run is replaced and deleted. Public tables are read-only.
"""

import os

import pandas as pd
from pandas.testing import assert_frame_equal
import pytest
from psycopg.errors import UniqueViolation
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from data import reconcile_rfm
from db import MODEL_SCHEMA, database_engine, load_inputs, publish
from main import EXPERIMENTS, run_experiment
from test_recovery import check_fitted_low_a_recovery


@pytest.mark.skipif(not os.environ.get("POSTGRES_HOST"), reason="requires Compose Postgres")
@pytest.mark.parametrize("run_name", [*EXPERIMENTS, "PROD"])
def test_experiment_idempotence_saved_outputs_and_atomic_rollback(run_name):
    engine = database_engine()
    reserved = f"__stage3_pytest__:{run_name}"
    try:
        clean, reversals, rfm = load_inputs(engine)
        assert reconcile_rfm(clean, reversals, rfm)["customers"] == len(rfm)
        arguments = {"clean": clean, "reversals": reversals, "name": run_name,
                     "capped": run_name != "A_no_cap", "scoring": run_name == "PROD"}
        dates = ("2011-12-09", 90) if run_name == "PROD" else EXPERIMENTS[run_name]
        first = run_experiment(*dates, **arguments)
        if run_name == "A":
            check_fitted_low_a_recovery(first[0]["params"]["cutoff_fits"]["test"]["bgnbd"]["parameters"])
        second = run_experiment(*dates, **arguments)
        assert (first[0]["test_cutoff"] - first[0]["train_cutoff"]).days == dates[1]
        if run_name == "PROD":
            assert first[0]["base_rate_test"] is None
            assert first[2].filter(like="actual_").isna().all().all()
            assert set(first[1].metric) == {"test_n", "mean_predicted_probability"}
        assert (first[0]["params"]["purchase_cap"] is None) == (run_name == "A_no_cap")
        # Times and created_at vary; every numerical evaluation and prediction must match.
        assert_frame_equal(first[1], second[1], check_exact=True)
        assert_frame_equal(first[2], second[2], check_exact=True)
        for run, metrics, predictions in (first, second):
            run["run_id"] = reserved
            publish(engine, run, metrics, predictions)
            with engine.connect() as connection:
                stored_metrics = pd.read_sql_query(text(
                    f'SELECT model,metric,segment,value FROM "{MODEL_SCHEMA}".model_metrics WHERE run_id=:id'),
                    connection, params={"id": reserved})
                stored_predictions = pd.read_sql_query(text(
                    f'SELECT * FROM "{MODEL_SCHEMA}".customer_predictions WHERE run_id=:id'),
                    connection, params={"id": reserved}).drop(columns="run_id")
            keys = ["model", "metric", "segment"]
            assert_frame_equal(stored_metrics.sort_values(keys).reset_index(drop=True),
                               metrics.sort_values(keys).reset_index(drop=True), check_exact=True)
            keys = ["model", "customer_id"]
            expected = predictions.sort_values(keys).reset_index(drop=True)
            actual = stored_predictions.sort_values(keys).reset_index(drop=True)[expected.columns]
            assert_frame_equal(actual, expected, check_dtype=False, check_exact=True)
        def snapshot():
            with engine.connect() as connection:
                return [pd.read_sql_query(text(
                    f'SELECT * FROM "{MODEL_SCHEMA}".{table} WHERE run_id=:id ORDER BY {order}'),
                    connection, params={"id": reserved})
                    for table, order in (("model_runs", "run_id"),
                                         ("model_metrics", "model,metric,segment"),
                                         ("customer_predictions", "model,customer_id"))]

        before_failure = snapshot()
        bad_metrics = pd.concat([first[1], first[1].iloc[[0]]], ignore_index=True)
        with pytest.raises((UniqueViolation, IntegrityError)):
            publish(engine, first[0], bad_metrics, first[2])
        for before, after in zip(before_failure, snapshot()):
            assert_frame_equal(before, after, check_exact=True)
        with engine.connect() as connection:
            count = connection.execute(text(
                f'SELECT count(*) FROM "{MODEL_SCHEMA}".model_metrics WHERE run_id=:id'),
                {"id": reserved}).scalar_one()
            tables = connection.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=:schema"),
                {"schema": MODEL_SCHEMA}).scalars().all()
        assert count == len(first[1])
        assert set(tables) == {"model_runs", "model_metrics", "customer_predictions"}
    finally:
        # The service will have created its schema before this cleanup on success.
        with engine.begin() as connection:
            if connection.execute(text("SELECT to_regclass(:table)"),
                                  {"table": f"{MODEL_SCHEMA}.model_runs"}).scalar_one():
                connection.execute(text(f'DELETE FROM "{MODEL_SCHEMA}".model_runs WHERE run_id=:id'),
                                   {"id": reserved})
        engine.dispose()
