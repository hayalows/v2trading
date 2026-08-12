# V2 v2.7 — FX Execution & Microstructure Layer

**Research/paper only. No broker execution claim.**

## Purpose

V2's existing structure engine can identify sweeps, BOS, POIs and canonical paper entries, but completed OHLC bars do not fully establish executable BID/ASK path order. V2.7 adds a separate execution-evidence layer instead of changing the canonical paper engine mid-experiment.

## Architecture

### `fx_microstructure_1m`
Stores public Dukascopy BID/ASK tick-derived one-minute context for EURUSD and GBPUSD:
- BID OHLC;
- ASK OHLC;
- mean/open/high/low/close spread in research pips;
- tick count per minute;
- public feed volume fields;
- source timestamp and provenance.

The live sync deliberately fetches only the current and previous hour. Historical recovery is not allowed to block prospective freshness. The production cron runs every 10 minutes and stale data is labelled `STALE`, never imputed as current.

### `paper_trade_execution_audit`
A shadow journal that independently checks paper entries using executable-side logic:
- LONG limit entry: ASK must reach the entry;
- SHORT limit entry: BID must reach the entry;
- LONG stop/target observation: BID path;
- SHORT stop/target observation: ASK path.

Exact public ticks are preferred. If the exact hourly tick file is unavailable, stored BID/ASK one-minute bars may confirm that a level was reachable but cannot prove ordering inside the same minute. Same-minute uncertainty remains ambiguous.

## Frozen boundary

Prospective execution-audit cutoff: **2026-08-12T19:10:00Z**.

Anything before that cutoff is descriptive/historical audit evidence only. It cannot rewrite the canonical $500 account or be used as prospective proof of an execution filter.

## First historical audit findings

Four already-entered EURUSD/GBPUSD paper records were audited after the layer was added.

- The latest GBPUSD long loss was independently reproduced by the public BID/ASK one-minute path. The first executable-side midpoint observation occurred around **17:48 UTC**, with indicative spread around **0.73 pip**.
- The earlier GBPUSD short timeout's canonical entry was **not reproduced** by the independent BID/ASK one-minute path available for that window.
- EURUSD historical audits remained unavailable where the required Dukascopy BID/ASK windows could not be retrieved/stored.
- The existing ambiguous EURUSD short remains canonical `AMBIGUOUS`; no P&L is invented.

These are exactly the kinds of discrepancies the layer is intended to expose. No historical account result was changed.

## Product behavior

The app now shows:
- per-pair microstructure freshness;
- recent spread state relative to its stored median;
- tick-activity state;
- per-trade execution confirmation/mismatch/unavailable status;
- entry spread when independently observed.

Discord trade/open/closure messages include the latest execution evidence. A separate `execution_check` message may fire once when new audit evidence arrives for an open paper trade. Spread/activity changes alone do not create repeated alerts.

## Automation

- `v2-fx-microstructure-10m`: minute 3 every 10 minutes.
- `v2-paper-execution-audit-10m`: minute 5 every 10 minutes.

The existing paper engine and Discord cadence remain unchanged.

## Promotion rule

The execution layer is shadow-only. Before it can affect whether a canonical entry is accepted/rejected, V2 needs a prospective sample large enough to compare:
1. canonical midpoint fills versus independent BID/ASK confirmations;
2. outcomes conditioned on spread/activity state;
3. false-fill/mismatch frequency by pair/session;
4. whether any execution filter improves expectancy without merely reducing sample size or using stale data.

Until those gates pass, the 50% midpoint and canonical $500 journal remain frozen.
