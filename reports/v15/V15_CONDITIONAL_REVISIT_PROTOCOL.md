# V2 v1.5 — Conditional POI revisit model protocol

## Question
Can information already known when Stage 6 confirms improve out-of-sample estimates of whether the POI midpoint will be revisited within fixed future horizons?

This model is **not** a trade-win model and is **not** allowed to alter entry, SL, TP, BOS, POI, or paper-trade rules.

## Frozen source
Use the v1.4 exact-live-geometry candidate generator:
- EURUSD + GBPUSD only
- full high-low last-opposite M15 POI, matching the live scanner
- candidate identified at Stage 6 before future midpoint information is observed
- right-censor candidates without sufficient future bars for each tested horizon

## Stage-6-known features only
- symbol
- direction
- risk ATR
- POI width / ATR
- sweep-to-BOS bars
- BOS UTC hour
- BOS day of week

Explicitly excluded:
- midpoint fill time
- shallow-touch status
- pre-entry extension
- MFE/MAE
- trade outcome
- any future candle feature

## Models
For each fixed horizon (24, 48, 96 M15 bars), compare:
1. training-sample base-rate probability;
2. regularized logistic regression with one-hot categorical encoding and standardized numeric features.

## Validation
Walk-forward by calendar year. For a test year, training data must come strictly from earlier years. Report per-year and pooled:
- sample size
- event rate
- ROC AUC
- Brier score
- base-rate Brier score
- Brier improvement

## Acceptance gate
The model may be considered for a future descriptive UI layer only if all are true:
- pooled test sample >= 500;
- pooled AUC >= 0.55;
- pooled model Brier is lower than the base-rate Brier;
- Brier improvement is positive in at least 3 test years;
- no horizon is selected after seeing results. The primary horizon is 48 bars; 24 and 96 are robustness checks.

If the primary 48-bar model fails, reject predictive UI integration. Historical survival/base-rate context may remain descriptive.

## Product boundary
Even if accepted, any output must be labeled **historical conditional revisit estimate**, not win probability, execution probability, or trade signal. Broker-specific execution remains unresolved.
