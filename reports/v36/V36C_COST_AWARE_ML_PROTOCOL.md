# V3.6C Cost-Aware High-Win-Rate ML Protocol

Status: **FROZEN BEFORE ANY V3.6C RESULT AND BEFORE OPENING 2023-2025 HOLDOUT**

## Why this follow-up exists

The first V3.6 ML study produced a repeatable pre-holdout pattern: several fixed LightGBM configurations achieved materially higher win rates (roughly 53-69%) and positive baseline-cost expectancy across the pre-2023 sample, but none cleared the preregistered stress-cost gate. The clearest high-hit-rate example used a 1.25 ATR stop and 0.75R target and was positive before stress but negative after wider friction.

This study tests a specific economic hypothesis derived **only from pre-holdout evidence**:

> If the predictive ranking contains some information but fixed pip costs consume too much of a narrow stop, wider ATR stops plus explicit cost-as-a-fraction-of-risk discipline may preserve the hit-rate advantage while creating enough expectancy margin to survive friction.

This is not a rescue filter chosen from 2023-2025. The final holdout remains unopened when this protocol is frozen.

## Data / chronology

Identical raw data and causal features as V3.6:
- Dukascopy public bid M15 EURUSD and GBPUSD
- 2005-01-01 to 2025-12-31
- expanding-year LightGBM predictions
- discovery 2005-2016
- validation 2017-2020
- confirmation 2021-2022
- untouched final holdout 2023-2025

No V2/V3 engine output, setup label or previous trade is a feature.

## Model

Exactly the fixed V3.6 LightGBM architecture and feature set. No hyperparameter tuning is added.

## Frozen V3.6C search

Stop distance:
- 1.50 ATR
- 2.00 ATR
- 2.50 ATR
- 3.00 ATR

Target reward/risk:
- 0.50R
- 0.75R
- 1.00R
- 1.25R

Prediction-confidence thresholds:
- 0.60
- 0.65
- 0.70

Volatility availability gates, measured causally by trailing 20-day ATR percentile:
- no additional percentile gate
- ATR percentile >= 0.40
- ATR percentile >= 0.60

Every candidate must also pass the same fixed cost-to-risk discipline at the signal bar:
- baseline round-trip cost <= 0.08R of stop risk
- stress round-trip cost <= 0.15R of stop risk

Baseline/stress pip assumptions remain unchanged:
- EURUSD 0.8 / 1.5 pips
- GBPUSD 1.0 / 2.0 pips

The search therefore contains exactly 4 × 4 × 3 × 3 = **144 V3.6C configurations**.

## Execution

- signal is created only from a completed M15 bar;
- entry is next M15 open;
- maximum hold 32 M15 bars;
- same-bar target/stop is pessimistically stop-first;
- unresolved positions close at the horizon close;
- one position per pair/config at a time.

## Selection gate

V3.6C uses a stricter pre-holdout gate because its hypothesis was motivated by V3.6 pre-holdout observations:

- >= 300 pre-holdout trades total;
- >= 100 trades on each pair;
- net expectancy >= +0.04R/trade after baseline costs;
- profit factor >= 1.10;
- win rate >= 55%;
- both EURUSD and GBPUSD individually positive;
- >= 4 of 6 years 2017-2022 positive;
- stress-cost expectancy >= 0;
- no single year contributes >45% of cumulative pre-holdout net R.

Candidates are ranked only on data through 2022 using median yearly expectancy, stress expectancy, lower-confidence-bound expectancy, PF, hit rate and sample-size stability.

## Untouched holdout gate

Only the single top pre-2023 candidate is reconstructed on 2023-2025.

To earn `WATCHLIST`:
- >=120 holdout trades and >=40 per pair;
- win rate >=55%;
- mean net R >= +0.05;
- PF >=1.10;
- both pairs positive;
- at least 2/3 holdout years positive;
- stress mean R >=0;
- monthly block-bootstrap 95% lower bound > -0.02;
- no one month contributes >50% of gains.

To earn `PROMOTE`:
- all WATCHLIST gates;
- win rate >=58%;
- mean net R >= +0.10;
- PF >=1.20;
- stress mean R >= +0.03;
- bootstrap 95% lower bound >0.

If it fails, it is rejected. No holdout tuning is allowed.

## Deployment boundary

Even `PROMOTE` is deployed first as a separate shadow engine and paper ledger, because this is historical evidence rather than live broker execution evidence. It cannot overwrite the existing V2 $500 account without prospective confirmation.
