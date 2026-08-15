# V3.5 Trend + Support/Resistance + Candlestick Engine — Frozen Research Protocol

Status: preregistered before first V3.5 backtest result.

## Purpose
Build a separate price-action challenger that generates its own trades from raw EURUSD/GBPUSD OHLC. It does not depend on V2 sweep/BOS/POI events and cannot alter the baseline V2 engine.

## Public-principles sources translated into testable rules
- KojoForex public material: trend following, support/resistance, breakouts, price action/candlesticks, market structure and multi-timeframe analysis. This study does not claim to reproduce any private or paid Kojo strategy.
- Dapo Willis public material: top-down Monthly/Weekly/Daily context, support/resistance, pullbacks, 50%-61.8% Fibonacci retracement, lower-timeframe candle confirmation, and trend continuation. This study is a public-principles proxy, not his private strategy.
- Fred McAllen / John Murphy: uptrend = rising peaks/troughs, downtrend = declining peaks/troughs, support/resistance and trend lines as core chart structure.
- Steve Nison / Fred K. H. Tam: candlesticks should be interpreted in context and can be combined with Western trend/support-resistance methods; candle signals are not assumed to work in isolation.
- FX research boundary: support/resistance has empirical microstructure support, while candlestick patterns alone have mixed evidence. Therefore V3.5 explicitly tests context-gated candles versus candle-only controls.

## Data
- Symbols: EURUSD, GBPUSD.
- Completed years: 2022, 2023, 2024, 2025.
- Public M5 OHLC from the same frozen source used by V3.4, resampled causally to M15/H1/H4/D1/W1/MN1.
- No current/incomplete bar may be used to create a historical signal.
- Signals are evaluated from the next M5 bar after the completed trigger candle.

## Shared definitions
### Trend
Confirmed 2-left/2-right swing pivots.
- Bullish structure: last confirmed swing high > previous high AND last confirmed swing low > previous low.
- Bearish structure: both lower.
- Otherwise mixed.

EMA20/EMA50 is recorded separately and never substitutes for structural trend in the primary variants.

### Support/resistance zones
At each completed M15 bar, derive only from information available at that time:
1. latest confirmed H4 swing highs/lows;
2. latest confirmed D1 swing highs/lows;
3. prior day high/low;
4. prior week high/low;
5. equal-high/equal-low clusters from confirmed H1/H4 pivots.

A price is 'at' a zone when its distance is <= 0.30 H1 ATR. Multiple nearby levels are merged into one zone. A zone broken by a completed H1 close > 0.15 H1 ATR beyond it changes role and may be used as a breakout-retest level.

### Candlestick triggers on completed M15 bars
Mathematical, reproducible definitions only:
- bullish engulfing / bearish engulfing;
- hammer-like / shooting-star-like rejection: dominant wick >=45% of range and >=1.8x body;
- strong directional body: body >=60% of candle range and close in directional outer 25% of range;
- doji is recorded but is not an entry trigger.

### Risk
- Entry: next M5 open after the completed M15 trigger.
- Structural stop: beyond the reaction zone or most recent M15 swing, whichever is farther, plus 0.10 M15 ATR.
- Reject risk <0.10 ATR or >2.00 ATR.
- One active trade per symbol per strategy family; no stacking duplicate signals while a trade is open.
- Same-M5-bar stop/target ambiguity is pessimistically counted as a loss for the primary metric; also report an ambiguity-neutral metric.
- Maximum hold: 96 M15 bars (24h). Timeout exits at final available close and records realized R.

## Frozen strategy families

### A. TCR — Trend Context Rejection
Goal: trend-following pullback into meaningful support/resistance.

Long:
1. D1 structure bullish.
2. H4 structure bullish OR mixed with bullish EMA20>EMA50 and positive 20-bar slope.
3. M15 trades into a support zone.
4. Completed M15 bullish engulfing, hammer-like rejection, or strong bullish body forms at the zone.
5. Entry next M5 open.

Short is symmetric.

Primary target: 2.5R.
Also report 2R and 3R outcome sensitivity without choosing a winner after the fact.

### B. BRC — Breakout Retest Continuation
Goal: trade a trend-aligned break of support/resistance after a retest.

Long:
1. D1 direction bullish or H4+D1 both bullish.
2. Completed M15/H1 close breaks resistance by >=0.10 H1 ATR.
3. Within the next 8 M15 bars price retests the broken zone within 0.30 H1 ATR.
4. A completed bullish candle trigger forms on the retest.
5. Entry next M5 open.

Short is symmetric.

Primary target: 2.5R.

### C. DFP — Dapo Public-Principles Fibonacci Pullback Proxy
Not a claim to reproduce Dapo Willis's private/paid strategy.

Long:
1. D1 structure bullish.
2. Latest completed H4 impulse is bullish and at least 1.25 H4 ATR from confirmed swing low to swing high.
3. Pullback reaches 50%-61.8% of that impulse without closing beyond the 78.6% level.
4. Fib pocket overlaps a support zone within 0.35 H1 ATR.
5. Completed M15 bullish engulfing/rejection/strong-body trigger occurs in the pocket.
6. Entry next M5 open.

Short is symmetric.

Primary target: 3R, with 2.5R sensitivity reported.

### D. KOJO-PX — Kojo Public-Principles Price-Action Proxy
Not a claim to reproduce KojoForex's private/paid strategy.

1. H4 structural trend is bullish/bearish.
2. Price is at a support/resistance zone in the trend direction or has just retested a broken level.
3. M15 price action trigger agrees with trend.
4. M15 must not close through the invalidation side of the zone.
5. Entry next M5 open.

Primary target: 3R, matching the public 1:3 framing used in Kojo materials.

### E. CANDLE-ONLY negative control
Same candle definitions, no trend, no support/resistance. Entry next M5 open in candle direction, fixed ATR structural stop, 2.5R target. This exists to test whether candle shapes add value by themselves.

## Ablations
For TCR and DFP report:
- trend only;
- trend + support/resistance without candle gating;
- trend + candle without support/resistance;
- full contextual strategy;
- engulfing only;
- rejection only;
- strong body only.

These are descriptive ablations, not post-hoc promotion candidates.

## Metrics
For each family, symbol, year, and pooled sample:
- signals, entered trades, wins, losses, timeouts, ambiguous bars;
- decisive win rate;
- mean R/trade;
- median R;
- profit factor;
- max drawdown in R under sequential 1R risk units;
- annual results;
- long/short split;
- session split;
- target sensitivity where specified.

## Promotion gate
A V3.5 family may be labeled historically promising only if ALL hold:
1. >=200 trades pooled and >=50 trades in each symbol;
2. mean R > +0.10R at the frozen primary target;
3. profit factor >1.10;
4. positive mean R in at least 3 of 4 years;
5. both symbols have non-negative mean R;
6. full contextual variant materially exceeds its candle-only control;
7. bootstrap 95% CI for pooled mean R excludes 0 OR walk-forward yearly behavior is consistently positive enough to justify prospective shadowing.

Historical promotion does NOT authorize broker execution. Any historically promising family enters prospective paper/shadow mode first.

## Live architecture if implemented
- Separate engine name: `trend-candle-engine`.
- Separate snapshots/trades from baseline V2.
- No automatic interaction with baseline paper account.
- UI labels it as a challenger engine with its own state and historical/prospective evidence.
- Discord may send challenger alerts only when a complete rule set triggers; alerts must say `Trend-Candle Challenger` and never masquerade as a baseline V2 trade.
