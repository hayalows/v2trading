# V3.4 Market Intelligence Findings

## Decision

V3.4 improves what V2 can **see**, but the 2022–2025 challenger study did not justify changing the frozen baseline trade rules.

The production midpoint entry, structural stop and 2.5R target remain unchanged. Monthly/weekly structure, liquidity, displacement, FVG, candle state, POI penetration and public Kojo/Dapo strategy proxies are promoted only as context and prospective research features.

## Test design

- Frozen universe: exact V1.9 POI setup universe.
- Markets: EURUSD and GBPUSD.
- Completed years: 2022–2025.
- Frozen opportunities: 2,090.
- Baseline: 50% POI midpoint, sweep-extreme structural stop, 2.5R target.
- Path evidence: public M5 OHLC, with ambiguity retained where sequence could not be proved.
- New features were computed only from information available by setup BOS time.
- Primary comparison: R per frozen V2 opportunity. A skipped setup contributes 0R, so selective rules cannot look better merely by hiding rejected trades.

## Baseline

- Filled: 1,715 / 2,090 (82.06%).
- Decisive outcomes: 801.
- Decisive win rate: 33.46%.
- Opportunity expectancy: +0.06555R per frozen setup.

## Higher-timeframe structure

A binary requirement for higher-timeframe agreement was rejected.

- 2+ HTF structural agreements selected 732 setups and had a 34.08% decisive win rate, but paired opportunity delta was -0.04091R with a 95% interval of roughly -0.0773R to -0.0053R.
- 3+ agreements was worse as a gate.
- The relationship was not monotonic. Zero aligned HTFs, one aligned HTF, two, and three did not form a clean increasing sequence.

**Production interpretation:** V2 now keeps Monthly, Weekly, Daily, H4, H1 and M15 structural states separately. Agreement and conflict are descriptive. No single master trend is allowed to erase a valid lower-timeframe structure.

## Displacement and FVG

These are useful characteristics, especially displacement, but not safe binary entry filters yet.

- Strong displacement setups: 35.50% decisive wins and +0.08594R opportunity expectancy.
- Setups without strong displacement: 28.86% decisive wins and +0.00476R.
- FVG present: 34.57% decisive wins and +0.07440R.
- No FVG: 32.70% and +0.05867R.
- Requiring displacement + FVG as a hard gate still produced a negative paired opportunity delta (-0.03947R).

**Production interpretation:** displacement and FVG are shown in POI context and logged prospectively. They do not cancel or create a trade.

## POI candle quality

The POI-candle quality subset reached 34.43% decisive wins and +0.08208R, versus a weaker complement, but the paired filter delta was -0.02368R and its confidence interval crossed zero.

**Production interpretation:** POI candle body/wick behavior remains a quality descriptor, not a gate.

## Generic candlestick confirmation

Waiting for a completed M15 confirmation candle after the midpoint touch was strongly rejected.

- Confirmed delayed entries: 105.
- Decisive win rate: 17.98%.
- Mean R: -0.2136R.

Engulfing, hammer-like, shooting-star-like and generic strong-body confirmation did not justify delaying the frozen midpoint entry. A tiny strong-bull subgroup looked better but was far too small to promote.

**Production interpretation:** V2 classifies M15/H1/H4 candle state but does not wait for a generic candle pattern before entering.

## Liquidity

Simple proximity to a previous-day/week/month or equal-high/equal-low level was not enough.

- The major-liquidity proximity subset underperformed as a binary gate.

**Production interpretation:** the live map now distinguishes buy-side from sell-side liquidity, above vs below current price, untouched targets vs recently swept/rejected vs traded-through levels, and distance in pips/ATR. "Near liquidity" is not treated as automatically bullish or bearish.

## Composite context

A medium-high context score did identify richer subsets, but additive confirmation was not monotonic.

- Context score 4+: 37.01% decisive wins and +0.10981R on selected setups.
- Paired opportunity delta: -0.02967R, so it failed promotion.
- Context score 6 performed poorly, showing that "more confirmations" is not automatically better.

**Production interpretation:** V2 exposes the ingredients rather than collapsing everything into an overconfident single score.

## Public Kojo Forex and Dapo Willis proxies

These are reproducible proxies built only from public principles. They are not claims about private, paid or proprietary systems.

### Kojo public-principles proxy

Encoded market structure, liquidity sweep concepts, multi-timeframe context, price-action confirmation and a 1:3 research target.

- Standalone proxy sample: 322.
- Mean R: +0.06338R.
- V2 Kojo-style hybrid selected a richer subset (38.24% decisive wins), but the hard filter lost opportunity expectancy and did not pass the promotion gate.

### Dapo public proxy

Encoded monthly/weekly major levels, higher-timeframe reversal/location ideas, lower-timeframe confirmation and a 1:3 research target.

- Standalone proxy sample: 55.
- Mean R: +0.09279R.
- The V2 Dapo-style hybrid sample was too small and failed the hard-gate test.

**Decision:** keep both as challenger research families and continue prospective logging. Do not claim either proxy reproduces the trader's private method.

## What is live now

The V3.4 market-intelligence layer now provides:

- structural trend: M15, H1, H4, D1, W1, MN1;
- EMA direction as a separate comparator;
- previous day/week/month liquidity;
- H4 equal-high/equal-low clusters;
- buy-side/sell-side classification;
- nearest liquidity above and below current price;
- swept/rejected/traded-through state;
- current weekly/monthly premium-discount location;
- M15/H1/H4 candle classification;
- FVG and BOS displacement context;
- direction-aware POI penetration/location;
- explicit agreement/conflict counts without forcing universal HTF alignment.

The `market-intelligence-runner` freezes prospective snapshots every 15 minutes for Stage 3+ states, linking them to active campaigns/trades where possible. This creates an auditable record of what V2 knew before future outcomes.

## Promotion policy

No V3.4 challenger changes a trade unless a future preregistered test clears the promotion criteria. Market-intelligence context cannot create, cancel, resize or reroute the frozen baseline paper plan.
