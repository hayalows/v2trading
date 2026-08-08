# V2 Research Lab v0.8 — Product + Live Data Audit

## Objective

Use the prospective data collected since the live lab launched, together with current quant-research and interface-design principles, to improve how the product prioritizes information and guides investigation.

## Live sample audited

Audit timestamp: 2026-08-08 UTC, after the first live FX session had closed.

Core markets:
- EURUSD
- GBPUSD

At the audit point the prospective store contained about 70 observations per pair, sampled approximately every 15 minutes when history snapshots were written.

### EURUSD
- ~70 prospective observations
- 17 formation-stage/direction changes
- 9 changes were low-information Stage 0 ↔ Stage 1 flicker
- 8 meaningful Stage-3+ transitions
- 1 Stage-5 arrival
- 1 Stage-6 arrival
- 0 Stage-8 arrivals
- the Stage-6 long state persisted across three snapshots (~45 minutes) before the detector changed into a new short sweep sequence

### GBPUSD
- ~70 prospective observations
- 21 formation-stage/direction changes
- 8 changes were Stage 0 ↔ Stage 1 flicker
- 12 meaningful Stage-3+ transitions
- 0 Stage-5/6/8 arrivals

### Combined finding

17 of 38 observed state changes were only Stage 0 ↔ Stage 1 churn. Treating every state update as equally important would therefore create unnecessary cognitive noise.

The product now suppresses this low-signal churn in the primary timeline and highlights Stage-3+ changes, direction changes involving an active formation, and mature-state arrivals.

## Important data-health finding

The v0.7 health engine correctly measured missing completed bars during an open market, but it interpreted weekend non-production as feed staleness. That is semantically wrong for the user.

v0.8 introduces a separate market-clock layer:
- market open: freshness/lag is evaluated normally
- weekend market closed: the last completed open-market state is preserved and described as market closed, not stale

This is an example of why data quality must understand the market calendar rather than only timestamp distance.

## Product-design research applied

### Apple Human Interface Guidelines

Current Apple guidance emphasizes purpose, simplicity, concise language, hierarchy, progressive disclosure, and presenting a chart's main message before requiring the user to inspect individual data marks.

Applied in v0.8:
- a Research Brief appears before the chart
- the primary view answers what matters now, why, what changed, and what to investigate next
- advanced metrics are behind one disclosure layer
- chart interaction is optional for detail, not required to discover the critical message

References:
- https://developer.apple.com/design/human-interface-guidelines/design-principles
- https://developer.apple.com/design/human-interface-guidelines/charts
- https://developer.apple.com/design/human-interface-guidelines/disclosure-controls

### OpenAI product-design framing

OpenAI's product-design material emphasizes synthesizing research into decisions and converting user goals into flows and design implications.

Applied here by turning raw market-state metrics into a concise research narrative rather than simply exposing more numbers.

Reference:
- https://openai.com/business/plugins/product-design/

### Quant architecture

NautilusTrader's research/live parity and event-driven philosophy continues to inform the lab: events should represent meaningful state changes and the same completed-bar semantics should be used in historical replay and live research.

Qlib's end-to-end research framing continues to inform the separation of data, features, research evidence, and future prediction models.

References:
- https://nautilustrader.io/docs/latest/concepts/architecture/
- https://github.com/microsoft/qlib

## v0.8 experience architecture

The primary workflow is now:

1. **Market status** — open or closed; never confuse weekend closure with bad data.
2. **Pair attention state** — Background / Watchlist / Review now / At location.
3. **Research Brief** — plain-language description of the current formation.
4. **Why it matters** — a few explicit reasons.
5. **Last meaningful change** — event history without Stage-0/1 noise.
6. **What to do next** — an investigation instruction, not a trading instruction.
7. **Overview** — trend + context at a glance.
8. **Chart** — visual verification.
9. **Research** — sample size, mature arrivals, meaningful transitions, methodology.
10. **Data trust** — reference price vs structural candle feed vs unavailable execution truth.

## Why this is better for a future live agent

A future agent should not narrate every five-minute refresh. It should reason over **event significance**.

Examples of agent-worthy events:
- Stage 3 appears after background state
- BOS confirms (Stage 5)
- fresh POI appears (Stage 6)
- direction changes while a formation is active
- context changes from supportive to conflicting
- regime-shift risk becomes elevated/high
- data quality changes during an open market

Examples that should normally be suppressed:
- repeated identical states
- Stage 0 ↔ Stage 1 flicker
- weekend 'staleness' caused solely by market closure

This event-significance layer can eventually support a live analyst agent that answers questions such as:
- What changed since I last looked?
- Which pair deserves attention first?
- Is this formation new or persistent?
- What evidence supports or conflicts with it?
- Has this market state behaved differently in our prospective dataset?

## Statistical boundary

The sample is still early. Approximately 70 observations per pair and one Stage-6 arrival are not enough for live win-rate or forward-return inference.

The correct next data-science progression remains:
1. continue accumulating point-in-time observations
2. identify independent formation episodes, not repeated snapshots
3. attach forward 15m/30m/1h/2h/4h outcomes using the same candle source
4. measure MFE/MAE and stage-to-stage transition probabilities descriptively
5. stratify by session, regime, context alignment, efficiency and shift state only after adequate episode counts
6. use uncertainty intervals and minimum sample requirements
7. only later attempt predictive modeling, with purge/embargo and multiple-testing controls
8. continue to block executable trade claims until broker-quality labels are available

## Current product verdict

v0.8 improves the product mainly by reducing cognitive noise and improving semantic accuracy. The lab is becoming a useful market-research interface, but the strongest future value will come from a growing prospective episode dataset rather than additional indicators.