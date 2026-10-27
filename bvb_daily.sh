#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$HOME/bvb-info"
LOG_DIR="$BASE_DIR/logs"
OUTPUT_DIR="$BASE_DIR/output"
LOG_FILE="$LOG_DIR/bvb_daily_$(date +%F).log"

mkdir -p "$LOG_DIR" "$OUTPUT_DIR"

set -a
source "$BASE_DIR/.env"
set +a

PSQL_URL="${BVB_DATABASE_URL/+psycopg2/}"

log() {
    echo "[$(date '+%F %T')] $*" | tee -a "$LOG_FILE"
}

log "Pornire bvb_daily"

trap '
    rc=$?
    if [ "$rc" -ne 0 ]; then
        log "ESEC bvb_daily (exit=$rc)"
        .venv/bin/python publish_failure.py "$rc" || true
    fi
' EXIT

# 1. Importul bvb-info
# Această etapă rămâne momentan un placeholder.
# Când îmi spui comanda reală de import, o adăugăm aici.

cd "$BASE_DIR" && .venv/bin/python -m bvb_scraper.main prices >> "$LOG_FILE" 2>&1
log "Import bvb-info finalizat"

# 2. Salvează semnalele noi în jurnal
psql "$PSQL_URL" -v ON_ERROR_STOP=1 <<'SQL' >> "$LOG_FILE" 2>&1
INSERT INTO strategy_signals_log (
    symbol,
    signal_date,
    entry_date,
    entry_price,
    rsi_14,
    volume_ratio_20d,
    candidate_status,
    strategy_version
)
SELECT
    symbol,
    signal_date,
    next_date,
    next_close,
    rsi_14,
    volume_ratio_20d,
    candidate_status,
    'v1'
FROM v_trade_candidates
WHERE candidate_status IN ('confirmed_reversal', 'pending_confirmation')
  AND volume_ratio_20d >= 2.0
  AND signal_date = (
      SELECT MAX(date)
      FROM v_ohlcv_clean
  )
ON CONFLICT (symbol, signal_date, strategy_version) DO NOTHING;
SQL

# 3. Exportă semnalele noi în JSON
psql "$PSQL_URL" -At -v ON_ERROR_STOP=1 -c "
SELECT COALESCE(
    json_agg(
        json_build_object(
            'symbol', symbol,
            'signal_date', signal_date,
            'entry_date', next_date,
            'entry_price', next_close,
            'rsi_14', rsi_14,
            'volume_ratio_20d', volume_ratio_20d,
            'candidate_status', candidate_status
        )
    ),
    '[]'::json
)
FROM (
    SELECT *
    FROM v_trade_candidates
    WHERE candidate_status IN ('confirmed_reversal', 'pending_confirmation')
      AND volume_ratio_20d >= 2.0
      AND signal_date = (
          SELECT MAX(date)
          FROM v_ohlcv_clean
      )
) AS new_signals;
" > "$OUTPUT_DIR/new_signals.json"

log "Semnale exportate în $OUTPUT_DIR/new_signals.json"
log "Finalizare bvb_daily"
