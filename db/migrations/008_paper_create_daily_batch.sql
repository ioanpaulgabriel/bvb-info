BEGIN;

CREATE OR REPLACE FUNCTION paper.create_daily_batch(
    p_signal_date DATE,
    p_cash NUMERIC,
    p_risk_per_trade NUMERIC DEFAULT 0.01,
    p_stop_atr_multiplier NUMERIC DEFAULT 3.0
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_batch_id UUID;
    v_signal_count INTEGER;
BEGIN
    IF p_cash <= 0 THEN
        RAISE EXCEPTION 'Cash must be positive';
    END IF;

    IF p_risk_per_trade <= 0 OR p_risk_per_trade > 0.05 THEN
        RAISE EXCEPTION 'Risk per trade must be between 0 and 5 percent';
    END IF;

    IF p_stop_atr_multiplier <= 0 THEN
        RAISE EXCEPTION 'Stop ATR multiplier must be positive';
    END IF;

    SELECT COUNT(*)
    INTO v_signal_count
    FROM public.v_trade_candidates
    WHERE signal_date = p_signal_date
      AND candidate_status IN (
          'confirmed_reversal',
          'pending_confirmation'
      )
      AND volume_ratio_20d >= 2.0;

    IF v_signal_count = 0 THEN
        RAISE EXCEPTION 'No eligible signals for date %', p_signal_date;
    END IF;

    INSERT INTO paper.approval_batches (
        signal_date
    )
    VALUES (
        p_signal_date
    )
    ON CONFLICT (signal_date)
    DO UPDATE SET
        created_at = now()
    RETURNING batch_id
    INTO v_batch_id;

    INSERT INTO paper.orders (
        batch_id,
        symbol,
        signal_date,
        entry_date,
        entry_price,
        atr_value,
        candidate_status,
        proposed_quantity
    )
    SELECT
        v_batch_id,
        candidate.symbol,
        candidate.signal_date,
        candidate.next_date,
        candidate.next_close,
        candidate.rsi_14,
        candidate.candidate_status,
        FLOOR(
            (
                p_cash * p_risk_per_trade
            ) / (
                p_stop_atr_multiplier * candidate.rsi_14
            )
        )
    FROM public.v_trade_candidates AS candidate
    WHERE candidate.signal_date = p_signal_date
      AND candidate.candidate_status IN (
          'confirmed_reversal',
          'pending_confirmation'
      )
      AND candidate.volume_ratio_20d >= 2.0
    ON CONFLICT (batch_id, symbol, signal_date, strategy_version)
    DO NOTHING;

    RETURN v_batch_id;
END;
$$;

COMMIT;
