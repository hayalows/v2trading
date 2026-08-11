# V2 v1.8 Model Council — preregistered protocol

Committed before the v1.8 results are observed.

## Research boundary

V2 v1.8 remains research-only. It does not enable broker execution, live-money trading, a buy/sell recommendation, or a visible current probability in Focus.

The primary target is unchanged:

> Earliest independent EURUSD/GBPUSD Stage-3/4 campaign observation -> same-direction BOS / Stage 5 within the next 16 completed M15 bars.

The completed historical evaluation window is 2022–2025. Partial 2026 may be reported as a warning only and cannot rescue a failed completed-year gate.

## Question A — does TTM add information beyond StateTwin?

Use the exact causal V2 replay and the intersection of campaigns for which both models can produce a prediction. One earliest observation per independent campaign.

For every test year:

1. All model fitting and blend selection must use earlier years only.
2. StateTwin uses its frozen v1.6 feature family and component architecture: regularized logistic regression, LightGBM, and distance-weighted KNN. Component weights are selected on the last available pre-test validation year and then the components are refit on the full pre-test history.
3. Granite TTM R2 uses 512 completed M15 closes, the first 16 forecast bars, the four frozen BOS-aware v1.7 forecast features, and a regularized logistic calibration layer trained only on earlier years.
4. The Council is a convex probability blend of StateTwin and TTM. The StateTwin weight is selected only on the last pre-test validation year from the fixed grid 0.00, 0.05, ..., 1.00 by minimum Brier score. Ties prefer more StateTwin weight.
5. No test-year labels may affect model weights, hyperparameters, feature definitions, or acceptance thresholds.

### Primary Council acceptance gate

The Council earns `historical_candidate` status only if all are true on pooled 2022–2025 predictions:

- at least 5,000 independent intersected campaigns;
- Council Brier score is strictly lower than both standalone StateTwin and standalone TTM;
- Council log loss is no worse than StateTwin;
- Council ROC AUC is no worse than StateTwin by more than 0.005;
- Council minus StateTwin Brier improvement is non-negative in at least 3 of 4 completed test years;
- Council minus StateTwin Brier improvement is non-negative for both EURUSD and GBPUSD;
- a fixed-seed 2,000-replicate paired campaign bootstrap gives a 95% confidence interval for `StateTwin Brier - Council Brier` whose lower bound is greater than 0.

If the bootstrap condition fails, the result is treated as insufficient evidence even if the point estimate improves.

### Complementarity diagnostics

Freeze and report:

- Pearson and Spearman correlation of StateTwin and TTM probabilities;
- mean absolute probability disagreement;
- Brier score in disagreement quartiles;
- event rate when the models strongly disagree;
- best historical blend weights selected independently by test year;
- pair-level and year-level metrics.

These diagnostics do not alter the acceptance gate.

## Question B — can StateTwin be distilled into a compact live shadow scorer?

The original StateTwin ensemble is the teacher. A compact student may use only the same causal StateTwin input family available at the forecast timestamp and must be trainable using data through 2025 only.

The student architecture is fixed to a regularized logistic regression over the frozen v1.6 preprocessed StateTwin features plus the teacher probability as a training target diagnostic. It predicts the actual structural outcome, not merely the teacher score.

Evaluation uses chronological 2022–2025 out-of-sample predictions on the same earliest independent campaigns.

### Distillation acceptance gate

A compact StateTwin student earns `shadow` status only if all are true:

- at least 5,000 completed-year campaigns;
- Brier score is no more than 0.0025 worse than the original StateTwin teacher;
- ROC AUC is no more than 0.015 worse than the teacher;
- Brier improvement versus chronological base rate is positive in at least 3 of 4 completed years;
- Brier improvement versus base is non-negative for both EURUSD and GBPUSD;
- ECE10 <= 0.06 pooled.

A pass permits prospective hidden scoring in Shadow Arena only. It does not permit Focus probability display.

## Prospective Council policy

If and only if both a frozen StateTwin shadow score and a frozen TTM shadow score exist before a Shadow Arena outcome:

- store both hidden probabilities in the immutable forecast record;
- calculate `model_disagreement = abs(p_state_twin - p_ttm)`;
- calculate binary entropy of the accepted historical Council probability if a Council passed;
- expose only qualitative research state such as `LOW_DISAGREEMENT`, `MODEL_DISAGREEMENT`, or `UNCALIBRATED` until the prospective sample gate is reached;
- probabilities remain `visible:false` and have zero influence on Focus ranking or paper trades.

No live promotion threshold will be selected in v1.8. Prospective records are evidence collection only.

## Falsification rule

A failed model is recorded as failed. The protocol is not rerun with new thresholds, different test years, hand-selected pairs, or friendlier blend grids inside v1.8.
