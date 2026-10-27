BEGIN;

CREATE OR REPLACE FUNCTION paper.approve_order(
    p_order_id UUID,
    p_approved_quantity NUMERIC
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE paper.orders
    SET
        status = 'APPROVED',
        approved_quantity = p_approved_quantity,
        approved_at = now()
    WHERE order_id = p_order_id
      AND status = 'PENDING_APPROVAL';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Order % cannot be approved from its current status',
            p_order_id;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION paper.reject_order(
    p_order_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE paper.orders
    SET status = 'REJECTED'
    WHERE order_id = p_order_id
      AND status = 'PENDING_APPROVAL';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Order % cannot be rejected from its current status',
            p_order_id;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION paper.execute_order(
    p_order_id UUID,
    p_execution_price NUMERIC,
    p_execution_date DATE
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_quantity NUMERIC;
    v_symbol TEXT;
    v_entry_price NUMERIC;
BEGIN
    SELECT
        approved_quantity,
        symbol,
        entry_price
    INTO
        v_quantity,
        v_symbol,
        v_entry_price
    FROM paper.orders
    WHERE order_id = p_order_id
      AND status = 'APPROVED'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Order % cannot be executed from its current status',
            p_order_id;
    END IF;

    UPDATE paper.orders
    SET
        status = 'EXECUTED',
        executed_at = now()
    WHERE order_id = p_order_id;

    INSERT INTO paper.positions (
        order_id,
        symbol,
        entry_date,
        entry_price,
        quantity
    )
    VALUES (
        p_order_id,
        v_symbol,
        p_execution_date,
        p_execution_price,
        v_quantity
    );
END;
$$;

COMMIT;
