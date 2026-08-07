# V2 Trading

Research-first quantitative trading laboratory built around the frozen V2 M15 setup engine.

> **Status:** active research. No live-money execution. The original V2 logic remains frozen and separate from experimental filters, models, macro features, news features, and execution research.

## Core question

Given that the frozen V2 engine has already produced a valid setup, can information available at that moment improve the estimated probability that the trade reaches its fixed 2.5R target before its stop, after realistic costs?

## What was recovered

The original project lived locally at `C:/Users/USER/Documents/strategy_lab_mvp` and was connected to MT5. The recovered Library data includes a 2,227-trade 2020–July 2026 enriched ledger with 132 fields.

Historical frozen-V2 summary:

- 2,227 trades
- 48.72% win rate
- 0.656R average expectancy after recovered spread cost
- profit factor about 2.23
- full-period max drawdown about 11.54R in the recovered report

## v0.1 recovered-ledger pre-test

A strict leakage audit found that `m15_v2_setup_score` equals `net_r` exactly. It is now blacklisted.

After removing realized/post-trade fields, an expanding-year walk-forward experiment on 2023–2026 produced:

- 1,128 OOS V2 trades
- LightGBM pooled AUC: ~0.648
- all V2 OOS expectancy: ~0.648R
- training-median score cohort (q50): 613 trades, ~0.987R expectancy
- training-70th-percentile score cohort (q70): 395 trades, ~1.211R expectancy

## v0.2 independent public-data proxy

Because the exact original V2 source and broker candles are not currently available, a separate proxy experiment reconstructs the core idea with explicit rules and runs it on public Hugging Face M15/M5 data for EURUSD, GBPUSD, XAUUSD and NAS100.

The proxy is intentionally **not** presented as the exact historical V2 implementation.

Independent public-data result:

- 1,080 generated setups
- 1,022 resolved trades after excluding 58 remaining intrabar ambiguities
- 53.03% win rate
- ~0.466R baseline expectancy
- PF ~1.78
- 242 setups required 5-minute data to resolve M15 stop/target ordering

Expanding-year 2023–2025 meta-model result:

- 566 OOS trades
- pooled AUC ~0.729 with the first full feature set
- q50: 295 trades, ~0.820R expectancy
- q70: 170 trades, ~1.130R expectancy

Ablation found that price/setup-only features ranked slightly better than the first raw calendar implementation, so macro/news remains a separate research layer rather than being forced into the core model.

See `reports/public_data/PUBLIC_DATA_PROXY_REPORT.md` for the full methodology, cost stress and limitations.

## Repository map

- `docs/RESEARCH_PLAN.md` – full research design
- `docs/DATA_SOURCES.md` – market/macro/news source plan
- `docs/MODEL_CARD.md` – current model and limitations
- `src/v2trading/` – leakage-safe feature/model/backtest code
- `scripts/run_recovered_ledger_experiment.py` – reproducible recovered-ledger experiment
- `scripts/public_data_v2_proxy.py` – explicit public-data V2 proxy engine
- `scripts/public_data_v2_proxy_runner.py` – pandas/string-safe research runner
- `scripts/public_data_ablation.py` – price vs event-context ablation
- `scripts/mt5_export.py` – broker-candle export script for the original Windows/MT5 machine
- `scripts/news_features.py` – recent GDELT research collector
- `reports/public_data/` – independent proxy findings
- `reports/` – recovered-ledger walk-forward, stress and pre-test outputs
- `web/` – lightweight research dashboard

## Run the recovered-ledger experiment

```bash
pip install -r requirements.txt
PYTHONPATH=src python scripts/run_recovered_ledger_experiment.py path/to/FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv reports
```

## Research rule

A better backtest is not the goal. The goal is an edge that survives attempts to falsify it.
