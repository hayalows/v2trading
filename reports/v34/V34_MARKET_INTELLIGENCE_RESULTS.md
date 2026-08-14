# V3.4 Market Intelligence Results

Date: 2026-08-14

## Research run

- Workflow: `v34-market-intelligence`
- Successful run: `31800947793`
- Job: `94768530514`
- Artifact: `v34-market-intelligence`
- Artifact ID: `9219544249`
- Artifact digest: `sha256:91f8d8fd4ba707773785fdf6f4e3224d62945415e7e71ea679cd5425a9d26d94`
- Frozen input universe: V1.9 POI research universe, same baseline entry/stop/target geometry.
- Completed years: 2022-2025.
- Markets: EURUSD, GBPUSD.
- Baseline risk-valid 50% POI opportunities: 2,090.

The study protocol was frozen before the first completed run in `V34_MARKET_INTELLIGENCE_PROTOCOL.md`.

## Frozen baseline

| Metric | Result |
|---|---:|
| Opportunities | 2,090 |
| Filled | 1,715 |
| Fill rate | 82.06% |
| Decisive outcomes | 801 |
| Decisive win rate | 33.46% |
| Opportunity expectancy | +0.06555R |
| M5 ambiguity rate among fills | 53.29% |

Opportunity expectancy was positive in all four completed years:

- 2022: +0.0561R
- 2023: +0.1312R
- 2024: +0.0117R
- 2025: +0.0594R

By pair:

- EURUSD: +0.05447R/opportunity
- GBPUSD: +0.07610R/opportunity

The high historical M5 ambiguity rate reinforces the separate V2 BID/ASK execution-audit work. These results remain public-price research, not broker execution truth.

## Main conclusion

**No V3.4 hard filter passed the preregistered promotion gate.**

The richer context contains useful information, but none of the tested rules should universally cancel a valid baseline V2 plan. Selective filters can show a higher win rate or higher R on the trades they retain while still reducing total opportunity expectancy by skipping other historically positive V2 opportunities.

Accordingly, the V2 50% midpoint, structural stop and 2.5R baseline remain unchanged.

## Challenger results

| Challenger | Selected n | Win rate | Selected R/opportunity | Paired delta vs baseline | 95% bootstrap interval | Decision |
|---|---:|---:|---:|---:|---:|---|
| HTF structure >=2 aligned | 732 | 34.08% | +0.07036R | -0.04091R | [-0.07727, -0.00526] | Reject hard gate |
| HTF structure >=3 aligned | 143 | 34.09% | +0.05944R | -0.06148R | [-0.10622, -0.02081] | Reject hard gate |
| Major liquidity location | 487 | 32.28% | +0.05031R | -0.05383R | [-0.09499, -0.01542] | Reject hard gate |
| Displacement + FVG | 695 | 35.59% | +0.07842R | -0.03947R | [-0.07751, -0.00311] | Context only |
| Active session | 1,303 | 32.65% | +0.05833R | -0.02919R | [-0.05502, -0.00431] | Reject hard gate |
| POI candle quality | 1,066 | 34.43% | +0.08208R | -0.02368R | [-0.05467, +0.00611] | Context only |
| Context score >=3 | 1,344 | 34.84% | +0.08296R | -0.01220R | [-0.03923, +0.01376] | Shadow/context only |
| Context score >=4 | 683 | 37.01% | +0.10981R | -0.02967R | [-0.06711, +0.00563] | Shadow/context only |
| Context score >=5 | 237 | 35.37% | +0.08228R | -0.05622R | [-0.10024, -0.01579] | Reject hard gate |
| V2 + Dapo-inspired hybrid | 32 | 33.33% | +0.07813R | -0.06435R | negative interval | Reject / too small |
| V2 + Kojo-inspired hybrid | 99 | 38.24% | +0.11616R | -0.06005R | [-0.10456, -0.01770] | Shadow only |

## Higher-timeframe structure finding

Higher-timeframe structural agreement was **not monotonic** with performance:

- 0 aligned HTFs: +0.10271R/opportunity
- 1 aligned HTF: +0.04372R
- 2 aligned HTFs: +0.07301R
- 3 aligned HTFs: +0.05944R

There was also strong pair heterogeneity. For example, the `>=2 aligned` subgroup was about -0.0173R on EURUSD but +0.14935R on GBPUSD.

Therefore V2 must not use a universal rule such as `only trade in the Monthly/Weekly direction`. Monthly/Weekly structure is now part of the market map and prospective research state instead.

