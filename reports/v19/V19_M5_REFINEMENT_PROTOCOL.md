# V2 v1.9 POI Penetration Lab — M5 refinement protocol

**Status: frozen before M5 refinement results.**

This is a secondary protocol frozen **after** the first M15-only run exposed two limitations and **before** M5 refinement results are observed.

## Why this refinement exists

The first M15-only run showed a high same-bar ambiguity rate, and its pre-entry favorable-excursion diagnostic started at BOS rather than at the first POI touch. Therefore it cannot by itself answer the user's exact question: *when price only grazes or partially enters the POI without reaching midpoint, what happens after that touch?*

The first-pass static-depth decision remains immutable. This refinement may strengthen or weaken interpretation, but it cannot retroactively tune the original grid or acceptance rule.

## Data

- Same causal EURUSD and GBPUSD Stage-6 POI reconstructions from the first v1.9 run.
- Same `NatoG93/market-data` source.
- M15 remains the formation timeframe.
- M5 is used only for post-BOS touch sequencing and ambiguity reduction.
- No broker bid/ask, queue position, spread history, or tick ordering is available, so this remains structural research rather than execution validation.

## M5 outcome refinement

For every valid-risk simulated entry depth:

1. Keep the M15-detected setup, POI, stop, 2.5R target, and risk gate unchanged.
2. Keep the M15 fill decision unchanged for comparability.
3. Only rows classified as M15 `ambiguous_entry_bar` or `ambiguous_exit_bar` are re-examined with M5.
4. Within the M15 fill candle, find the first M5 candle that contains the entry price.
5. From that M5 candle forward, resolve stop versus target for at most the original 48-hour horizon.
6. If the entry, stop, and/or target ordering is still unknowable inside one M5 candle, keep the row ambiguous. Do not guess.

Recompute, for every 5% depth:

- valid-risk setups
- fill rate
- resolved fills
- M5 residual ambiguity rate
- resolved win rate
- opportunity expectancy with unresolved/ambiguous = 0
- pessimistic and optimistic ambiguity bounds

Then repeat the original chronological 2022-2025 static-depth-versus-midpoint comparison with M5-refined outcomes. The first-pass acceptance gate is unchanged.

## Reaction-after-penetration event study

A first touch and a later deeper visit are different events. The live GBPUSD case first grazed the POI and later reached about 43.5% maximum penetration without touching midpoint. Therefore the historical study is indexed by **penetration thresholds reached before midpoint**, not merely by first-touch depth.

For each fresh POI and each frozen threshold:

`0%, 10%, 20%, 30%, 40%, 45%`

find the first M5 candle after BOS for which penetration reaches at least that threshold while the midpoint has not yet been touched. Each POI contributes at most one event per threshold.

Starting **after the threshold-reaching M5 candle** to avoid same-candle sequencing assumptions, measure:

- later midpoint touch within 1h, 2h, 4h, 8h, 24h, and 48h
- later distal-edge touch within the same horizons
- M15 close through the distal edge
- whether the original midpoint-based +1R level is reached after the threshold event and before midpoint
- whether the original midpoint-based +2.5R target is reached after the threshold event and before midpoint
- the same +1R/+2.5R reaction rates within 1h, 2h, 4h, 8h, and 24h where applicable
- maximum favorable movement beyond the POI proximal edge before midpoint, in midpoint-risk R
- maximum favorable movement beyond the proximal edge before midpoint, in ATR
- time from threshold event to midpoint when midpoint is later reached

Also retain descriptive first-touch bins (`0-10`, `10-20`, `20-30`, `30-40`, `40-50`, `50-75`, `75-100`, `>=100%`) to describe how violently the initial visit entered the zone.

This distinguishes three different ideas that must not be conflated:

1. **POI reaction:** price reacts in the predicted direction after touching or penetrating part of the zone.
2. **Midpoint execution:** price reaches the fixed 50% entry.
3. **POI lifecycle/invalidation:** price traverses or closes through the zone, or a newer formation supersedes the old setup.

## Interpretation rules

- A shallow touch is not automatically called invalid.
- A later midpoint fill does not prove the shallow reaction failed; price may react first and revisit later.
- Reaching the old trade's target before entry is evidence that the original order may be stale, not proof that the zone itself has no future structural information.
- A completed close through the distal edge is treated as stronger invalidation evidence than a mere touch.
- No `85%`, midpoint, proximal edge, or other depth is promoted to production unless chronological out-of-sample evidence survives the unchanged acceptance gate and execution ambiguity is materially reduced.
