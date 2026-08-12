# V2.5 Foundation Model Challengers

Research only. These models have zero Focus, Discord-directional, paper-trade, or risk-sizing authority at registration.

## Candidates

- Amazon Chronos-2: time-series foundation model challenger for zero-shot / covariate-aware structural forecasting.
- Google TimesFM 2.5: independent time-series foundation-model challenger with long context and quantile forecasting support.

## Frozen role

Both models enter `shadow_model_registry` with status `challenger` and `probability_visible=false`.

They may only forecast pre-outcome V2 landmarks. They cannot consume future bars, final labels, post-event macro releases, or any feature unavailable at the forecast timestamp.

## Primary target

For each qualifying Stage-3/4 formation landmark, predict whether same-direction Stage 5 BOS occurs within the next 16 completed M15 bars. XAUUSD results must be reported separately from EURUSD/GBPUSD before any pooled interpretation.

## Comparators

1. Frozen historical base-rate comparator.
2. StateTwin compact student.
3. Granite TTM R2 shadow challenger.

## Promotion gate

A candidate remains zero-influence unless all are true on prospective data:

- at least 100 resolved independent forecast landmarks;
- Brier score improves versus the frozen baseline;
- paired bootstrap of baseline-minus-candidate Brier has a strictly positive lower 95% bound;
- no material calibration failure (ECE review);
- improvement is not concentrated in one calendar period or one instrument;
- XAUUSD has enough independent observations for an asset-specific review;
- no leakage or timestamp-ordering failure;
- model latency/cost is compatible with the free research stack.

Even after this gate, first promotion is to hidden shadow influence only. No model directly creates entries, SL, TP, leverage, or live-money instructions.
