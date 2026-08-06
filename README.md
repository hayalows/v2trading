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

## v0.1 pre-test

A strict leakage audit found that `m15_v2_setup_score` equals `net_r` exactly. It is now blacklisted.

After removing realized/post-trade fields, an expanding-year walk-forward experiment on 2023–2026 produced:

- 1,128 OOS V2 trades
- LightGBM pooled AUC: ~0.648
- all V2 OOS expectancy: ~0.648R
- training-median score cohort (q50): 613 trades, ~0.987R expectancy
- training-70th-percentile score cohort (q70): 395 trades, ~1.211R expectancy

These are research results, not a live-trading claim. The next major checks are raw-candle reproduction, M1/tick fill sequencing, point-in-time macro/news features, leave-symbol-out validation, and a frozen live shadow period.

## Repository map

- `docs/RESEARCH_PLAN.md` – full research design
- `docs/DATA_SOURCES.md` – market/macro/news source plan
- `docs/MODEL_CARD.md` – current model and limitations
- `src/v2trading/` – leakage-safe feature/model/backtest code
- `scripts/run_recovered_ledger_experiment.py` – reproducible recovered-ledger experiment
- `scripts/mt5_export.py` – broker-candle export script for the original Windows/MT5 machine
- `scripts/news_features.py` – recent GDELT research collector
- `reports/` – walk-forward, stress and pre-test outputs
- `web/` – lightweight research dashboard

## Run the recovered-ledger experiment

```bash
pip install -r requirements.txt
PYTHONPATH=src python scripts/run_recovered_ledger_experiment.py path/to/FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv reports
```

## Research rule

A better backtest is not the goal. The goal is an edge that survives attempts to falsify it.
