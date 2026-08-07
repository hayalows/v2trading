# V2 Trading

Research-first quantitative trading laboratory built around the recovered V2 M15 setup concept.

> **Status:** active research. **No live-money execution and no live buy/sell signals.** v0.3 accepts the strict price-ranking model as a research baseline but fails the independent execution-validation gate.

## Core question

Given that the V2 engine has already produced a valid structural setup, can information available at that exact moment improve the estimated probability that the trade reaches its fixed 2.5R target before its stop, after realistic execution costs?

## What was recovered

The original project lived locally at `C:/Users/USER/Documents/strategy_lab_mvp` and was connected to MT5. The recovered Library data includes a 2,227-trade 2020–July 2026 enriched ledger with 132 fields.

Historical frozen-V2 summary:

- 2,227 trades
- 48.72% win rate
- 0.656R average expectancy after recovered spread cost
- profit factor about 2.23
- full-period max drawdown about 11.54R in the recovered report

## v0.1 recovered-ledger pre-test

A leakage audit found that `m15_v2_setup_score` equals `net_r` exactly. It is blacklisted together with realized/post-trade fields.

After removing outcome information, the first expanding-year model still showed useful but imperfect ranking power.

## v0.2 independent public-data proxy

Because the exact original V2 source and broker candles are not currently available, a separate explicit proxy reconstructs:

`liquidity sweep -> BOS -> fresh POI -> 50% POI entry -> stop -> fixed 2.5R`

It runs on independent public M15/M5 data for EURUSD, GBPUSD, XAUUSD and NAS100.

- 1,080 generated setups
- 1,022 resolved trades
- 53.03% win rate
- ~0.466R proxy expectancy
- PF ~1.78
- 242 setups required 5-minute sequencing checks

The proxy is **not** presented as the unavailable original MT5 implementation.

See `reports/public_data/PUBLIC_DATA_PROXY_REPORT.md`.

## v0.3 — causal models + execution falsification

v0.3 removes two additional sources of timestamp optimism:

- the model cannot use the entry candle's eventual close/volume; price state comes from completed M15 bars only;
- a pre-release trade cannot see an economic announcement's future actual/surprise value.

It also lags daily macro data, conservatively publication-lags monthly geopolitical-risk data, purges trades overlapping OOS year boundaries, and prevents duplicate model-output joins.

### Strict price/setup model

2023–2025 pooled OOS:

- 566 trades
- AUC **0.713**
- Brier **0.215**
- all-trade proxy expectancy **+0.430R**
- pooled q50 cohort: **+0.808R**
- pooled q70 cohort: **+1.210R**

The stricter AUC is lower than the earlier v0.2 headline, which is expected after removing information that was not definitely available at entry. The ranking signal survives.

### Context layers

Economic-event overlay:

- **REJECTED as an incremental filter**
- fixed 80/20 price+event blend worsened AUC from 0.713 to 0.707

XAUUSD macro/geopolitical overlay:

- **REJECTED as an incremental filter**
- 2025 was promising, but 2023/2024 were unstable and the fixed blend worsened aggregate AUC/calibration

### Execution audit

Independent XAUUSD M1 replay:

- 169 overlapping trades audited
- 92.9% adjusted fill rate
- only **55.3%** agreement between source M15/M5 win/loss outcome and independent M1 outcome

Targeted Dukascopy bid/ask tick replay:

- 16 stratified windows
- 87.5% adjusted fill rate
- only **53.8%** win/loss agreement in comparable trades
- median observed spread ≈ **0.55R** of planned risk
- p90 observed spread ≈ **2.27R**

Therefore the historical R figures remain **proxy research statistics, not expected live returns**. The execution gate fails until labels can be reproduced on broker-appropriate lower-timeframe/bid-ask data.

See `reports/v03/V03_QUANT_RESEARCH_REPORT.md` and `reports/v03/v03_summary.json`.

## Current acceptance state

```text
V2 structural setup engine       -> RESEARCH
Strict price meta-model          -> ACCEPTED RESEARCH BASELINE
Economic-event overlay           -> REJECTED
XAU macro/geopolitical overlay   -> REJECTED
Independent M1 execution gate    -> FAILED
Bid/ask tick execution gate      -> FAILED
Live-money execution             -> DISABLED
Live buy/sell signals            -> DISABLED
```

## Repository map

- `docs/RESEARCH_PLAN.md` – full research design
- `docs/DATA_SOURCES.md` – market/macro/news source plan
- `docs/MODEL_CARD.md` – model limitations
- `src/v2trading/` – leakage-safe feature/model/backtest code
- `scripts/run_recovered_ledger_experiment.py` – recovered-ledger experiment
- `scripts/public_data_v2_proxy.py` – explicit public-data V2 proxy engine
- `scripts/v03_quant_stack.py` – completed-bar price, causal event and gold macro research stack
- `scripts/v03_postprocess.py` – duplicate-safe model combination and acceptance decisions
- `scripts/v03_execution_audit.py` – independent XAUUSD M1 replay
- `scripts/v03_tick_audit.mjs` – targeted Dukascopy bid/ask replay
- `.github/workflows/v03-quant-research.yml` – reproducible v0.3 workflow
- `reports/public_data/` – v0.2 independent proxy findings
- `reports/v03/` – v0.3 findings and frozen summaries
- `web/` – lightweight research dashboard

## Next research gate

The next version should be **execution-first**, not a larger AI model:

1. rebuild labels from bid/ask or conservative broker-appropriate M1 data;
2. model `spread / risk` and genuine fill probability as first-class variables;
3. reject geometrically tight setups whose planned stop is not large relative to transaction friction;
4. retrain the price meta-model only after execution-validated labels exist;
5. add Deflated Sharpe Ratio, CSCV/Probability of Backtest Overfitting and a frozen experiment registry before another model is promoted.

## Research rule

A better backtest is not the goal. The goal is an edge that survives attempts to falsify it.
