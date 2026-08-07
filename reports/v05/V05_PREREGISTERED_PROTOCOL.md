# V2 Quant v0.5 — Pre-registered Same-Broker Protocol

**Status:** frozen before the original-broker v0.5 result is observed.

## Research question

The v0.4 cross-broker execution audit failed. v0.5 asks one narrower question:

> When the original V2 entry/stop/target levels and the lower-timeframe execution quotes come from the same MT5 broker feed, are the historical V2 outcome labels reproducible enough to justify model rebuilding?

This protocol is about **label integrity**, not profitability optimization.

## Data required

Original MT5 broker feed for the recovered V2 research period:

- M1, M5 and M15 bars;
- bid/ask ticks for recovered trade windows whenever the broker provides them;
- symbol point/tick/contract/execution metadata;
- the recovered V2 trade ledger containing symbol, direction, entry time, entry price, stop, target when available, and historical result.

Default expected markets:

- EURUSD
- GBPUSD
- XAUUSD
- US30

A missing expected market counts as **zero coverage** and prevents the pooled gate from passing.

## Immutable-data rule

Every exported parquet file is recorded in `manifest.json` with byte size and SHA256. `v05_verify_export.py` must pass before relabeling.

The export must not include account login or account-holder identity.

## Entry reconciliation

The recovered ledger records an M15 entry timestamp. v0.5 will not let a limit order fill indefinitely after that time.

Default entry reconciliation window:

**15 minutes from `entry_time`.**

If the executable side of the market does not reach the entry during this window, the replay is `no_fill` even if price revisits the level later.

After a valid fill, stop/target replay may continue for the configured holding horizon, default **12 hours**.

No post-result expansion of the entry window is allowed in the primary v0.5 test.

## Executable quote rules

Direct tick replay:

- long entry: ask <= entry;
- short entry: bid >= entry;
- long stop: bid <= stop;
- long target: bid >= target;
- short stop: ask >= stop;
- short target: ask <= target.

Invalid crossed quotes where `ask < bid` are discarded.

If a stop is crossed beyond the requested stop level, actual crossed quote is used and stop slippage is measured in R.

When a target is executable, target fill is recorded at the target limit level.

## M1 fallback

Direct broker ticks are preferred ground truth.

When direct ticks are unavailable, same-broker MT5 M1 bid OHLC plus the recorded bar spread may be used as secondary evidence.

M1 fallback must not guess:

- entry/exit ordering inside the fill minute;
- stop versus target ordering when both occur in one minute.

Such cases remain ambiguous and do not become direct-tick labels.

## Label quality

### trusted_tick

Direct same-broker tick win/loss with:

- fill spread <= 0.20R;
- stop slippage <= 0.10R.

### tick_high_friction

Direct tick outcome is clear but spread and/or stop slippage exceeds the trusted threshold.

### m1_unambiguous

No direct tick label, but M1+spread produces one unambiguous path.

### ambiguous

Available lower-timeframe data cannot establish order of events.

### unresolved

No usable data, no fill, timeout without a clear primary label, or another unresolved condition.

## Primary pre-registered gate

The pooled same-broker label gate passes only if **all** conditions pass:

1. all expected markets are present;
2. at least **200** clear direct-tick labels overall;
3. at least **100** trusted direct-tick labels overall;
4. at least **30** clear direct-tick labels in every expected market;
5. source historical outcome vs same-broker direct-tick outcome agreement >= **90%** overall;
6. source historical outcome vs trusted same-broker tick agreement >= **93%**;
7. unresolved-label rate <= **10%**.

The gate is implemented in `scripts/v05_label_gate.py`.

## Decisions fixed before results

### If the gate passes

The project may proceed to a new executable-label model research stage.

Passing does **not** approve:

- live-money trading;
- live buy/sell recommendations;
- production position sizing.

The next model must be retrained from executable labels and independently walk-forward validated.

### If the gate fails because agreement is low

Do not retrain any predictive model. Diagnose the V2 simulator, exact entry semantics and historical labeling process first.

### If the gate fails because tick coverage is insufficient

Do not substitute M1 labels to force a pass. Obtain a deeper broker tick archive or reduce the research claim to markets/periods with adequate direct-tick coverage under a separately pre-registered experiment.

### If only one or some markets look strong

Do not delete weak markets and report the pooled strategy as successful. Any market-specific follow-up becomes a new pre-registered research experiment with its own OOS validation.

## Forbidden post-hoc rescue actions

The primary v0.5 result will not be rescued by:

- flipping wins/losses or model direction;
- changing the 15-minute entry window after inspecting outcomes;
- changing the 90%/93% agreement gates after inspecting outcomes;
- dropping weak instruments from the pooled result;
- selecting only profitable years;
- changing trusted spread/slippage thresholds after inspecting outcomes;
- using future bars or quotes to decide whether a label should count.

Any follow-up change must be named as a new experiment and must preserve the original v0.5 result.

## Why this gate is deliberately strict

v0.4 showed only ~59% source-vs-independent-tick agreement and the frozen v0.3 score did not survive executable relabeling. A same-broker study is specifically intended to remove cross-broker basis/path differences. Therefore, if same-broker source labels still cannot reach high agreement, the historical outcome engine is not reliable enough to justify additional machine learning.

## Current status

The v0.5 software pipeline is built and code-tested. The original-broker result has **not** been run in this repository because the original MT5 terminal/archive is not available to the remote research environment.
