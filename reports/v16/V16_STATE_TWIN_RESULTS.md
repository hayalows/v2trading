# V2 v1.6 StateTwin — frozen results

## Decision

**ACCEPT_RESEARCH_CANDIDATE** for structural-transition research.

This decision applies only to the question: while an EURUSD/GBPUSD V2 formation is still at Stage 3/4, how much information does the current causal state contain about same-direction BOS / Stage 5 arriving within a fixed horizon?

It is **not** evidence of trade profitability, broker-executable fills, or a live buy/sell signal. The v0.4 execution failure remains in force. The Focus screen must continue to withhold a live structural-transition probability until a prospective shadow-calibration period is accumulated.

## Frozen run

GitHub Actions research run: `31438009289`

Artifact: `v16-state-twin-research`

Artifact SHA256:

`80ed1564e5d9378a2b6d34be22bddfec589c77ebf6e4369281fe67486fe7f211`

The run used the protocol in `V16_STATE_TWIN_PROTOCOL.md` without changing the acceptance gate after results were observed.

Dataset/replay totals across the three frozen horizons:

- 150,558 landmark rows
- 11,352 formation campaigns
- EURUSD and GBPUSD only
- chronological OOS test years: 2022, 2023, 2024, 2025, and partial 2026
- 38,331 OOS landmark predictions per horizon

Landmarks are repeated state updates inside a campaign, so 38,331 must not be described as 38,331 independent formations. A separate one-landmark-per-campaign falsification audit is reported below.

## Primary result — BOS within 16 M15 bars / 4 hours

| Metric | Pooled OOS |
|---|---:|
| Landmark observations | 38,331 |
| Event rate | 19.58% |
| ROC AUC | 0.6883 |
| Brier score | 0.14649 |
| Walk-forward base Brier | 0.15755 |
| Brier improvement | +0.01106 |
| Log loss | 0.45924 |
| ECE, 10 bins | 0.00527 |
| Years with positive Brier improvement | 4 |

Pair-level primary results:

| Pair | OOS n | AUC | Brier | Base Brier | Improvement |
|---|---:|---:|---:|---:|---:|
| EURUSD | 19,170 | 0.6967 | 0.14510 | 0.15680 | +0.01170 |
| GBPUSD | 19,161 | 0.6800 | 0.14789 | 0.15831 | +0.01042 |

The primary horizon passed every preregistered gate: sample size, AUC, pooled Brier improvement, year consistency threshold, pooled calibration threshold, and non-negative pair-level Brier improvement.

## Robustness horizons

### 8 bars / 2 hours

- OOS n: 38,331
- event rate: 13.39%
- AUC: 0.7370
- Brier: 0.10562
- base Brier: 0.11600
- Brier improvement: +0.01037
- ECE10: 0.00536
- positive Brier years: 4

### 32 bars / 8 hours

- OOS n: 38,331
- event rate: 23.37%
- AUC: 0.6813
- Brier: 0.16629
- base Brier: 0.17917
- Brier improvement: +0.01288
- ECE10: 0.00781
- positive Brier years: 4

The shorter 2-hour horizon ranks progression best. The 8-hour horizon still improves probability quality over the historical base rate. The 4-hour horizon remains primary because it was frozen before the run.

## Year-by-year primary horizon

| Test year | n | AUC | Brier improvement | ECE10 | Frozen ensemble weights: linear / nonlinear / twin |
|---|---:|---:|---:|---:|---:|
| 2022 | 9,066 | 0.6657 | +0.00793 | 0.0319 | 0.25 / 0.25 / 0.50 |
| 2023 | 9,560 | 0.7044 | +0.01289 | 0.0193 | 0.00 / 0.75 / 0.25 |
| 2024 | 9,722 | 0.7031 | +0.01114 | 0.0331 | 0.25 / 0.75 / 0.00 |
| 2025 | 9,527 | 0.7017 | +0.01273 | 0.0095 | 0.00 / 0.75 / 0.25 |
| 2026 partial | 456 | 0.5935 | -0.00153 | 0.0554 | 0.00 / 1.00 / 0.00 |

The partial-2026 slice did not beat the base-rate Brier score. It is much smaller than a full test year, but it is retained rather than hidden. This is one reason a prospective shadow period remains mandatory.

The nonlinear component carries most of the ensemble weight after 2022. The nearest-state component contributes materially in 2022, 2023 and 2025, but receives zero weight in 2024 and the partial-2026 slice. StateTwin should therefore be described as an adaptive ensemble, not as proof that nearest-neighbour similarity alone is the edge.

## Independent-campaign falsification audit

The landmark design intentionally updates predictions as a campaign ages, but repeated landmarks are correlated. To test whether repeated campaign observations manufacture the result, a stricter post-gate audit keeps only the **earliest eligible landmark from each campaign**.

For the completed 2022–2025 period at the primary 4-hour horizon:

- independent campaigns: 8,526
- event rate: 23.33%
- AUC: 0.6657
- Brier: 0.16831
- base Brier: 0.17957
- Brier improvement: +0.01126
- ECE10: 0.02134

A deterministic 1,000-resample campaign bootstrap, seed 42, produced:

- Brier-improvement median: about +0.0113
- 95% interval: approximately **+0.0090 to +0.0138**
- AUC median: about 0.6658
- 95% interval: approximately **0.6525 to 0.6778**

Only one campaign crossed a calendar-year boundary, creating three landmark rows across the three horizons. This is negligible relative to the sample, but the boundary case is recorded rather than ignored.

### Independent-campaign probability separation

Using one earliest landmark per 2022–2025 campaign, the lowest and highest predicted deciles were materially separated:

- lowest decile: mean predicted probability about 5.4%, actual BOS rate about **7.2%**
- highest decile: mean predicted probability about 47.0%, actual BOS rate about **44.5%**
- ordinary walk-forward base probability around 20.5–20.7%

This does not mean the top decile is a profitable trade set. It means the model distinguishes low- and high-progression Stage-3/4 states for the structural event it was trained to study.

## What is new in the V2 implementation

StateTwin treats a V2 formation as a **changing state**, not a frozen setup snapshot. The product synthesis combines:

1. the existing causal V2 structure state;
2. online run-length / regime-break diagnostics on M15 returns;
3. dynamic campaign age and point-in-time market geometry;
4. cross-pair EURUSD/GBPUSD context;
5. a calibration-first ensemble of regularized linear, shallow nonlinear and nearest-state models;
6. explicit abstention in the live UI until historical evidence is followed by prospective calibration.

The value of the design is the separation between market-state intelligence and execution claims. It can say that one structural state has historically progressed more often than another without pretending that this proves a broker-executable trading edge.

## Foundation-model policy

Chronos-2 / Chronos-Bolt, TimesFM, MOMENT and related sequence-representation models remain **challengers**. They should be evaluated on the same chronological folds and structural targets. They enter the live product only if they improve out-of-sample calibration or representation quality beyond the simpler StateTwin baseline.

A larger model is not promoted because it is larger.

## Product status after this result

- Live descriptive StateTwin: eligible for product use
- Comparable-state similarity: eligible for product use with clear wording
- Historical structural-transition model: accepted research candidate
- Current live structural-transition probability: **WITHHELD pending prospective shadow calibration**
- Trade-profit probability: not established
- Broker execution truth: not established
- Live-money execution: disabled
