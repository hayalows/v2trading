# V2 Quant v0.5 — Same-Broker Reconstruction Runbook

## Why this exists

v0.4 showed that the public-source M15/M5 outcomes were not stable when the same trades were replayed on an independent bid/ask feed. That does not distinguish between two possibilities:

1. the V2 backtest labels were optimistic or execution-invalid; or
2. cross-broker/source differences were large enough to destroy label comparability.

v0.5 resolves that question by using the **same MT5 broker feed** for the historical V2 levels and for the lower-timeframe execution replay.

No new ML model is allowed until this label-integrity gate passes.

## What v0.5 exports

For each research symbol (`EURUSD`, `GBPUSD`, `XAUUSD`, `US30` by default):

- full-period M1 bars;
- full-period M5 bars;
- full-period M15 bars;
- bid/ask ticks on the UTC dates required to replay recovered trades, with one-day boundary padding;
- broker symbol mapping;
- digits, point, tick size/value, contract size, stop/freeze levels, volume rules and swap metadata;
- bar-integrity diagnostics;
- daily tick diagnostics;
- SHA256 for every exported file.

The targeted tick mode is the default because exporting every tick for four markets over more than six years can be unnecessarily large. `v05_mt5_export.py` still exists for a full continuous tick archive when one is specifically needed.

Account login and account-holder name are intentionally not exported.

## Prerequisites

Use the Windows machine that has the original research broker's MetaTrader 5 terminal installed and logged in.

```powershell
cd C:\path\to\v2trading
python -m pip install -r requirements-mt5.txt
```

The MT5 Python package communicates with the locally installed terminal. The exporter does not place or modify trades.

## Preferred one-command workflow

You need the recovered full V2 trade ledger on the same machine.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\v05_run_same_broker.ps1 `
  -Ledger "C:\path\to\FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv"
```

If the broker uses suffixes/prefixes, pass explicit mappings rather than guessing:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\v05_run_same_broker.ps1 `
  -Ledger "C:\path\to\FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv" `
  -Aliases @("EURUSD=EURUSD.a","GBPUSD=GBPUSD.a","XAUUSD=XAUUSD.a","US30=US30.cash")
```

The default requested bar window is 2020-01-01 through 2026-08-01. Tick days are derived from actual recovered trade timestamps. Change `-Start` / `-End` if the broker has a different archive range.

## Manual workflow

### 1. Export same-broker data

Preferred targeted export:

```powershell
python scripts\v05_mt5_targeted_export.py `
  --ledger "C:\path\to\FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv" `
  --symbols EURUSD GBPUSD XAUUSD US30 `
  --start 2020-01-01 `
  --end 2026-08-01 `
  --out same-broker-v05\export
```

If a symbol is ambiguous, the script stops and requires an explicit `--alias`; it will not silently select a similarly named CFD.

For a complete continuous tick archive instead of trade-window days:

```powershell
python scripts\v05_mt5_export.py `
  --symbols EURUSD GBPUSD XAUUSD US30 `
  --start 2020-01-01 `
  --end 2026-08-01 `
  --out same-broker-v05\full-export
```

### 2. Verify immutable hashes

```powershell
python scripts\v05_verify_export.py --export-root same-broker-v05\export
```

Any missing/changed parquet file fails verification.

### 3. Relabel recovered V2 trades

```powershell
python scripts\v05_same_broker_relabel_runner.py `
  --ledger "C:\path\to\FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv" `
  --export-root same-broker-v05\export `
  --out same-broker-v05\v05_same_broker_relabels.csv
```

Direct ticks are preferred. If a day has no tick archive, the runner may fall back to same-broker M1 bid OHLC plus the bar spread. M1 labels keep intraminute ambiguity rather than guessing an outcome.

### 4. Run the label-integrity gate

```powershell
python scripts\v05_label_gate.py `
  --relabels same-broker-v05\v05_same_broker_relabels.csv `
  --out same-broker-v05\gate
```

### 5. Only if the gate passes, prepare a training ledger

```powershell
python scripts\v05_prepare_training_ledger.py `
  --ledger "C:\path\to\FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv" `
  --relabels same-broker-v05\v05_same_broker_relabels.csv `
  --gate-summary same-broker-v05\gate\v05_label_gate_summary.json `
  --out same-broker-v05\v05_execution_training_ledger.csv
```

The script refuses to create this file when the gate failed.

## Pre-registered label gate

Passing this gate means **eligible for the next research stage**, not eligible for live trading.

- at least 200 clear direct-tick labels overall;
- at least 100 trusted low-friction direct-tick labels;
- at least 30 direct-tick labels per market;
- source candle vs same-broker tick agreement at least 90%;
- trusted-label agreement at least 93%;
- unresolved-label rate no more than 10%.

These thresholds are written into code before the original-broker result is seen.

## Label hierarchy

### `trusted_tick`

Direct same-broker bid/ask tick outcome, fill spread <=0.20R and stop slippage <=0.10R.

### `tick_high_friction`

Direct tick label is clear but the trade experienced wider spread and/or stop slippage. The outcome remains useful for studying real execution but is not a clean label-quality observation.

### `m1_unambiguous`

No direct tick history for that window. Same-broker M1 bid bars + recorded spread produced only one possible stop/target order. This is secondary evidence, not direct tick ground truth.

### `ambiguous`

Entry/stop/target ordering cannot be established from available lower-timeframe data. The engine does not choose the favorable outcome.

### `unresolved`

No usable fill/data/outcome.

## How stops and targets are replayed

For direct ticks:

- long entry uses **ask**;
- short entry uses **bid**;
- long stop/target uses **bid**;
- short stop/target uses **ask**;
- invalid crossed quotes (`ask < bid`) are discarded;
- a stop gap records the actual crossed quote and slippage;
- a target uses the target limit level once the executable quote reaches it.

There is no cross-broker basis adjustment in v0.5 because all levels and quotes should be from the original broker.

## What to send back for remote review

Do not upload the raw tick archive unless specifically necessary. The useful small outputs are:

- `v05_same_broker_relabels.csv`
- `v05_same_broker_relabels.summary.json`
- `gate/v05_label_gate_summary.json`
- `gate/v05_label_gate_by_symbol.csv`
- `export/manifest.json`

If the gate passes, also keep `v05_execution_training_ledger.csv` locally for the next walk-forward model build.

## Interpretation rules

### If same-broker agreement is high

Cross-broker/source differences were a major reason v0.4 failed. Rebuild the price model using executable labels, then do untouched walk-forward and shadow trading.

### If same-broker agreement is still low

The original M15/M5 outcome construction itself is not reliable enough. Stop model development and fix the strategy simulator/entry definition before any further ML work.

### If only one market passes

Do not pool the markets. Treat the passing instrument as its own strategy research program and require its own OOS validation.

### If tick history is sparse

M1 fallback can diagnose broad problems but cannot promote the strategy to executable-label training. Acquire/export a broker archive with sufficient tick depth.
