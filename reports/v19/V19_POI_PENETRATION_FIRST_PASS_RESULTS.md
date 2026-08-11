# V2 v1.9 POI Penetration Lab — first-pass results

Research only. These are public M15 OHLC structural-proxy results, not broker execution validation.

## Frozen run

- GitHub Actions run: `31501787388`
- Artifact: `v19-poi-penetration`, ID `9105876384`
- Artifact SHA256: `0e58867611a55f1dd9698e73f8511cf511890ad67bb61650d0da521548801068`
- Protocol: `reports/v19/V19_POI_PENETRATION_PROTOCOL.md`
- Symbols: EURUSD, GBPUSD
- History start: 2020-01-01
- POI depth grid: 0%, 5%, ..., 100%
- Target: fixed 2.5R
- Current risk gate: `0.08 <= risk_atr <= 1.60`
- Primary completed test years: 2022-2025

## Sample

- Fresh POI setups reconstructed: **5,590**
- POI x depth simulation rows: **117,390**
- Completed 2022-2025 setups: **4,245**

## Current 50% midpoint — completed 2022-2025

- valid-risk setups: **2,090**
- fill rate: **82.06%**
- resolved fills: **801**
- resolved win rate: **33.46%**
- M15 ambiguity rate among fills: **53.29%**
- censored opportunity expectancy: **+0.0656R per valid setup**
- pessimistic ambiguity bound: **-0.3718R**
- optimistic ambiguity bound: **+1.1589R**
- target-before-entry rate: **84.59%**
- median bars to fill: **14 M15 bars**

The high ambiguity means the M15-only expectancy must not be treated as execution truth.

## Descriptive static depth scan under the current risk gate

The highest pooled censored opportunity expectancy in completed 2022-2025 was **20% depth**:

- valid-risk setups: **1,784**
- fill rate: **84.53%**
- resolved win rate: **35.07%**
- M15 ambiguity rate: **46.29%**
- censored opportunity expectancy: **+0.1029R**

But the paired 20%-minus-midpoint comparison on common valid setups was only **+0.03745R**, with bootstrap 95% CI approximately **[-0.0166R, +0.0890R]**. It crosses zero, so 20% is **not** established as superior.

Other useful paired comparisons versus midpoint on common valid-risk setups:

- 15%: +0.0318R, 95% CI roughly [-0.0271, +0.0901]
- 40%: +0.0138R, CI roughly [-0.0213, +0.0485]
- 55%: +0.0142R, CI roughly [-0.0091, +0.0382]
- 65%: +0.0204R, CI roughly [-0.0150, +0.0556]
- 85%: **-0.0149R**, CI roughly [-0.0658, +0.0327]
- 100%: **-0.0333R**, CI roughly [-0.1053, +0.0363]

Therefore there is no robust current-risk-gate evidence for a universal 85%, 65%, 20%, or other replacement depth.

## Ungated geometry diagnostic

When the risk gate is ignored purely to isolate POI geometry, 65% depth had the highest completed-period censored opportunity expectancy among the grid at about **+0.0731R**, versus midpoint **+0.0479R**. On all 4,245 common setups, 65%-minus-midpoint was about **+0.0252R**, bootstrap 95% CI approximately **[+0.0054R, +0.0455R]**.

This does **not** justify changing production entry to 65%. The apparent advantage changes once the actual V2 risk gate is enforced, showing that entry depth and the risk filter interact materially.

## Win-rate result

No global depth produced more wins than losses among M15-resolved fills. Across the grid, resolved win rates were roughly in the low-to-mid 30% range; the best global risk-gated values were around 36-37%.

At a fixed 2.5R reward and 1R loss, the frictionless break-even win rate is 28.57%, so a win rate below 50% can still have positive gross expectancy. That does not address transaction costs or execution quality.

## Chronological walk-forward static-depth test

The preregistered training procedure selected **100% distal depth** from prior history for each completed test year. Against midpoint on the same valid setups:

- 2022: **-0.0023R**
- 2023: **-0.0813R**
- 2024: **+0.0188R**
- 2025: **-0.0593R**

