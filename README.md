# V2 Trading

Research-first quantitative trading laboratory built around the recovered V2 M15 setup concept.

> **Status:** active research. **No live-money execution and no live buy/sell signals.** v0.4 showed that the frozen price-ranking signal does not currently survive independent executable relabeling. v0.5 remains the same-broker validation gate, while **V2 Research Lab v1** now observes live/recent market state prospectively using a zero-cost public-data stack.

## V2 Research Lab v1 — live market observation

The project now has a live research layer that works without MT5, a paid data API, or a new market-data account.

Current stack:

- Supabase Free — database, Edge Function and five-minute Cron refresh;
- Vercel — public research interface;
- Yahoo Finance public chart endpoints — completed-bar structure/history;
- exchangerate.dev anonymous endpoint — EURUSD and GBPUSD reference rates when available;
- goldprice.dev anonymous endpoint — XAUUSD spot reference and bid/ask when available;
- TradingView free widget — interactive visual chart only, separate from research calculations.

The live lab currently covers:

- EURUSD
- GBPUSD
- XAUUSD
- US30 / Dow context

Because there is no broker execution feed, the lab is deliberately a **market-state and formation monitor**, not a signal engine.

It calculates:

- D1, H4, H1 and M15 trend + strength;
- trending/ranging/transition/volatility regimes;
- recent swing and liquidity context;
- previous-day levels;
- M15 ATR and recent-range position;
- a deterministic V2 formation state machine from liquidity proximity through sweep, BOS, fresh POI and research entry-zone proximity;
- source freshness and proxy warnings.

The formation states are:

```text
0  NO_SETUP
1  LIQUIDITY_NEARBY
2  POI_USED
3  SWEEP_CONFIRMED
4  WAITING_FOR_BOS
5  BOS_CONFIRMED
6  FRESH_POI_IDENTIFIED
7  APPROACHING_POI
8  ENTRY_ZONE_REACHED   # research state, not a trade signal
```

XAUUSD structure currently uses COMEX gold futures as a free proxy while an anonymous XAUUSD spot reference is used when available. US30 uses E-mini Dow futures as a free extended-hours proxy for broker US30 CFDs. These limitations are shown in the UI and API.

The lab writes timestamped state observations to Supabase so future research can measure stage transition rates and outcomes prospectively rather than fitting only to recovered historical trades.

Architecture and methodology: `docs/LIVE_RESEARCH_LAB_V1.md`.

## Core validation question

Can the recovered V2 structural setup be reproduced with execution labels that remain valid when entries, stops and targets are evaluated on the correct bid/ask side of the same broker feed?

Only after that question is answered does probability-model optimization become meaningful. The live research lab is useful in parallel because trend/structure observation does not require us to pretend the old execution labels are valid.

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
Live Research Lab v1             -> ACTIVE OBSERVATION / RESEARCH ONLY
Executable-label retraining      -> BLOCKED UNTIL VALID LABELS EXIST
Live-money execution             -> DISABLED
Live buy/sell signals            -> DISABLED
```

## Repository map

- `docs/RESEARCH_PLAN.md` — research design
- `docs/LIVE_RESEARCH_LAB_V1.md` — zero-cost live lab architecture and methodology
- `docs/V05_SAME_BROKER_RUNBOOK.md` — same-broker Windows workflow
- `src/v2trading/` — leakage-safe feature/model/backtest code
- `supabase/functions/market-lab/index.ts` — live market-state engine
- `supabase/migrations/20260807_live_research_lab.sql` — live lab database schema and RLS source
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
- `web/` — live V2 Research Lab interface

## Research rule

A better backtest is not the goal. The goal is an edge that survives attempts to falsify it.
