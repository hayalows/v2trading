# V2 v1.4 — POI waiting-time protocol

## Question
The v1.3 paper engine currently calls a plan `expired` if the 50% POI midpoint is not reached within 8 completed M15 bars after BOS. That 8-bar value came from the historical proxy configuration. It was not independently validated as a structural invalidation rule.

This study asks:

1. How quickly do BOS-confirmed fresh POIs revisit their 50% midpoint?
2. How many additional fills are recovered by waiting 12, 16, 24, 32 or 48 M15 bars?
3. Do late fills retain positive research expectancy in the frozen public proxy?
4. Does a shallow POI-zone touch before the midpoint materially change later midpoint outcomes?

## Frozen geometry
No detector threshold is changed for this study.

- sweep lookback: 20 M15 bars
- BOS reference: 8 bars
- sweep penetration/reclaim: 0.03 ATR
- BOS deadline: 6 bars
- POI: last opposite candle between sweep and BOS
- entry: 50% POI midpoint
- stop: sweep extreme +/- 0.03 ATR
- risk gate: 0.08–1.60 ATR
- target: fixed 2.5R
- post-entry hold: 48 M15 bars
- same-bar stop/target ambiguity: use M5 when possible; otherwise ambiguous

## Waiting horizons
Evaluate the same frozen Stage-6 candidate set at 8, 12, 16, 24, 32 and 48 completed M15 bars after BOS.

Candidate detection is completed before the waiting horizon is evaluated. Changing a horizon must not create or remove a Stage-6 candidate.

## Censoring
A POI that has not revisited by the end of the observable dataset is right-censored. It is not a loss and is not automatically structurally invalid.

The study produces a Kaplan-Meier-style time-to-midpoint curve using the available public M15 history.

## Decision rule before results
The live system may replace the 8-bar expiry with a longer lifecycle wait if:

- waiting through 24 bars recovers at least 5 percentage points of additional fills versus 8 bars;
- at least 30 resolved fills occur in the incremental 8–24 bar window; and
- those incremental fills retain positive mean net R in the public proxy.

This rule is intentionally modest. Passing it approves a **paper-research lifecycle change only**. It does not approve live-money execution.

## Live product semantics
Regardless of the result, v1.4 should distinguish:

- `armed`: valid fresh POI, waiting for midpoint;
- `aging`: still valid but older than the original 8-bar research window;
- `filled`: midpoint was reached;
- `invalidated`: a separately defined structural invalidation occurred;
- `stale_unfilled`: research observation horizon ended without a fill;
- `censored`: insufficient future data.

Time alone should not be labelled `invalidated` unless research explicitly supports that rule.

## Limits
The public reconstruction is not original-broker execution truth. v0.4 already showed that independent executable labels can disagree materially with candle-source labels. Therefore all v1.4 results remain research-only and should be used to improve paper-trade data collection, not to claim broker profitability.
