# BVB Info — Context proiect

## Scop
Sistem homelab pentru colectarea datelor BVB, generarea semnalelor,
salvarea tranzacțiilor, analiza riscului și monitorizare.

## Componente
- bvb-info: colectare și API date BVB
- PostgreSQL: stocarea datelor normalizate și a semnalelor
- bvb_daily.sh: orchestratorul zilnic
- portfolio_metrics.py: calculul metricilor de portofoliu
- Grafana: vizualizare equity, drawdown și distribuția pierderilor
- Home Assistant / MQTT: alertare și senzori

## Tabel strategy_trades
- id: identificator unic
- symbol: simbolul BVB
- entry_date: data intrării în poziție
- exit_date: data ieșirii din poziție
- entry_price: prețul de intrare
- exit_price: prețul de ieșire
- volume_ratio: volum / media volumului pe 20 zile
- signal_type: tipul semnalului
- strategy_version: versiunea strategiei
- created_at: momentul înregistrării

Reguli:
- Tabelul păstrează tranzacțiile închise.
- O tranzacție este unică prin symbol, entry_date și strategy_version.
- Metricile de portofoliu folosesc acest tabel.
- Baseline-ul și stop-loss -8% se calculează pe aceleași tranzacții.

## Flux zilnic
1. Cron rulează bvb_daily.sh luni-vineri la 18:30.
2. Scriptul importă snapshot-ul BVB în PostgreSQL.
3. Strategia calculează semnalele.
4. Semnalele noi sunt salvate în strategy_signals_log.
5. Sistemul exportă output/new_signals.json.

## Comenzi utile
```bash
cd ~/bvb-info
source .venv/bin/activate
python3 bvb_daily.sh
tail -n 30 logs/cron.log
cat output/new_signals.json
```

## Metrici
- Cost total per tranzacție: 0.5%.
- Ieșire standard: 5 zile.
- Baseline: fără stop-loss.
- Test curent: stop-loss -8%.
- Metrici: Win Rate, Net Profit Factor, Maximum Drawdown,
  distribuția randamentelor și numărul tranzacțiilor oprite.

## Reguli
- Nu modificăm datele brute.
- Testăm modificările izolat, pe aceleași tranzacții.
- Baseline-ul rămâne neatins până la validare statistică.
- Orice decizie se bazează pe Net Profit Factor net,
  Maximum Drawdown și numărul suficient de tranzacții.

## Strategia v1.0 - BET Overextended Mean Reversion

### Semnal de intrare în ziua D
Toate condițiile trebuie îndeplinite simultan:
1. Close[D] < SMA20[D] * 0.95
2. Close[D] > Open[D]
3. RSI14[D] > 35
4. Volume[D] / SMA20_Volume[D] >= 1.5
5. Volume[D] > 0

### Execuție
- Intrare: Open[D+1]
- Ieșire standard: Open[D+6], adică după 5 zile tranzacționate
- Cost total: 0.5% per tranzacție
- Stop-loss testat separat: -8% net
- Perioadă inițială: 2021-01-01 până la ultima dată disponibilă

### Reguli de integritate
- Indicatorii folosesc doar date disponibile până la D.
- Nu se folosește informația din D+1 pentru semnalul din D.
- Nu se intră din nou pe același simbol cât timp poziția este deschisă.
- Datele trebuie ajustate pentru evenimente corporative înainte de calcul.

## Structura tabelului daily_prices

| Coloană | Tip | Semnificație |
|---|---|---|
| id | integer | Identificator unic |
| symbol | varchar | Simbolul BVB |
| date | date | Data ședinței de tranzacționare |
| price | double precision | Prețul de închidere / ultimul preț |
| var_pct | double precision | Variația procentuală |
| open | double precision | Prețul de deschidere |
| max | double precision | Maximul zilei |
| min | double precision | Minimul zilei |
| avg | double precision | Prețul mediu |
| value_ron | double precision | Valoarea tranzacțiilor în RON |
| volume | double precision | Volumul tranzacționat |
| trades | double precision | Numărul tranzacțiilor |
| market | varchar | Piața / segmentul |
| last_time | varchar | Ora ultimei tranzacții |
| source | varchar | Sursa datelor |

### Mapare pentru strategie
- Data: date
- Simbol: symbol
- Open: open
- High: max
- Low: min
- Close: price
- Volum: volume

### Reguli
- Nu folosim coloana trade_date; numele real este date.
- Pentru Close folosim coloana price.
- Pentru High folosim max, iar pentru Low folosim min.
- Volume Ratio = volume / media volumului din ultimele 20 de zile disponibile.

## Stadiu date istorice
- daily_prices conține în principal snapshot-uri recente, nu istoric complet.
- TLV are un singur rând la 2026-10-12, cu open și volume NULL.
- Nu se poate genera un backtest valid până la importul istoricului.
- Următorul pas: backfill istoric BVB în daily_prices.
- După backfill: validare pe TLV, FP și SNP, apoi generarea tranzacțiilor.

## Situația istoricului
- bvb-data-worker are doar snapshot-uri zilnice din octombrie 2026.
- Fișierele CSV conțin OHLCV complet pentru ziua respectivă.
- Nu există încă istoric TradeVille importat.
- Pentru backtest 2021-2026 este necesar un backfill istoric.
- Candidatul curent este API-ul bvb-info: /api/v1/prices.
- Înainte de implementare, se verifică empiric prima dată disponibilă.

