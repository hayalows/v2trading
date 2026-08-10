# V2 v1.4 — POI waiting-time and lifecycle results

## Decision
**Replace the 8-M15-bar expiry with lifecycle tracking.**

The previous 8-bar rule was a proxy experiment boundary, not a validated market invalidation rule. Elapsed time alone did not identify a defensible point at which an untouched fresh POI should be cancelled.

This report uses the **exact live POI geometry**: the full high-low range of the last opposite M15 candle between sweep and BOS, with the paper entry at its 50% midpoint. An earlier v1.4 research pass reused the older public-proxy directional sub-zone. The reviewer parity pass corrected that mismatch before these numbers were frozen.

This decision changes the **paper-research lifecycle only**. It does not override the v0.4 executable-label failure and does not claim broker profitability.

## Dataset and method
- Markets: EURUSD and GBPUSD.
- Public source: the same free M15/M5 reconstruction data used by the V2 public proxy.
- Frozen exact-live-geometry Stage-6 candidates: **1,685** total: EURUSD 849, GBPUSD 836.
- Sweep and BOS rules were frozen before evaluating waiting horizons.
- POI: full last-opposite M15 candle high-low, matching the live scanner.
- Entry: 50% POI midpoint.
- Stop: sweep extreme +/- 0.03 ATR.
- Risk gate: 0.08–1.60 ATR.
- Target: 2.5R.
- Post-entry outcome window: 48 M15 bars.
- Waiting horizons examined: 8, 12, 16, 24, 32, 48, 72, 96, 144 and 192 M15 bars.
- Unobserved fills are treated as right-censored rather than losses.

## Time to midpoint

| Bars after BOS | Hours | All fill rate | EURUSD | GBPUSD |
|---:|---:|---:|---:|---:|
| 8 | 2 | **31.9%** | 29.7% | 34.1% |
| 12 | 3 | 38.4% | 35.2% | 41.6% |
| 16 | 4 | 44.2% | 40.0% | 48.4% |
| 24 | 6 | **54.8%** | 50.6% | 59.1% |
| 32 | 8 | 60.4% | 57.7% | 63.2% |
| 48 | 12 | **66.1%** | 63.4% | 68.8% |
| 72 | 18 | 71.4% | 69.1% | 73.7% |
| 96 | 24 | 74.7% | 72.4% | 77.1% |
| 144 | 36 | 80.6% | 78.5% | 82.7% |
| 192 | 48 | **82.8%** | 81.4% | 84.3% |

The exact-live-geometry result confirms that the old 8-bar cutoff was too early to be treated as invalidation. Nearly 23 additional percentage points of candidates reached the midpoint between bars 9 and 24 alone.

## Pre-registered 8-to-24-bar decision gate
At 8 bars, 537/1,685 candidates had filled (31.9%). At 24 bars, 924/1,685 had filled (54.8%), an increase of **23.0 percentage points**.

Across the incremental 8-to-24-bar late-fill buckets, **365 resolved trades** retained an approximately **+0.332R mean net public-proxy result**.

The preregistered gate required:
- at least 5 percentage points of recovered fills;
- at least 30 resolved incremental 8-to-24-bar fills; and
- positive mean net R for those late fills.

All three conditions passed using the exact live POI definition.

## Long-tail check
No clean time cliff appeared after 24 bars. Aggregate fill probability continued increasing through the 48-hour research tail.

Incremental exact-live-geometry late buckets:
- 8–12 bars: +0.209R mean, 108 resolved.
- 12–16 bars: +0.260R mean, 94 resolved.
- 16–24 bars: +0.455R mean, 163 resolved.
- 24–32 bars: +0.648R mean, 79 resolved.
- 32–48 bars: +0.296R mean, 83 resolved.
- 48–72 bars: +0.452R mean, 81 resolved.
- 72–96 bars: +0.296R mean, 52 resolved.
- 96–144 bars: +0.620R mean, 91 resolved.
- 144–192 bars: +0.671R mean, 35 resolved.

