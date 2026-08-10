# V2 v1.5 — Conditional POI revisit model results

## Decision
**ACCEPT_RESEARCH_CANDIDATE for the preregistered 48-bar horizon.**

This does not authorize a live trade signal, win-probability label, or broker-execution claim. It only shows that a small set of Stage-6-known variables contains modest out-of-sample information about whether the POI midpoint is revisited by a fixed horizon.

## Data and validation
- Exact-live full-candle POI geometry from v1.4.
- EURUSD + GBPUSD.
- Walk-forward test years: 2022, 2023, 2024, 2025.
- Pooled OOS n: 1,262 per tested horizon.
- Features known at Stage 6 only: symbol, direction, risk ATR, POI width/ATR, sweep-to-BOS bars, BOS UTC hour, BOS day of week.
- Regularized logistic regression versus training-sample base-rate probability.

## Pooled results

| Horizon | OOS n | Event rate | AUC | Model Brier | Base Brier | Improvement | Positive Brier years |
|---|---:|---:|---:|---:|---:|---:|---:|
| 24 bars / 6h | 1,262 | 53.96% | **0.6171** | **0.23927** | 0.24893 | +0.00966 | 3/4 |
| 48 bars / 12h | 1,262 | 65.37% | **0.6269** | **0.21755** | 0.22676 | +0.00921 | 3/4 |
| 96 bars / 24h | 1,262 | 74.64% | 0.5553 | 0.18989 | **0.18943** | -0.00046 | 2/4 |

## Interpretation
The primary 48-bar gate passed all preregistered conditions:
- n >= 500;
- AUC >= 0.55;
- lower pooled Brier than the base-rate benchmark;
- positive Brier improvement in at least three test years.

The result is **modest**, not strong enough to justify a prominent live probability. The 96-bar failure also shows that the static Stage-6 features lose useful discrimination at longer horizons.

## Product decision
- Keep the Focus screen deterministic and simple.
- Keep pair-level historical lifecycle base rates as descriptive context.
- Show this model only in Research as an accepted candidate.
- Do not expose a current-trade conditional probability until a final frozen model is trained, calibration is checked by pair and year, and prospective behavior is compared with the accumulating live campaign dataset.

## Next research
The next defensible model should be a **dynamic survival/hazard model** that updates after Stage 6 using only point-in-time variables available at each elapsed bar, such as current age, distance from POI, whether the outer POI was touched, pre-entry extension so far, regime, session and HTF context. It must preserve censoring and use walk-forward validation. A Random Survival Forest or discrete-time hazard model can be compared against the accepted static logistic baseline; complexity must improve calibration to be retained.