## Displacement and FVG

These are useful quality features, especially displacement.

### FVG

- No FVG: +0.05867R, 32.70% decisive win rate
- FVG: +0.07440R, 34.57% decisive win rate

### Strong BOS displacement

- No strong displacement: +0.00476R, 28.86% decisive win rate
- Strong displacement: +0.08594R, 35.50% decisive win rate

This is one of the clearest V3.4 quality findings. It is now captured in the live market-intelligence context, but it is not allowed to veto or create a baseline trade.

## POI candle quality

POI candle body/wick quality was modestly positive overall:

- lower-quality subgroup: +0.04834R
- higher-quality subgroup: +0.08208R

But the effect was pair-dependent. It was much stronger historically for GBPUSD than EURUSD, so a universal hard gate is not justified.

## Session finding

A simple London/New York active-session rule did not improve the baseline:

- active-session subgroup: +0.05833R
- other-session subgroup: +0.07751R

Session remains descriptive context rather than a trade gate.

## Candlestick-confirmation test

The tested rule waited for the M15 candle containing the first midpoint touch to close, required a directional candlestick confirmation, then entered at that close using the frozen structural stop and 2.5R target.

Result:

- n = 105
- wins = 16
- losses = 73
- timeouts = 16
- decisive win rate = 17.98%
- mean R = **-0.21360R**

Pattern groups tested included bullish/bearish engulfing, hammer-like rejection, shooting-star-like rejection and strong directional bodies. None had enough robust evidence to justify delaying the baseline entry. A seven-case strong-bull subgroup was positive but far too small to promote.

**Decision: do not add a generic `wait for candlestick confirmation after midpoint` rule.** Candle shape remains a contextual feature only.

## Public-strategy proxy tests

These are transparent research proxies built only from sufficiently public principles. They are not claims about either trader's private or paid system.

### Dapo public proxy

- n = 55
- decisive win rate = 20.45%
- mean R = +0.09279R at 3R target

Year behavior was inconsistent:

- 2023: -0.111R
- 2024: +0.413R
- 2025: -0.457R

Pair behavior also diverged:

- EURUSD: -0.326R
- GBPUSD: +0.236R

Decision: research only; too sparse and unstable for production.

### Kojo public-principles proxy

- n = 322
- decisive win rate = 21.76%
- mean R = +0.06338R at 3R target

By year:

- 2022: -0.1958R
- 2023: +0.2142R
- 2024: +0.1366R
- 2025: +0.0855R

By pair:

- EURUSD: +0.02097R
- GBPUSD: +0.11023R

Decision: worthy of prospective shadow observation, not a production trade rule. The test represents public market-structure/liquidity/multi-timeframe concepts, not private GOAT/Gold Digger logic.

## Live V3.4 market map

A new protected `market-intelligence` Edge Function has been deployed. It calculates and stores descriptive context for each pair:

- M15 structural trend + EMA trend
- H1 structural trend + EMA trend
- H4 structural trend + EMA trend
- D1 structural trend + EMA trend
- W1 structural trend + EMA trend
- MN1 structural trend + EMA trend
- previous day/week/month highs and lows
- repeated H4 high/low clusters
- nearest liquidity levels normalized by ATR
- Asia/London/New York research ranges
- M15/H1/H4 candle body/wick classifications
- BOS displacement
- strict three-candle FVG diagnostics
- POI candle characteristics and freshness when a POI exists

The Monthly/Weekly source removes non-positive OHLC values before structural aggregation.

The market map is explicitly descriptive. `tradeRulesChanged=false`.

## Prospective learning

A new service-only `market_intelligence_snapshots` table freezes context on live Stage-3+ formations. Each snapshot can link to the active formation campaign and later paper trade. This allows future analysis to compare setup outcome against the exact context known before the result.

The recurring runner is scheduled on completed M15 boundaries. This creates the evidence needed to learn pair-specific and regime-specific interactions instead of hard-coding assumptions from the historical pool.

## Production policy after V3.4

1. Keep the baseline V2 entry/stop/target unchanged.
2. Use Monthly/Weekly structure as context, not a universal directional veto.
3. Expose strong displacement, FVG, liquidity location, POI candle quality and session context to the research/brief layer.
4. Freeze these features prospectively for every live formation.
5. Keep Kojo/Dapo proxies as challengers/shadows until prospective evidence is materially larger.
6. Do not delay midpoint entry for generic candlestick confirmation.
7. Continue improving execution truth with BID/ASK evidence because historical M5 ambiguity remains substantial.