Pooled completed-year candidate-minus-midpoint:

- paired n: **992**
- mean delta: **-0.03327R**
- bootstrap 95% CI: **[-0.10635R, +0.03478R]**
- EURUSD mean delta: **-0.03024R**
- GBPUSD mean delta: **-0.03629R**
- non-inferior completed years: **1 of 4**

Frozen decision: **`KEEP_MIDPOINT_RESEARCH_ONLY`**.

This is also evidence of non-stationarity. Descriptively, 100% depth looked strongest in 2022-2024, while 0% proximal depth was strongest in 2025. A pooled optimum is therefore not necessarily a stable rule.

## POI lifecycle after shallow first visits

At midpoint-valid setups, first-visit cohorts showed:

### GRAZED first visit
- n: **955**
- later midpoint fill rate: **90.99%**
- later resolved midpoint win rate: **34.41%**
- M15 distal-close rate within the research horizon: **82.09%**

### SHALLOW first visit (25%-50% penetration)
- n: **500**
- later midpoint fill rate: **92.40%**
- later resolved midpoint win rate: **31.08%**
- M15 distal-close rate: **84.00%**

So a shallow touch does not imply immediate invalidation. But if an old POI is kept alive for a long research horizon, most shallow first visits later reach midpoint and many eventually close through the distal edge. Freshness should therefore be modeled as a lifecycle, not a binary flag.

The first pass also found that the pre-entry target had already been delivered in about **84.68%** of midpoint-valid setups over the full sample. This diagnostic starts at BOS, not at first touch, so it must not be interpreted as a reaction-after-touch statistic. That limitation motivated the frozen M5 refinement protocol.

## M15 resolution limitation

Midpoint ambiguity was strongly related to stop tightness. Among completed-year filled midpoint setups:

- risk_atr 0.08-0.20: ~100% M15 ambiguous
- 0.20-0.40: ~90.8%
- 0.40-0.60: ~77.6%
- 0.60-0.80: ~63.3%
- 0.80-1.00: ~46.5%
- 1.00-1.20: ~34.9%
- 1.20-1.60: ~20.2%

Therefore M5 or finer sequencing is required before treating the depth scan as execution evidence.

## Live GBPUSD example that motivated the study

Old long POI:

- POI: 1.3491271734 to 1.3495459557
- midpoint: 1.3493365645
- stop: 1.3491134681
- original midpoint target: 1.3498943056
- deepest observed visit without midpoint: about **43.5% penetration**
- midpoint missed by about **0.27 pip**

Using the same sweep stop and fixed 2.5R target, the live M15 path gave:

- 0% entry: filled 2026-08-11 07:30 UTC, 2.5R target after fill at 08:30 UTC
- 20% entry: filled 11:45 UTC, 2.5R target at 13:00 UTC
- 40% entry: filled 12:00 UTC, 2.5R target at 12:30 UTC
- 45% entry: not filled
- 50% midpoint: not filled

So this specific case is a genuine **midpoint-missed winner** under 0%, 20%, and 40% alternative entry simulations. It is one observation and cannot select the production depth.

At the latest live check, this old trade remained `armed` after roughly 100 M15 bars, with `pre_entry_target_reached=true` and `setup_condition=partially_mitigated_after_target`, while a newer GBPUSD long Stage-4 formation existed. That supports treating the old plan as stale/superseded for lifecycle purposes rather than calling it fresh merely because the midpoint was never touched.

## First-pass conclusion

1. A POI is **not automatically invalid** when price first touches it or partially enters it.
2. The current GBPUSD POI was partially mitigated, not structurally invalidated by a distal close, but its old trade plan is stale/superseded.
3. This live example shows the midpoint can miss a clean 2.5R outcome.
4. Historical data do **not** support replacing midpoint with a universal 85%, 65%, 40%, 20%, or proximal entry yet.
5. The pooled M15 scan contains too much intrabar ambiguity for an execution claim.
6. The next valid refinement is M5 post-touch sequencing and M5 ambiguity reduction, frozen separately in `V19_M5_REFINEMENT_PROTOCOL.md`.