There is heterogeneity by market and bucket. For example, EURUSD's 72–96-bar incremental bucket was slightly negative in this proxy. Therefore the result does **not** mean waiting longer is always better, and it does not mean every untouched POI will eventually fill. About 17% of eligible candidates still had not filled by the 192-bar research tail.

The evidence supports **continued observation instead of automatic time expiry**, not a promise of eventual revisit.

## Shallow POI interaction
A shallow touch of the POI before reaching the midpoint is a major quality flag.

| Condition | Resolved | Mean net R | Win rate |
|---|---:|---:|---:|
| Midpoint reached directly / same POI interaction | 499 | **+0.992R** | 68.9% |
| Shallow POI touch, midpoint reached later | 807 | **+0.041R** | 39.5% |

The shallow-touch group remained slightly positive in aggregate, but was dramatically weaker. v1.4 therefore records it as **partially mitigated / degraded context** instead of treating it as equivalent to an untouched POI. The evidence is not strong enough to promote every shallow touch into an automatic cancellation rule.

## Pre-entry directional extension
We also tested whether a setup should be cancelled merely because price had already moved strongly in the intended direction before returning to the midpoint.

| Pre-entry condition | Resolved | Mean net R | Win rate |
|---|---:|---:|---:|
| Planned 2.5R target not reached before entry | 223 | +0.045R | 35.0% |
| Planned 2.5R target already reached before entry | 1,083 | +0.478R | 54.0% |
| <1R favorable extension | 93 | +0.237R | 44.1% |
| 1R–2.5R | 130 | -0.092R | 28.5% |
| 2.5R–5R | 313 | +0.019R | 35.5% |
| >=5R | 770 | +0.664R | 61.6% |

The relationship is strongly non-linear. Therefore, **“the move already reached TP before the retrace” is not accepted as a universal invalidation rule**. Pre-entry extension is stored as a context feature for future prospective modelling.

## Live lifecycle policy
For an unfilled Stage-6 paper plan:

1. `fresh_wait`: first 8 completed M15 bars after BOS.
2. `extended_wait`: bars 9–48. The former cutoff has passed, but the exact-live-geometry study still shows material revisit activity.
3. `long_tail_wait`: bars 49–192. Still tracked; evidence exists but this is a slower lifecycle.
4. `outside_studied_tail`: beyond 192 bars. The plan remains observable, but the waiting-time study no longer supplies empirical support for that age bucket.

Time alone does **not** set `invalidated`.

Separate condition flags:
- `intact`: POI has not been touched before midpoint.
- `partially_mitigated`: POI boundary was touched but midpoint not reached.
- `target_delivered_before_entry`: the intended pre-entry move exceeded 2.5R before midpoint fill.
- `partially_mitigated_after_target`: both conditions occurred.

A midpoint can still fill in any waiting phase. The app must show the age and condition rather than silently deleting the opportunity.

## Current GBPUSD implication during the release audit
The live GBPUSD long plan from the 12:30 UTC sweep / 13:15 UTC BOS has:
- POI 1.34912717–1.34954596;
- midpoint 1.34933656;
- stop 1.34911347;
- target 1.34989431.

At the production audit it remained `armed · extended_wait`, with 19 completed M15 bars after BOS, **no POI touch and no midpoint entry**. The engine recorded roughly 16.41R of pre-entry favorable extension and flagged `target_delivered_before_entry`, but did not cancel the plan because the exact historical study does not support that as a universal invalidation rule.

## Limits
These are public completed-candle proxy results. They are not original-broker executable bid/ask results. v0.4 demonstrated that candle-source labels can disagree materially with executable labels. The purpose of v1.4 is to stop discarding prospective paper observations for an unsupported timer and to collect a better lifecycle dataset, not to declare the strategy live-money ready.
