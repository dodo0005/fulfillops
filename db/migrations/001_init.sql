-- 001_init: core schema. The constraints here enforce the invariants (see docs/ADR-001.md).

CREATE TABLE products (
    sku              TEXT PRIMARY KEY,
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0)
);

CREATE TABLE inventory (
    sku        TEXT PRIMARY KEY REFERENCES products (sku),
    available  INTEGER NOT NULL CHECK (available >= 0),          -- never negative stock
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    order_id        UUID PRIMARY KEY,
    idempotency_key TEXT NOT NULL,
    request_hash    CHAR(64) NOT NULL,
    customer_id     TEXT NOT NULL CHECK (char_length(customer_id) BETWEEN 1 AND 64),
    status          TEXT NOT NULL
                    CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    total_cents     INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    CONSTRAINT orders_idempotency_key_unique UNIQUE (idempotency_key)  -- one key -> one order
);

CREATE TABLE order_items (
    order_id         UUID NOT NULL REFERENCES orders (order_id),
    sku              TEXT NOT NULL REFERENCES products (sku),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0),
    PRIMARY KEY (order_id, sku)                                 -- lines are aggregated per SKU
);

CREATE TABLE jobs (
    job_id          UUID PRIMARY KEY,
    order_id        UUID NOT NULL REFERENCES orders (order_id),
    status          TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'done', 'dead')),
    attempts        INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts    INTEGER NOT NULL CHECK (max_attempts >= 1),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_by       TEXT,
    locked_until    TIMESTAMPTZ,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT jobs_order_id_unique UNIQUE (order_id)           -- one job per order
);

CREATE INDEX jobs_status_next_attempt_idx ON jobs (status, next_attempt_at);

CREATE TABLE receipts (
    order_id     UUID PRIMARY KEY REFERENCES orders (order_id), -- an order completes at most once
    completed_by TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
