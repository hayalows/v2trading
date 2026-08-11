# V2 v1.8 Model Council — frozen result

## Decisions

- **Model Council:** `REJECT_COUNCIL_INCREMENTAL`
- **StateTwin compact student:** `PROMOTE_STATE_TWIN_STUDENT_TO_SHADOW`

The preregistered protocol was committed before this result was observed. The failed Council gate is not being rerun with different weights, thresholds, pairs, or years.

## Frozen run

- GitHub Actions run: `31445594246`
- Artifact: `v18-model-council`
- Artifact ID: `9084456218`
- Artifact SHA256: `2ef94a7d5d28fbca8523c6f40c359d349cd53cc591a7a1f5d2d6095ec0361d62`
- Intersected campaigns total: 11,314
- Completed 2022–2025 campaigns: 8,526
- Eligible live model landmark age: **0 only**

## Completed 2022–2025 comparison

| Model | ROC AUC | Brier | Improvement vs chronological base | Log loss | ECE10 |
|---|---:|---:|---:|---:|---:|
| StateTwin teacher | 0.66465 | 0.16825 | +0.01072 | 0.51254 | 0.01130 |
| Granite TTM R2 | 0.64870 | 0.17075 | +0.00822 | 0.51957 | 0.01455 |
| Model Council | **0.67117** | **0.16761** | **+0.01136** | **0.51075** | 0.01493 |
| StateTwin student | 0.65741 | 0.16938 | +0.00959 | 0.51832 | 0.01976 |

The Council had the best pooled point estimates, but the frozen gate was deliberately stricter than “best pooled number.”

## Why the Council was rejected

The Council improved StateTwin pooled Brier by only:

`0.16825064 - 0.16760949 = 0.00064115`

The paired 2,000-replicate campaign bootstrap for `StateTwin Brier - Council Brier` was:

- point: **+0.000641**
- 95% CI: **[-0.000221, +0.001516]**

The lower confidence bound is below zero, so the improvement is not statistically established under the frozen gate.

The year-level robustness condition also failed. Council minus StateTwin Brier was positive in only 2 of 4 completed years:

| Year | StateTwin Brier | Council Brier | StateTwin − Council |
|---|---:|---:|---:|
| 2022 | 0.17657 | 0.17373 | +0.00284 |
| 2023 | 0.16756 | 0.16872 | **−0.00116** |
| 2024 | 0.16708 | 0.16560 | +0.00149 |
| 2025 | 0.16205 | 0.16256 | **−0.00050** |

Therefore the Council is recorded as **rejected**, despite attractive pooled AUC and Brier values.

## What TTM still contributes

StateTwin and TTM probabilities were only moderately correlated:

- Pearson: **0.5863**
- Spearman: **0.5831**
- mean absolute disagreement: **0.0766**
- median absolute disagreement: **0.0641**

There were 948 completed-year campaigns where the absolute probability gap was at least 0.15. Their event rate was 27.85%.

The highest-disagreement quartile was also where the simple Council helped most descriptively:

- StateTwin Brier: 0.18020
- TTM Brier: 0.18519
- Council Brier: 0.17740

This is useful evidence that TTM may contain complementary information in some market states, but it is not enough to promote a global blend under the frozen statistical gate.

## StateTwin student result

The compact logistic StateTwin student passed its separate deployment gate:

- AUC: **0.65741** vs teacher 0.66465
- Brier: **0.16938** vs teacher 0.16825
- Brier degradation: **+0.00113**, within the frozen +0.0025 tolerance
- ECE10: **0.01976**, below the 0.06 limit
- positive improvement over chronological base in **4 / 4** completed years
- positive base-rate improvement in both EURUSD and GBPUSD
- teacher/student probability correlation: **0.9200**

The student therefore earns **SHADOW** status. It may produce hidden pre-outcome age-0 structural probabilities for prospective calibration.

## Product decision

v1.8 will **not** expose or use a blended Council probability.

Instead it will prospectively run two independently validated age-0 shadow observers:

1. `state-twin-student-v18`
2. `granite-ttm-r2-v17`

The browser may receive only qualitative disagreement state:

- `LOW_DISAGREEMENT` when `|p_student - p_ttm| < 0.15`
- `MODEL_DISAGREEMENT` when `|p_student - p_ttm| >= 0.15`
- `UNCALIBRATED` when either score is missing

The underlying probabilities remain hidden, have no Focus ranking influence, have no paper-trade influence, and do not establish broker execution truth or live-money profitability.
