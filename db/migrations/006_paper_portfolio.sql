BEGIN;

CREATE SCHEMA IF NOT EXISTS paper;

CREATE TABLE IF NOT EXISTS paper.approval_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_date DATE NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalized_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'FINALIZED')),
    strategy_version TEXT NOT NULL DEFAULT 'v1',
    CONSTRAINT batches_finalized_requires_time
        CHECK (
            status <> 'FINALIZED'
            OR finalized_at IS NOT NULL
        )
);

CREATE TABLE IF NOT EXISTS paper.orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES paper.approval_batches(batch_id),
    symbol TEXT NOT NULL,
    signal_date DATE NOT NULL,
    entry_date DATE NOT NULL,
    entry_price NUMERIC(20,10) NOT NULL,
    atr_value NUMERIC(20,10) NOT NULL,
    candidate_status TEXT NOT NULL,
    strategy_version TEXT NOT NULL DEFAULT 'v1',

    proposed_quantity NUMERIC(20,6) NOT NULL,
    approved_quantity NUMERIC(20,6),

    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL'
        CHECK (status IN (
            'PENDING_APPROVAL',
            'APPROVED',
            'REJECTED',
            'EXECUTED',
            'CANCELLED'
        )),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,

    CONSTRAINT orders_quantity_positive
        CHECK (
            proposed_quantity > 0
            AND (
                approved_quantity IS NULL
                OR approved_quantity > 0
            )
        ),
    CONSTRAINT orders_execution_requires_approval
        CHECK (
            status <> 'EXECUTED'
            OR (
                approved_at IS NOT NULL
                AND executed_at IS NOT NULL
                AND approved_quantity IS NOT NULL
            )
        ),
    CONSTRAINT orders_unique_signal
        UNIQUE (batch_id, symbol, signal_date, strategy_version)
);

CREATE INDEX IF NOT EXISTS idx_paper_orders_batch
    ON paper.orders(batch_id);

CREATE INDEX IF NOT EXISTS idx_paper_orders_status
    ON paper.orders(status);

CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol_date
    ON paper.orders(symbol, signal_date);

CREATE TABLE IF NOT EXISTS paper.positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL UNIQUE REFERENCES paper.orders(order_id),
    symbol TEXT NOT NULL,
    entry_date DATE NOT NULL,
    entry_price NUMERIC(20,10) NOT NULL,
    quantity NUMERIC(20,6) NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'CLOSED')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    CONSTRAINT positions_quantity_positive
        CHECK (quantity > 0)
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol_status
    ON paper.positions(symbol, status);

CREATE TABLE IF NOT EXISTS paper.equity_daily (
    date DATE PRIMARY KEY,
    cash NUMERIC(20,4) NOT NULL,
    market_value NUMERIC(20,4) NOT NULL,
    equity NUMERIC(20,4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT paper_equity_non_negative
        CHECK (
            cash >= 0
            AND market_value >= 0
            AND equity >= 0
        )
);

COMMIT;
