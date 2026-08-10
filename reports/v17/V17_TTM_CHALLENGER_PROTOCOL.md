# V2 v1.7 — Granite TTM R2 challenger protocol

## Frozen question

For an independent EURUSD or GBPUSD V2 formation at its earliest eligible Stage-3/4 observation, does a zero-shot IBM Granite Tiny Time Mixer R2 forecast contain causal information about whether the same-direction formation reaches BOS / Stage 5 within the next 16 completed M15 bars (4 hours)?

This is a structural-transition study only. It does not test trade profitability, fills, spread, slippage or broker execution.

## Data and independence

- Markets: EURUSD and GBPUSD only.
- Frozen public M15 history used by the existing V2 research pipeline.
- Start: 2020-01-01.
- One earliest eligible observation per formation campaign. Repeated campaign landmarks are excluded from this challenger gate.
- A sample requires at least 512 completed M15 closes before the observation.
- No future bar is used in the TTM input or feature construction.
- The label is 1 only if the same-direction V2 campaign reaches Stage 5+ within 16 M15 bars. Reset, direction flip or horizon expiry is 0. Dataset-boundary samples are censored.

## Frozen TTM

- Model family: IBM Granite Tiny Time Mixer R2.
- Hub model: `ibm-granite/granite-timeseries-ttm-r2`.
- Context: 512 M15 closes.
- Forecast horizon used: first 16 M15 outputs.
- Zero-shot only. No TTM weights are fine-tuned on V2 labels.
- Each input window is externally standardized from its own past context only. Forecasts are transformed back to price space before structural features are computed.

## BOS-aware forecast features

The V2 detector's point-in-time BOS reference is reconstructed from the same causal sweep geometry available at the observation. From the TTM forecast we freeze four features:

1. directional forecast extreme relative to the BOS reference, normalized by current ATR;
2. directional forecast endpoint move, normalized by ATR;
3. whether the zero-shot forecast path crosses the BOS reference;
4. forecast-path dispersion, normalized by ATR.

These features are calibrated with one fixed L2 logistic regression. No tree search, feature search or post-result threshold tuning is allowed in this gate.

## Walk-forward evaluation

For each test year from 2022 onward:

- fit the fixed logistic calibrator using only prior years;
- freeze the prior-history event rate as the base probability;
- predict the untouched test year;
- report AUC, Brier score, base Brier score, Brier improvement, log loss and 10-bin ECE;
- report EURUSD and GBPUSD separately as well as pooled.

The completed 2022–2025 period is the acceptance period. Partial 2026 is reported but cannot rescue or invalidate the frozen completed-year gate by itself.

## Frozen acceptance gate

TTM progresses from `challenger` to `shadow` only if, on pooled independent 2022–2025 campaigns:

- at least 5,000 resolved independent campaigns;
- ROC AUC >= 0.58;
- Brier improvement versus the chronological base probability > 0;
- positive Brier improvement in at least 3 of the 4 completed test years;
- non-negative Brier improvement for both EURUSD and GBPUSD.

A pass only means TTM has earned a second test: incremental value when added to StateTwin and prospective Shadow Arena calibration. It does not allow TTM to influence Focus, paper trades or live-money decisions.

A failure freezes the result as `REJECT_TTM_STANDALONE` and leaves StateTwin unchanged.
