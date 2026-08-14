# V3.4 Market Intelligence Challenger Protocol

## Purpose

Test whether richer market context improves the frozen V2 midpoint paper-plan baseline without rewriting historical outcomes or cherry-picking rules after seeing results.

## Frozen baseline

- Universe: exact V1.9 POI setup universe from the `v19-poi-penetration` research artifact.
- Markets: EURUSD and GBPUSD.
- Completed evaluation years: 2022, 2023, 2024, 2025.
- Baseline entry: 50% POI midpoint.
- Baseline stop: sweep extreme plus/minus 0.03 ATR.
- Baseline target: 2.5R.
- Historical path source: public M5 OHLC used in the existing V2 research stack.

## New pre-entry context features

Every feature must be computed using data completed no later than the setup BOS time.

1. Structural trend on M15, H1, H4, D1, W1 and MN1 using confirmed swing highs/lows.
2. Existing EMA-style direction retained as a separate comparator.
3. Liquidity map:
   - previous day high/low
   - previous week high/low
   - previous month high/low
   - repeated H4 pivot clusters (equal-high/equal-low proxy)
4. BOS displacement normalized by ATR.
5. Strict three-candle FVG around the BOS impulse.
6. Session classification.
7. POI-candle body/wick quality.
8. Composite context score built only from the preregistered items above.

## Candle confirmation study

Candle confirmation is not allowed to look inside the future of the baseline fill. The variant waits until the M15 candle containing the first midpoint touch has closed. Only then can it classify directional confirmation (engulfing, rejection/hammer/shooting-star-like, or strong directional body). If confirmed, a new research entry is simulated from that close with the frozen structural stop and 2.5R target.

## Public strategy proxies

These are explicitly **not claims of the proprietary paid strategies** of Kojo Forex or Dapo Willis. They encode only rules described publicly enough to make a reproducible research proxy.

### Dapo public proxy

Public-source concepts encoded:
- monthly/weekly major levels
- weekly reversal-pattern family (double top/bottom and head-and-shoulders/inverse proxy)
- higher-timeframe directional agreement
- lower-timeframe H4 candlestick confirmation
- 1:3 research reward/risk

### Kojo public-principles proxy

Public-source concepts encoded:
- market structure
- liquidity sweep concept
- multi-timeframe alignment
- price-action confirmation
- 1:3 research reward/risk

The private GOAT/Gold Digger entry rules are not inferred or reverse-engineered.

## V2 hybrid challengers

- HTF structural alignment filters
- major-liquidity-location filter
- displacement + FVG filter
- active-session filter
- POI-candle-quality filter
- composite context-score thresholds
- Dapo-inspired V2 hybrid
- Kojo-inspired V2 hybrid

## Primary metric

Opportunity expectancy in R per frozen V2 opportunity, not win rate alone. Skipped setups contribute 0R to the challenger so a selective filter cannot look better merely by hiding rejected trades.

Secondary metrics:
- fill rate
- decisive win rate
- pessimistic ambiguity-adjusted R
- sample size
- year-by-year stability
- pair-level stability

## Promotion gate

No challenger changes the production baseline unless all of the following hold:

1. Paired bootstrap lower 95% bound for opportunity-R delta is above zero.
2. At least three of four completed years are non-inferior.
3. EURUSD and GBPUSD are both non-inferior on adequate sample.
4. The improvement is not driven by a very small subgroup.
5. The rule can be computed prospectively with current data integrity.

If a feature is informative but fails the promotion gate, it may be exposed as context/quality information while remaining unable to create, cancel, resize or reroute a baseline trade.
