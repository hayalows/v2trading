# V2 Trading

Research-first quantitative trading laboratory built around the recovered V2 M15 setup concept.

> **Status:** active research. **No live-money execution and no live buy/sell signals.** v0.4 showed that the frozen price-ranking signal does not currently survive independent executable relabeling. v0.5 is therefore focused on same-broker label reconstruction, not new predictive models.

## Core question

Can the recovered V2 structural setup be reproduced with execution labels that remain valid when entries, stops and targets are evaluated on the correct bid/ask side of the same broker feed?

Only after that question is answered does model optimization become meaningful.

## Recovered historical V2

The original project lived locally at `C:/Users/USER/Documents/strategy_lab_mvp` and was connected to MT5. Recovered reports describe a 2,227-trade 2020–July 2026 enriched ledger.

Historical report summary:

- 2,227 trades
- 48.72% win rate
- 0.656R average expectancy after recovered spread cost
- profit factor about 2.23
- max drawdown about 11.54R

These are historical research statistics, not expected live returns.

## v0.1 — recovered-ledger leakage audit

`m15_v2_setup_score` was found to equal realized `net_r` exactly and was blacklisted together with post-trade fields. A weaker but still interesting entry-time ranking signal remained after leakage removal.

## v0.2 — independent public-data proxy

An explicit proxy reconstructed:

`liquidity sweep -> BOS -> fresh POI -> 50% POI entry -> stop -> fixed 2.5R`

on independent public M15/M5 data for EURUSD, GBPUSD, XAUUSD and NAS100.

- 1,080 generated setups
- 1,022 resolved trades
- 53.03% win rate
- ~0.466R proxy expectancy
- PF ~1.78

The proxy is not presented as the unavailable original MT5 implementation.

See `reports/public_data/PUBLIC_DATA_PROXY_REPORT.md`.

## v0.3 — causal model stack

v0.3 removed entry-candle leakage, future economic-surprise leakage, macro publication-timing optimism and OOS boundary overlap.

Strict price/setup model, 2023–2025 pooled OOS:

- 566 trades
- AUC **0.713**
- all-trade proxy expectancy **+0.430R**
- q50 **+0.808R**
- q70 **+1.210R**

Economic-event and XAU macro/geopolitical overlays were rejected because they did not improve the frozen price baseline consistently.

See `reports/v03/V03_QUANT_RESEARCH_REPORT.md`.

## v0.4 — Execution First

v0.4 froze the v0.3 score and tested it against a deterministic score-stratified sample of real Dukascopy bid/ask ticks plus an independent XAUUSD M1 feed.

### Tick audit

- 64 score-stratified trades
- 61 clear executable labels
- 31 trusted low-friction labels
- 96.9% fill rate
- source M15/M5 vs tick agreement: **59.0%**
- frozen v0.3 price AUC on executable labels: **0.389**
- source expectancy on the same 61 trades: **+0.381R**
- executable score-stratified expectancy: **-0.612R**
- median fill spread: **0.153R**
- p90 fill spread: **0.655R**

Even the <=0.10R spread cohort only produced 0.338 AUC, so spread alone does not explain the failure.

### Independent XAU M1 check

- 44 OOS-prediction-overlap trades
- source vs M1 agreement: **52.3%**
- frozen price AUC on M1 labels: **0.378**

### v0.4 decision

**Live gate: FAIL.**

The current candle labels are not robust enough to be treated as executable ground truth, and the frozen ranking is not promoted or inverted after the negative result.

See `reports/v04/V04_EXECUTION_FIRST_REPORT.md`.

## v0.5 — Same-Broker Reconstruction

v0.5 addresses the main unresolved question from v0.4: were the disagreements caused by an invalid source simulator, or by comparing different brokers/data vendors?

The v0.5 pipeline exports from the original MT5 broker:

- M1, M5 and M15 bars;
- partitioned historical bid/ask ticks;
- symbol point/tick/contract/execution metadata;
- immutable SHA256 file hashes;
- bar/tick integrity diagnostics.

It then replays the recovered V2 ledger on that same feed using:

- ask for long entries and short exits;
- bid for short entries and long exits;
- actual stop-cross quotes for slippage;
- explicit ambiguous/no-fill/no-data labels;
- M1+recorded-spread only as a fallback when direct ticks are unavailable.

The pipeline refuses to create an executable-label training ledger unless a pre-registered integrity gate passes:

- >=200 clear direct-tick labels;
- >=100 trusted direct-tick labels;
- >=30 direct-tick labels per market;
- >=90% overall source-vs-same-broker-tick agreement;
- >=93% agreement in trusted labels;
- <=10% unresolved rate.

Passing v0.5 would approve **model rebuilding only**, not live trading.

Runbook: `docs/V05_SAME_BROKER_RUNBOOK.md`.

## Current acceptance state

```text
Recovered V2 historical report   -> RESEARCH EVIDENCE
Strict v0.3 price model          -> HISTORICAL RANKING SIGNAL ONLY
Economic-event overlay           -> REJECTED
XAU macro/geopolitical overlay   -> REJECTED
v0.4 cross-broker tick gate      -> FAILED
v0.4 independent XAU M1 gate     -> FAILED
v0.5 same-broker label gate      -> NOT RUN YET
Executable-label retraining      -> BLOCKED UNTIL v0.5 PASSES
Live-money execution             -> DISABLED
Live buy/sell signals            -> DISABLED
```

## Repository map

- `docs/RESEARCH_PLAN.md` — research design
- `docs/V05_SAME_BROKER_RUNBOOK.md` — same-broker Windows workflow
- `src/v2trading/` — leakage-safe feature/model/backtest code
- `scripts/public_data_v2_proxy.py` — explicit public-data proxy
- `scripts/v03_quant_stack.py` — causal v0.3 model stack
- `scripts/v04_tick_relabel.mjs` — cross-broker executable relabeler
- `scripts/v04_execution_analysis.py` — frozen-score execution test
- `scripts/v05_mt5_export.py` — original-broker M1/M5/M15/tick exporter
- `scripts/v05_verify_export.py` — SHA256 export verifier
- `scripts/v05_same_broker_relabel_runner.py` — same-broker executable replay
- `scripts/v05_label_gate.py` — pre-registered label-integrity gate
- `scripts/v05_prepare_training_ledger.py` — gated executable-label ledger builder
- `scripts/v05_run_same_broker.ps1` — one-command Windows workflow
- `reports/v03/` — v0.3 findings
- `reports/v04/` — v0.4 execution findings
- `web/` — lightweight research dashboard

## Research rule

A better backtest is not the goal. The goal is an edge that survives attempts to falsify it.
