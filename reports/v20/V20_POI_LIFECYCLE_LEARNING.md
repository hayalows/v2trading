# V2 v2.0 POI Lifecycle Learning

Research-only release. No broker execution, live-money routing, or executable bid/ask claim is added.

## Decision from v1.9

The frozen v1.9 M15 and M5 POI-depth studies did **not** justify replacing the 50% midpoint baseline.

M5 completed-year midpoint (2022-2025):
- valid-risk setups: 2,090
- fill rate: 82.06%
- resolved fills: 1,118
- resolved win rate: 32.38%
- residual M5 ambiguity among fills: 32.59%
- opportunity expectancy: +0.0713R

The pooled descriptive best depth was 40%:
- opportunity expectancy: +0.1014R

But the preregistered chronological test failed:
- 2022 candidate-minus-midpoint: +0.0115R
- 2023: -0.0417R
- 2024: -0.0271R
- 2025: -0.0712R
- pooled completed-year delta: -0.0353R
- bootstrap 95% interval: approximately [-0.1104R, +0.0388R]

Frozen decision: **KEEP_MIDPOINT_RESEARCH_ONLY**.

Therefore v2.0 does not turn 20%, 40%, 65%, 85%, or any other depth into a live entry signal.

## What v2.0 changes

### 1. Continuous POI lifecycle

A POI is no longer represented only as fresh versus touched. V2 stores maximum penetration from the proximal edge toward the distal edge:

- 0.00 = proximal edge
- 0.50 = midpoint
- 1.00 = distal edge
- >1.00 = price traded beyond the distal edge

Lifecycle labels are:
- `untouched`
- `grazed`
- `partially_mitigated`
- `midpoint_touched`
- `deep_unfilled`
- `distal_touched`
- `invalidated_close_through`

A completed close through the distal edge is stronger invalidation evidence than a shallow touch.

### 2. Focus and research are separated

An old unfilled plan can remain in the research journal without continuing to look like the current opportunity.

A newer same-symbol, same-direction formation can mark the older plan as:
- `focus_active = false`
- `focus_suppression_reason = superseded_by_newer_same_direction_plan`

The old observation is not deleted. Its eventual midpoint/depth behavior continues to be collected for research.

Plans beyond the studied waiting-time tail and plans with a distal close-through are also suppressed from Focus while remaining auditable.

### 3. Prospective depth shadows

Every recorded POI gets research-only shadow geometry at 5% increments:

`0%, 5%, 10%, ..., 95%, 100%`

Every shadow uses the same frozen logic:
- same sweep-based stop
- same 0.03 ATR stop buffer
- same 2.5R target
- same 0.08-1.60 ATR risk gate
- 192 M15 bars to observe an entry
- 48 M15 bars after entry for outcome resolution
- public M5 sequencing when M15 ordering is ambiguous

The 50% midpoint remains the only baseline paper-trade plan shown as the production research rule.

### 4. Backfill cannot contaminate prospective evidence

Existing historical/live plans are useful for diagnostics but cannot be allowed to masquerade as forecasts made before their outcomes were known.

Depth rows and penetration events therefore carry a `prospective` flag.

- backfilled plans: `prospective = false`
- only newly frozen post-release observations can become `prospective = true`
- backfilled rows never count toward future promotion gates

The live engine additionally requires a prospective plan to be frozen before the first future M15 bar after BOS can complete. Recovered old Stage-6 plans are therefore research backfills, not prospective evidence.

### 5. Performance suppression

For prospective depth shadows:
- raw depth performance is withheld until at least 30 scored prospective observations at that depth
- `evidenceReady` requires at least 100 scored prospective observations
- no automatic promotion exists
- no depth can alter Focus, baseline paper-entry geometry, or broker execution

If a future depth is ever considered for baseline replacement, it must receive a new preregistered chronological/prospective acceptance protocol.

## Live GBPUSD motivation

The Aug-10 GBPUSD long POI showed why lifecycle tracking matters:
- 0% entry simulation reached 2.5R
- 20% reached 2.5R
- 40% reached 2.5R
- 45% did not fill
- 50% midpoint did not fill

The old plan was therefore a real midpoint-missed historical example. It also became partially mitigated, had already delivered the original target before entry, and was later superseded by a newer same-direction formation.

v2.0 treats that combination correctly: keep the observation for learning, but do not present it as a fresh current Focus opportunity.

## Boundaries

This release learns from public completed-candle data. It has **no broker** bid/ask feed, queue position, spread history, slippage truth, or executable tick validation.

The v0.4 executable-label failure remains in force. POI-depth research can improve how V2 observes and journals market behavior, but it is not evidence of live-money profitability until independently validated with execution-safe data.
