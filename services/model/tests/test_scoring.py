"""Production uses complete training labels, never unavailable forecast labels."""
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from data import ModelError, build_features, build_labels, purchase_cap
from main import run_experiment
from test_features import make_lines, empty_reversals


def test_production_cutoff_boundaries():
    clean = make_lines([{"invoice_date": date} for date in (
        "2011-09-10 23:59:59", "2011-09-11", "2011-12-09 23:59:59", "2011-12-10")])
    reversals = empty_reversals(clean)
    train = build_features(clean, reversals, "2011-09-10")
    assert train.loc["1", "frequency"] == 0
    assert build_labels(clean, reversals, train.index, "2011-09-10", 90).loc["1", "actual_purchases"] == 2
    assert build_features(clean, reversals, "2011-12-09").loc["1", "frequency"] == 2
    assert purchase_cap(clean, reversals, "2011-09-10") == 10


def test_scoring_requires_complete_training_window():
    clean = make_lines([{"invoice_date": "2011-12-08"}])
    with pytest.raises(ModelError, match="coverage"):
        run_experiment("2011-12-09", 90, clean=clean, reversals=empty_reversals(clean), scoring=True)


@pytest.mark.skipif(not __import__("os").environ.get("POSTGRES_HOST"), reason="requires Compose Postgres")
def test_all_production_predictions_ignore_future_data():
    from db import database_engine, load_inputs
    engine = database_engine()
    try:
        clean, reversals, _ = load_inputs(engine)
    finally:
        engine.dispose()
    original = run_experiment("2011-12-09", 90, clean=clean, reversals=reversals, name="PROD", scoring=True)
    future = make_lines([{"customer_id": "future", "invoice_date": "2011-12-10", "line_value": 1e12}])
    extended = run_experiment("2011-12-09", 90, clean=pd.concat([clean, future]),
                              reversals=reversals, name="PROD", scoring=True)
    assert_frame_equal(original[1], extended[1], check_exact=True)
    assert_frame_equal(original[2], extended[2], check_exact=True)
    assert original[0]["params"]["purchase_cap"] == extended[0]["params"]["purchase_cap"]
