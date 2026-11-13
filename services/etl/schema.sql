CREATE TABLE IF NOT EXISTS raw_transactions (
    invoice TEXT,
    stockcode TEXT,
    description TEXT,
    quantity BIGINT,
    invoice_date TIMESTAMP WITHOUT TIME ZONE,
    price DOUBLE PRECISION,
    customer_id TEXT,
    country TEXT,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    PRIMARY KEY (source_sheet, source_row)
);

CREATE TABLE IF NOT EXISTS clean_transactions (
    invoice TEXT NOT NULL,
    stockcode TEXT NOT NULL,
    description TEXT,
    quantity BIGINT NOT NULL CHECK (quantity > 0),
    invoice_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    price DOUBLE PRECISION NOT NULL CHECK (price > 0),
    customer_id TEXT NOT NULL,
    country TEXT,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    is_repeated_line BOOLEAN NOT NULL,
    line_value DOUBLE PRECISION NOT NULL CHECK (line_value > 0),
    PRIMARY KEY (source_sheet, source_row)
);

CREATE TABLE IF NOT EXISTS data_quality_report (
    rule TEXT PRIMARY KEY,
    unit TEXT NOT NULL,
    standalone_rows BIGINT NOT NULL CHECK (standalone_rows >= 0),
    removed_rows BIGINT NOT NULL CHECK (removed_rows >= 0),
    removed_line_value DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (removed_line_value >= 0)
);

ALTER TABLE data_quality_report ADD COLUMN IF NOT EXISTS
    removed_line_value DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (removed_line_value >= 0);

CREATE TABLE IF NOT EXISTS reversed_purchases (
    LIKE clean_transactions INCLUDING ALL,
    cancellation_invoice TEXT NOT NULL,
    cancellation_invoice_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    cancellation_source_sheet TEXT NOT NULL,
    cancellation_source_row INTEGER NOT NULL,
    gap_minutes DOUBLE PRECISION NOT NULL CHECK (gap_minutes > 0),
    UNIQUE (cancellation_source_sheet, cancellation_source_row)
);

CREATE TABLE IF NOT EXISTS excluded_stockcodes (
    stockcode TEXT PRIMARY KEY,
    row_count BIGINT NOT NULL CHECK (row_count > 0),
    sample_description TEXT
);

CREATE TABLE IF NOT EXISTS customer_rfm (
    customer_id TEXT PRIMARY KEY,
    frequency INTEGER NOT NULL CHECK (frequency >= 0),
    recency INTEGER NOT NULL CHECK (recency >= 0),
    "T" INTEGER NOT NULL CHECK ("T" >= recency),
    monetary_value DOUBLE PRECISION NOT NULL CHECK (monetary_value >= 0),
    cutoff_date DATE NOT NULL,
    CHECK (
        (frequency = 0 AND recency = 0 AND monetary_value = 0)
        OR (frequency > 0 AND monetary_value > 0)
    )
);
