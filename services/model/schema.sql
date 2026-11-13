CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {schema}.model_runs (
    run_id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    test_cutoff DATE NOT NULL,
    train_cutoff DATE NOT NULL,
    window_days INTEGER NOT NULL CHECK (window_days > 0),
    n_train INTEGER NOT NULL,
    n_test INTEGER NOT NULL,
    base_rate_train DOUBLE PRECISION NOT NULL,
    base_rate_test DOUBLE PRECISION,
    random_seed INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    params JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS {schema}.model_metrics (
    run_id TEXT NOT NULL REFERENCES {schema}.model_runs(run_id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    metric TEXT NOT NULL,
    segment TEXT NOT NULL,
    value DOUBLE PRECISION,
    PRIMARY KEY (run_id, model, metric, segment)
);

CREATE TABLE IF NOT EXISTS {schema}.customer_predictions (
    run_id TEXT NOT NULL REFERENCES {schema}.model_runs(run_id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    "p_purchase_N" DOUBLE PRECISION NOT NULL CHECK ("p_purchase_N" BETWEEN 0 AND 1),
    "expected_purchases_N" DOUBLE PRECISION,
    expected_order_value DOUBLE PRECISION NOT NULL CHECK (expected_order_value > 0),
    "expected_value_N" DOUBLE PRECISION NOT NULL CHECK ("expected_value_N" >= 0),
    actual_purchased INTEGER CHECK (actual_purchased IN (0, 1)),
    actual_purchases INTEGER CHECK (actual_purchases >= 0),
    actual_spend DOUBLE PRECISION CHECK (actual_spend >= 0),
    p_alive DOUBLE PRECISION CHECK (p_alive BETWEEN 0 AND 1),
    "bgnbd_clv_N" DOUBLE PRECISION,
    PRIMARY KEY (run_id, model, customer_id)
);

-- Backward-compatible migration: outcomes are unavailable for production scoring.
ALTER TABLE {schema}.model_runs ALTER COLUMN base_rate_test DROP NOT NULL;
ALTER TABLE {schema}.customer_predictions ALTER COLUMN actual_purchased DROP NOT NULL;
ALTER TABLE {schema}.customer_predictions ALTER COLUMN actual_purchases DROP NOT NULL;
ALTER TABLE {schema}.customer_predictions ALTER COLUMN actual_spend DROP NOT NULL;
