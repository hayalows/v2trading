# V2 v1.4 — POI waiting-time and lifecycle results

## Decision
**Replace the 8-M15-bar expiry with lifecycle tracking.**

The previous 8-bar rule was a proxy experiment boundary, not a validated market invalidation rule. In this study, elapsed time alone did not identify a defensible point at which an untouched fresh POI should be cancelled.

This decision changes the **paper-research lifecycle only**. It does not override the v0.4 executable-label failure and does not claim broker profitability.

## Dataset and method
- Markets: EURUSD and GBPUSD.
- Public source: the same free M15/M5 reconstruction data used by the V2 public proxy.
- Frozen Stage-6 candidates: **1,751** total: EURUSD 887, GBPUSD 864.
- Detector geometry was frozen before evaluating waiting horizons.
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
| 8 | 2 | 31.1% | 28.9% | 33.3% |
| 16 | 4 | 43.2% | 39.9% | 46.6% |
| 24 | 6 | 53.6% | 49.7% | 57.6% |
| 48 | 12 | 65.3% | 62.8% | 67.9% |
| 72 | 18 | 70.5% | 67.9% | 73.1% |
| 96 | 24 | 74.2% | 71.8% | 76.6% |
| 144 | 36 | 79.9% | 77.9% | 82.0% |
| 192 | 48 | 82.5% | 81.0% | 84.0% |

Among candidates that filled within the original 48-bar observation, the median midpoint revisit was about **9.5 M15 bars**, so the old 8-bar cutoff occurred before the median eventual revisit.

## Pre-registered 8-to-24-bar decision gate
At 8 bars, 544/1,751 candidates had filled (31.1%). At 24 bars, 939/1,751 had filled (53.6%), an increase of **22.6 percentage points**.

Across the incremental 8-to-24-bar late-fill buckets, **366 resolved trades** retained an approximately **+0.408R mean net proxy result**. A month-cluster bootstrap placed the mean at roughly **+0.24R to +0.58R (95% interval)**. The late-fill mean was positive in every full calendar year from 2020 through 2025.

The preregistered gate required >=5 percentage points of recovered fills, >=30 resolved incremental late fills and positive late-fill mean net R. All three conditions passed.

## Long-tail check
No obvious time cliff appeared after 24 bars. Fill probability continued increasing through the 48-hour research tail. Incremental late buckets also remained positive in the aggregate public proxy:

- 32–48 bars: +0.468R mean, 86 resolved.
- 48–72 bars: +0.588R mean, 80 resolved.
- 72–96 bars: +0.289R mean, 57 resolved.
- 96–144 bars: +0.643R mean, 91 resolved.
- 144–192 bars: +0.749R mean, 42 resolved.

These long-tail results argue against replacing the old 8-bar cutoff with another arbitrary hard timer. They do **not** justify claiming an untouched POI will definitely revisit.

## Shallow POI interaction
A shallow touch of the POI before reaching the midpoint is an important quality flag, but not a clean automatic invalidator in this dataset.

| Condition | Resolved | Mean net R | Win rate |
|---|---:|---:|---:|
| Midpoint reached directly / same POI interaction | 624 | +0.861R | 66.8% |
| Shallow POI touch, midpoint reached later | 712 | +0.143R | 43.4% |

The shallow-touch group remained positive overall but was materially weaker and varied by year. Live v1.4 should therefore mark it as **partially mitigated / degraded evidence**, keep tracking it, and collect prospective outcomes rather than silently treating it as equivalent to an untouched zone.

## Pre-entry directional extension
We also tested whether a setup should be cancelled merely because price had already moved strongly in the intended direction before returning to the midpoint.

| Pre-entry condition | Resolved | Mean net R | Win rate |
|---|---:|---:|---:|
| Planned 2.5R target not reached before entry | 207 | +0.268R | 42.0% |
| Planned 2.5R target already reached before entry | 1,129 | +0.517R | 56.6% |
| <1R favorable extension | 84 | +0.617R | 58.3% |
| 1R–2.5R | 123 | +0.029R | 30.9% |
| 2.5R–5R | 310 | -0.036R | 34.8% |
| >=5R | 819 | +0.727R | 64.8% |

The relationship is non-linear. Therefore, **“the move already reached TP before the retrace” is not accepted as a universal invalidation rule**. It is stored as a context feature for future prospective modelling.

## Live lifecycle policy
For an unfilled Stage-6 paper plan:

1. `fresh_wait`: first 8 completed M15 bars after BOS.
2. `extended_wait`: after bar 8 through bar 48. The old cutoff has passed, but historical research still shows material revisit activity.
3. `long_tail_wait`: bar 49 through bar 192. Still tracked; evidence exists but this is a slower lifecycle.
4. `outside_studied_tail`: beyond 192 bars. The plan remains observable, but the public waiting-time study no longer supplies empirical support for the age bucket.

Time alone does **not** set `invalidated`.

Separate condition flags:
- `intact`: POI has not been touched before midpoint.
- `partially_mitigated`: POI boundary was touched but midpoint not reached.
- `target_delivered_before_entry`: the intended pre-entry move exceeded 2.5R before midpoint fill.
- both flags may coexist.

A midpoint can still fill in any waiting phase. The app must make the reduced/unknown evidence explicit rather than deleting the opportunity.

## Current GBPUSD implication at the time of this study
The live GBPUSD long plan from the 12:30 UTC sweep / 13:15 UTC BOS had POI 1.34912717–1.34954596 and midpoint 1.34933656. Through the 17:30 completed M15 bar, price had not touched the POI or midpoint, so the plan remained **intact but aging**, not structurally invalidated.

Price had already extended far beyond the paper 2.5R target before retracing. v1.4 records that fact but does not cancel the plan solely because of it, because the historical extension study did not support such a universal rule.

## Limits
These are public completed-candle proxy results. They are not original-broker executable bid/ask results. v0.4 demonstrated that candle-source labels can disagree materially with executable labels. The purpose of v1.4 is to stop discarding prospective paper observations for an unsupported timer and to collect a better lifecycle dataset, not to declare the strategy live-money ready.