## MQTT / Home Assistant integration

### Broker
- Host: 192.168.1.186
- Port: 1883
- User: bvbinfo
- Password: stored in project settings / environment, never committed

### Topics
- ETL status: homelab/bvb-info/update/status
- Strategy status: homelab/bvb-info/strategy/status
- MQTT discovery config: homeassistant/sensor/bvb_strategy/status/config

### Home Assistant entities
- BVB Info - Ultima actualizare
  - state_topic: homelab/bvb-info/update/status
- BVB Strategy - Status
  - state_topic: homelab/bvb-info/strategy/status
  - created via MQTT discovery
  - value_template: {{ value_json.status }}
  - attributes: full strategy JSON payload

### Publishing rules
- Use publish_json() for normal project topics.
- publish_json() automatically prefixes topics with homelab/bvb-info.
- MQTT discovery messages must be published directly to homeassistant/...
  and must not use the project topic prefix.
- Strategy payload uses retain=True and QoS 1.

### Strategy payload example
{
  "strategy": "bvb_overextended_mean_reversion",
  "version": "v1.0_stop8",
  "status": "test",
  "total_trades": 43,
  "new_signals": 0,
  "win_rate": 0.6512,
  "average_net_return": 0.0278,
  "net_profit_factor": 3.2306,
  "max_drawdown": -0.08,
  "stop_loss": -0.08,
  "stopped_out_trades": 3
}

- Daily cron at 09:00 runs:
  build_strategy_status.py && publish_strategy.py strategy_status.json
- build_strategy_status.py reads:
  ~/bvb-data-worker/output/portfolio_metrics_history_stop8.json
- It writes:
  ~/bvb-info/strategy_status.json

## Cron jobs

### 1. Daily BVB ETL
- Schedule: 18:30, Monday to Friday
- Command:
  cd /home/bvb/bvb-info && ./bvb_daily.sh >> logs/cron.log 2>&1
- Purpose:
  Runs the daily BVB data update pipeline.

### 2. Daily strategy status publication
- Schedule: 09:00, every day
- Command:
  cd /home/bvb/bvb-info && .venv/bin/python build_strategy_status.py && .venv/bin/python publish_strategy.py strategy_status.json >> /home/bvb/bvb-info/strategy_publish.log 2>&1
- Purpose:
  1. Reads ~/bvb-data-worker/output/portfolio_metrics_history_stop8.json
  2. Writes ~/bvb-info/strategy_status.json
  3. Publishes it to MQTT topic:
     homelab/bvb-info/strategy/status
  4. Home Assistant updates sensor:
     BVB Strategy - Status

### Log files
- ETL log:
  ~/bvb-info/logs/cron.log
- Strategy publication log:
  ~/bvb-info/strategy_publish.log

## Final strategy automation flow

### Daily flow
1. bvb_daily.sh runs at 18:30, Monday to Friday.
2. It imports daily prices into bvb_info.
3. It exports new signals to:
   ~/bvb-info/output/new_signals.json
4. At 09:00 daily, cron runs:
   build_strategy_status.py && publish_strategy.py strategy_status.json
5. build_strategy_status.py reads:
   - ~/bvb-data-worker/output/portfolio_metrics_history_stop8.json
   - ~/bvb-info/output/new_signals.json
6. It writes:
   ~/bvb-info/strategy_status.json
7. publish_strategy.py publishes to:
   homelab/bvb-info/strategy/status
8. Home Assistant updates:
   BVB Strategy - Status

### Current behavior
- total_trades, win_rate, net_profit_factor, max_drawdown and
  stopped_out_trades come from the historical stop8 portfolio metrics.
- new_signals comes from the daily signals export.
- If no new signals exist, new_signals is 0.
- The historical metrics file is currently static; it is not regenerated
  automatically by the daily cron.

### Known limitation
- portfolio_metrics_history_stop8.json was generated manually.
- There is no dedicated script yet that regenerates it automatically.
- Future improvement: create a metrics generator that reads
  trades_history.csv, applies stop-loss logic correctly and writes
  portfolio_metrics_history_stop8.json before strategy status publication.

## Architecture correction — final state

### Scheduling correction
- Strategy status publication moved from 09:00 next day to 19:00 same day.
- New schedule:
  - 18:30, Monday-Friday: bvb_daily.sh
  - 19:00, Monday-Friday: build_strategy_status.py && publish_strategy.py
- This avoids publishing new signals after the next market open.

### Project decoupling correction
- bvb-info no longer reads directly from ~/bvb-data-worker/output/.
- A local snapshot is stored at:
  ~/bvb-info/output/portfolio_metrics_history_stop8.json
- build_strategy_status.py reads this local snapshot.
- This removes the fragile cross-project file dependency.

### Current final flow
1. 18:30: bvb_daily.sh imports daily prices and exports new_signals.json.
2. 19:00: build_strategy_status.py reads:
   - ~/bvb-info/output/portfolio_metrics_history_stop8.json
   - ~/bvb-info/output/new_signals.json
3. It writes ~/bvb-info/strategy_status.json.
4. publish_strategy.py publishes to:
   homelab/bvb-info/strategy/status
5. Home Assistant updates:
   BVB Strategy - Status

### Remaining limitation
- portfolio_metrics_history_stop8.json is still a static snapshot.
- It must be refreshed manually or by a future metrics generator.
- Future improvement: generate metrics automatically from trades_history.csv
  with correct stop-loss simulation and transaction costs.
