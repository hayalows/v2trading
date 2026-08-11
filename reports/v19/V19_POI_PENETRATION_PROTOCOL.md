# V2 v1.9 POI Penetration Lab — preregistered protocol

## Research question

For causal V2 Stage-6 fresh POIs on EURUSD and GBPUSD, what happens after price first revisits the zone, and does a fixed entry depth other than the current 50% midpoint improve out-of-sample paper-trade outcomes?

This study is research only. It does not establish broker execution truth or live-money profitability.

## Data

- Symbols: EURUSD, GBPUSD
- Primary timeframe: completed 15-minute OHLC bars from `NatoG93/market-data`
- Start: 2020-01-01
- Formation logic: the same causal sweep -> BOS -> opposite-candle POI reconstruction used by V2's prospective detector
- One observation per unique `(symbol, direction, sweep_time, bos_time, poi_time)` fresh POI
- A POI becomes knowable only after its BOS bar closes. No pre-BOS fill is permitted.

## POI geometry

Let the POI be `[low, high]`.

For a long POI, price revisits from above:
- proximal edge = `high`
- distal edge = `low`
- depth 0.00 = proximal edge
- depth 0.50 = midpoint
- depth 1.00 = distal edge
- entry(depth) = `high - depth * (high-low)`

For a short POI, price revisits from below:
- proximal edge = `low`
- distal edge = `high`
- entry(depth) = `low + depth * (high-low)`

Penetration may exceed 1.0 if price trades through the distal edge.

## Fixed entry grid

Primary grid is frozen before results:

`0.00, 0.05, 0.10, ..., 0.95, 1.00`

The current V2 midpoint rule is 0.50 and is the preregistered baseline.

## Stop and target

To isolate entry depth, keep the existing paper-engine geometry:

- stop = sweep extreme +/- `0.03 * ATR14 at sweep`
- reward target = `2.5R`
- valid risk gate = `0.08 <= risk_atr <= 1.60`

Results are reported both:
1. with the current risk gate, and
2. as ungated geometry diagnostics.

No depth gets a custom stop or reward multiple in the primary test.

## Causal fill rule

- first eligible bar is the first completed M15 bar after BOS
- a long entry fills when bar low <= entry <= bar high
- a short entry fills when bar low <= entry <= bar high
- no hypothetical fill before the entry level is actually touched
- time-to-fill is recorded in bars and hours

## Outcome resolution

After a fill:
- win = 2.5R target touched before stop
- loss = stop touched before target
- unresolved = neither within 48 hours (192 M15 bars)
- ambiguous = stop and target ordering cannot be determined from the same M15 bar

Ambiguous cases are not silently assigned. Report:
- censored primary result
- pessimistic bound: all ambiguous = loss
- optimistic bound: all ambiguous = win

## Pre-fill diagnostics

For every depth record:
- filled / not filled
- target delivered before entry
- maximum favorable excursion before fill, in R
- first zone touch time
- first-touch penetration fraction
- maximum penetration before invalidation/horizon

This directly measures cases where the POI works directionally without reaching the midpoint.

## POI-state diagnostics

A POI is not treated as binary fresh/invalid solely because it was touched. Track these states separately:

- UNTOUCHED: no overlap with POI
- GRAZED: zone touched but penetration < 0.25
- SHALLOW: 0.25 <= penetration < 0.50
- DEEP: 0.50 <= penetration < 1.00
- DISTAL_TOUCHED: penetration >= 1.00 without confirmed close-through classification
- CLOSE_THROUGH_DISTAL: completed close beyond distal edge

For first-touch cohorts, estimate conditional probabilities of:
- later midpoint touch
- later distal touch
- close through distal
- same-direction +1R, +2.5R excursion before distal close-through
- reversal against the POI

## Primary metrics by depth

For each depth:
- eligible setups
- valid-risk setups
- fill rate
- win rate among resolved fills
- loss rate
- ambiguous rate
- unresolved rate
- mean gross R per filled resolved trade
- gross R per eligible setup, with non-fills = 0 (`opportunity expectancy`)
- target-before-entry rate
- median bars to fill
- median MAE/MFE after fill

The primary optimization metric is **opportunity expectancy**, not conditional win rate, because deeper orders can manufacture a high win rate by filling only a selected minority.

## Robustness dimensions

Report pooled and split by:
- EURUSD / GBPUSD
- year
- long / short
- UTC session bucket
- zone width / ATR quartile
- displacement from BOS / ATR quartile
- time-to-first-touch bucket
- first-touch penetration state

## Chronological anti-overfit test

Completed test years: 2022, 2023, 2024, 2025. Partial 2026 is reported separately and cannot rescue a failed completed-year result.

For each test year:
1. use only earlier years to choose one static depth maximizing opportunity expectancy
2. require at least 100 resolved valid-risk fills in training for an eligible depth
3. evaluate that frozen depth on the next year
4. compare against frozen 0.50 midpoint on the same test setups

A candidate static depth may replace midpoint only if all are true on completed 2022-2025 walk-forward tests:
- pooled opportunity expectancy > midpoint
- paired bootstrap 95% CI for candidate-minus-midpoint opportunity R has lower bound > 0
- candidate is non-inferior to midpoint in at least 3 of 4 completed years
- both EURUSD and GBPUSD pooled opportunity expectancy are nonnegative relative to midpoint
- candidate does not reduce fill rate by more than 50% unless its opportunity expectancy still improves after non-fill penalty

Otherwise midpoint remains the production rule and the result is research-only.

## Adaptive-depth exploratory model

Only after the static grid is reported, run an explicitly exploratory adaptive policy using pre-entry causal features. It must be evaluated with nested chronological validation and cannot modify the primary static-depth decision.

Possible features:
- pair
- direction
- hour/session
- ATR
- zone width / ATR
- sweep-to-BOS displacement / ATR
- BOS latency
- trend/alignment features available at BOS

The adaptive policy is interesting only if it beats the best static depth out-of-sample after accounting for non-fills.

## Interpretation boundary

The POI construct is a V2 structural heuristic, not an academically established market object. Market-microstructure research supports the general trade-off between price improvement, execution probability, queue/depth state and adverse selection, but it does not validate 'order blocks' or a universal 50%/85% POI rule.

No result from this public OHLC proxy may be described as broker-executable edge without same-broker bid/ask/tick validation.