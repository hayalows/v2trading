# V2 v1.6 StateTwin — dynamic structural-transition protocol

## Research question

Can the current EURUSD/GBPUSD market state improve a strictly out-of-sample estimate of whether a developing Stage-3/4 V2 formation reaches same-direction BOS (Stage 5+) within a fixed future horizon?

This study predicts a **structural event**, not the next candle, trade profitability, or broker execution.

## Why this is the next model

The live lab already knows more than the stage number. At every completed M15 bar it has a causal description of direction, volatility, location and formation maturity. v1.5 showed that static Stage-6 information contains modest information about POI revisit timing, but the current market keeps changing after a setup begins. StateTwin therefore treats a formation as a changing state rather than a frozen setup.

The design combines three different inductive biases:

1. a regularized linear model for stable, calibration-friendly effects;
2. a shallow gradient-boosting model for nonlinear interactions;
3. a nearest-state model for local historical analogy.

The ensemble weights are selected only on an inner historical validation year. The next calendar year remains untouched until final evaluation.

## Frozen universe and source

- EURUSD and GBPUSD only.
- Public M15 history: the same `NatoG93/market-data` files already used by the V2 causal replay.
- Live-equivalent state machine: `scripts/v06_prospective_detector_validation_np.py`.
- Replay begins at 2020-01-01 when data is available.
- Every state is generated candle by candle with future bars hidden.

XAUUSD and US30 are excluded. The production research scope is intentionally the two FX pairs, and adding proxy markets would mix data-generation assumptions.

## Dynamic landmark sample

A campaign starts on the first same-direction Stage-3/4 bar and ends when one of these happens:

- same-direction Stage 5+ is reached;
- the detector resets to Stage 0–2;
- direction flips;
- the dataset ends.

Instead of treating every bar as independent, the study samples fixed campaign ages:

`0, 2, 4, 8, 12, 16, 24` M15 bars.

A landmark is included only while that campaign is still in Stage 3/4. This gives the model updated information as the formation ages while reducing repeated near-identical rows.

## Targets

For each landmark, estimate whether same-direction Stage 5+ occurs within:

- 8 bars / 2 hours;
- **16 bars / 4 hours — primary horizon**;
- 32 bars / 8 hours.

A reset or direction flip before BOS is a known negative. Rows without enough future observation and without a terminal event are censored and excluded for that horizon.

## Point-in-time features

Only information available at the landmark bar is allowed:

- symbol, direction, current Stage 3 vs Stage 4, campaign age;
- 1/4/8/16-bar returns;
- direction-adjusted 4/8/16-bar returns;
- ATR-normalized EMA20–EMA50 separation;
- 8/32-bar path efficiency;
- fast/slow realized-volatility ratio;
- 32-bar range position;
- ATR distance from recent 20-bar high and low;
- candle body and wick size in ATR units;
- UTC hour/day cyclical terms;
- contemporaneous EURUSD/GBPUSD 8h and 24h return correlation;
- other-pair 8-bar return and relative 8-bar return.

No future candle, future stage, future POI, MFE/MAE, trade result, or post-event field is permitted.

## Models

### Base-rate benchmark

Training-sample event rate. Any useful probabilistic model must beat this on Brier score.

### Linear component

Regularized logistic regression after median imputation, scaling and categorical one-hot encoding.

### Nonlinear component

A fixed shallow LightGBM classifier with conservative depth/leaf regularization. Class weighting is not used because probability calibration is the goal.

### Twin component

Distance-weighted k-nearest neighbours on the same standardized causal state vector. This is the local analogue layer.

### StateTwin ensemble

For each test year, the most recent earlier year is reserved as an inner validation year. Candidate convex weights over the three components are selected by validation Brier score only. The components are then refit on all earlier years and the frozen weights are applied to the untouched test year.

This nested procedure prevents choosing ensemble weights after seeing the test year.

## Walk-forward evaluation

Test years must be evaluated chronologically. For year Y:

- training years are strictly before Y;
- ensemble weights are selected without Y;
- all preprocessing is fit without Y;
- Y is scored once.

Report per horizon and test year:

- n and event rate;
- ROC AUC;
- Brier score;
- base-rate Brier score and improvement;
- log loss;
- expected calibration error (10 fixed probability bins);
- selected component weights.

Also report pooled results and pooled EURUSD/GBPUSD calibration separately.

## Primary acceptance gate

The 16-bar / 4-hour StateTwin ensemble becomes an **accepted research candidate** only if all conditions hold:

- pooled OOS n >= 1,000 landmarks;
- pooled ROC AUC >= 0.58;
- pooled Brier score is lower than the walk-forward base-rate Brier score;
- Brier improvement is positive in at least 3 test years;
- pooled expected calibration error <= 0.08;
- neither EURUSD nor GBPUSD has a worse pooled Brier score than its base-rate benchmark.

The 8-bar and 32-bar horizons are robustness checks and cannot replace the primary horizon after results are seen.

## Product boundary

Passing this gate does **not** authorize a buy/sell signal or live-money use. At most it allows the result to progress to a prospective shadow period against live StateTwin observations.

The Focus screen must continue to abstain from displaying a current structural-transition probability until the model has also survived prospective calibration on newly accumulated live campaigns.

The prior v0.4 execution failure remains in force. StateTwin is market-state intelligence, not broker execution truth.

## Foundation-model challengers

Chronos-2/Chronos-Bolt, TimesFM, MOMENT and other time-series foundation models are treated as challengers, not privileged defaults. They may be benchmarked later on the same frozen years, but they enter the product only if they improve out-of-sample calibration or state representation beyond this simpler causal baseline. Complexity alone is not evidence.
