# V2 v1.9 POI Penetration Lab — M5 refinement protocol

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

## Reaction-after-touch study

The reaction study starts at the **first M5 candle that overlaps the POI**, not at BOS.

For each fresh POI, calculate first-touch penetration from the POI proximal edge toward the distal edge:

- `0-10%`
- `10-20%`
- `20-30%`
- `30-40%`
- `40-50%`
- `50-75%`
- `75-100%`
- `>=100%`

The user's current GBPUSD example (about 43.5% maximum penetration without midpoint) belongs to `40-50%`; that fact is used only for interpretation, not parameter selection.

For touches that initially remain shallower than midpoint (`<50%`), starting **after the first-touch M5 candle** to avoid same-candle sequencing assumptions, measure:

- later midpoint touch within 1h, 2h, 4h, 8h, 24h, and 48h
- later distal-edge touch within the same horizons
- M15 close through the distal edge
- whether the original midpoint-based +1R level is reached after the touch and before midpoint
- whether the original midpoint-based +2.5R target is reached after the touch and before midpoint
- maximum favorable movement beyond the POI proximal edge before midpoint, in midpoint-risk R
- maximum favorable movement beyond the proximal edge before midpoint, in ATR
- time from first touch to midpoint when midpoint is later reached

This distinguishes three different ideas that must not be conflated:

1. **POI reaction:** price reacts in the predicted direction after touching part of the zone.
2. **Midpoint execution:** price reaches the fixed 50% entry.
3. **POI lifecycle/invalidation:** price traverses or closes through the zone, or a newer formation supersedes the old setup.

## Interpretation rules

- A shallow touch is not automatically called invalid.
- A later midpoint fill does not prove the shallow touch failed; price may react first and revisit later.
- Reaching the old trade's target before entry is evidence that the original order may be stale, not proof that the zone itself has no future structural information.
- A completed close through the distal edge is treated as stronger invalidation evidence than a mere touch.
- No `85%`, midpoint, proximal edge, or other depth is promoted to production unless chronological out-of-sample evidence survives the unchanged acceptance gate and execution ambiguity is materially reduced.
