# V2 Intelligence Lab v1.2 — Live Campaign Audit

Audit timestamp: 2026-08-10 10:36 UTC

## Why this upgrade exists

v1.1 correctly stopped counting every five-minute refresh as a new opportunity, but it still treated each new liquidity sweep as an independent episode. The live stream showed that this is too aggressive for inference: several same-direction sweeps can occur inside one continuous Stage-3+ market sequence, and their one-hour outcome windows overlap.

v1.2 therefore separates two units:

1. **Sweep event** — every distinct detected liquidity sweep is retained.
2. **Formation campaign** — one continuous same-direction Stage-3+ sequence, ending only on a structure reset or direction flip.

Outcome inference uses at most one earliest qualifying outcome per campaign. Raw sweep outcomes remain visible as diagnostics.

## Live data accumulated so far

### EURUSD

- 302 timestamped state observations in the current audit window.
- 5 sweep events.
- 3 continuous formation campaigns.
- 1 campaign reached Stage 5 and Stage 6.
- 3 independent Stage-3 campaign outcomes have at least one hour of forward data.
- Raw Stage-3 sweep outcomes: 5.
- Campaign compression: 5 raw outcomes → 3 independent campaign observations.

### GBPUSD

- 302 timestamped state observations in the current audit window.
- 13 sweep events.
- 5 continuous formation campaigns.
- 1 campaign reached Stage 5 and Stage 6.
- 5 independent Stage-3 campaign outcomes have at least one hour of forward data.
- Raw Stage-3 sweep outcomes: 12 at the audit time.
- Campaign compression: 12 raw outcomes → 5 independent campaign observations.

### Combined

- 604 recent prospective state observations.
- 18 sweep events.
- 8 continuous campaigns.
- 2 campaigns reached Stage 6.
- Stage-6 independent evidence: 2/10 minimum display gate.

## Current market state at the audit

### EURUSD

- Stage 0 / no active V2 formation.
- D1 bullish.
- H4 bullish.
- H1 bullish.
- M15 mixed.
- Regime: transition.
- Structure feed current with zero recent gaps and zero recent duplicates.

### GBPUSD

- Stage 4 short — waiting for BOS.
- Current continuous short campaign began around 07:25 UTC.
- Four distinct sweep events occurred inside the same campaign, from the first sweep around 07:00 UTC through the latest around 09:15 UTC.
- D1/H4/H1/M15 are all bullish at the audit time.
- Detector diagnostic: higher-timeframe context is **conflicting**, dominant context bullish.
- Regime: transition.
- Structure feed current with zero recent gaps and zero recent duplicates.

The v1.2 research priority is therefore **Observe · counter-context**. It instructs the user to wait for BOS and not anticipate the short break. Counter-context status is a review flag only; the sample is too small to promote it into a proven performance filter.

## Statistical correction

The old Stage-3 GBP denominator could reach 12 because several sweep events appeared within 15–60 minutes of each other. Those observations share large portions of the same forward price path. Treating them as independent would create pseudo-replication and make the evidence mature too quickly.

v1.2 gates on continuous campaigns instead:

- EURUSD Stage 3: 5 raw sweep outcomes → 3 campaign observations.
- GBPUSD Stage 3: 12 raw sweep outcomes → 5 campaign observations.

No Stage-3 percentage is shown for either pair because neither has 10 completed campaign observations.

## Product changes

- Campaign age and sweep count are first-class on mobile.
- Evidence cards show both independent campaign count and raw sweep-outcome count.
- Repeated sweeps remain visible in the timeline but cannot inflate the inference denominator.
- Context conflict now changes the research priority copy to `Observe · counter-context` or `Review · counter-context`.
- No buy/sell signal and no win probability is produced.

## Remaining blocker

Broker-specific execution truth is still unavailable. Public completed-candle structure can support prospective structure research and campaign-level forward movement analysis, but not trustworthy live PnL, fill, spread, slippage or stop/target ordering claims.
