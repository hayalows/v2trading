# V2 v1.7 Granite TTM R2 — frozen challenger result

## Decision

**PROMOTE_TTM_TO_SHADOW**

The preregistered standalone Granite Tiny Time Mixer R2 challenger passed every frozen 2022–2025 acceptance criterion for the structural question it was allowed to answer.

This decision does **not** mean TTM replaces StateTwin, improves trade profitability, or is ready to influence Focus. It only earns entry into prospective shadow evaluation and a separate incremental-to-StateTwin test.

## Frozen run

- GitHub Actions run: `31441121031`
- Artifact: `v17-ttm-challenger`
- Artifact ID: `9082949394`
- Artifact SHA256: `cb11dcd5495bcf72a532b3047d99530fb0ccaffd565b86d0d84c4e9671764f90`
- Model: `ibm-granite/granite-timeseries-ttm-r2`
- Context: 512 completed M15 closes
- Forecast outputs used: first 16 M15 bars / 4 hours
- Zero-shot TTM weights; V2 outcome calibration used the frozen four-feature logistic layer from the protocol.

The protocol in `V17_TTM_CHALLENGER_PROTOCOL.md` was committed before the result was observed.

## Completed-year gate: 2022–2025

One earliest observation was retained per independent V2 formation campaign.

| Metric | TTM challenger |
|---|---:|
| Independent campaigns | 8,526 |
| Event rate | 23.33% |
| ROC AUC | 0.6487 |
| Brier score | 0.17075 |
| Chronological base Brier | 0.17897 |
| Brier improvement | +0.00822 |
| Log loss | 0.51957 |
| ECE, 10 bins | 0.01455 |
| Completed years with positive Brier improvement | 4 / 4 |

The frozen acceptance gate required at least 5,000 campaigns, AUC >= 0.58, positive pooled Brier improvement, positive Brier improvement in at least three completed test years, and non-negative Brier improvement for both EURUSD and GBPUSD. All conditions passed.

## Pair-level results

| Pair | n | AUC | Brier | Base Brier | Improvement | ECE10 |
|---|---:|---:|---:|---:|---:|---:|
| EURUSD | 4,282 | 0.6514 | 0.17068 | 0.17908 | +0.00840 | 0.01482 |
| GBPUSD | 4,244 | 0.6458 | 0.17083 | 0.17887 | +0.00804 | 0.01558 |

The result is not being carried by only one pair.

## Year-by-year results

| Test year | n | Event rate | AUC | Brier improvement | ECE10 |
|---|---:|---:|---:|---:|---:|
| 2022 | 2,046 | 24.29% | 0.6424 | +0.00789 | 0.0203 |
| 2023 | 2,203 | 23.88% | 0.6510 | +0.00776 | 0.0230 |
| 2024 | 2,186 | 22.87% | 0.6658 | +0.01027 | 0.0256 |
| 2025 | 2,091 | 22.29% | 0.6326 | +0.00689 | 0.0135 |
| 2026 partial | 103 | 16.50% | 0.6573 | +0.00856 | **0.1137** |

The partial-2026 slice is tiny and has poor probability calibration despite reasonable rank discrimination. It is retained as a warning, not used to promote a live probability.

## Comparison with StateTwin

TTM passed its own frozen challenger gate, but it is **weaker standalone than the accepted StateTwin structural model** on the comparable independent-campaign evidence:

| Model | Independent-campaign AUC | Brier improvement vs base |
|---|---:|---:|
| StateTwin v1.6 | ~0.6657 | ~+0.01126 |
| Granite TTM R2 v1.7 | 0.6487 | +0.00822 |

Therefore the rational next question is not “replace StateTwin with TTM.” It is:

> Does TTM contain information that StateTwin does not already know?

That requires an incremental ensemble test and prospective Shadow Arena scoring.

## What TTM contributed

The model was not allowed to output a trading instruction. Its zero-shot future price path was converted into four causal, BOS-aware structural features:

1. directional forecast extreme relative to the point-in-time BOS reference, ATR-normalized;
2. forecast endpoint move in the formation direction, ATR-normalized;
3. whether the forecast path crossed the BOS reference;
4. forecast-path dispersion, ATR-normalized.

A fixed regularized logistic calibrator converted those features to the structural-event probability studied by the protocol.

## Product status

- TTM historical standalone gate: **PASSED**
- Registry status: **SHADOW**
- TTM live probability in Focus: **WITHHELD**
- TTM influence on paper trades: **NONE**
- Incremental value beyond StateTwin: **NOT YET ESTABLISHED**
- Prospective calibration: **REQUIRED**
- Broker execution truth: **NOT ESTABLISHED**
- Live-money execution: **DISABLED**

A larger model was not promoted because it was larger. TTM was promoted to shadow because it beat the frozen chronological probability baseline on the preregistered criteria.