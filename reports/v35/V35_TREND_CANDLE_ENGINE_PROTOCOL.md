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
5. equal-high/equal-low clusters from confirmed H4 pivots.

A price is 'at' a zone when its distance is <= 0.30 H1 ATR. Nearby level overlap is treated as a zone rather than as false precision. A completed breakout > 0.10 H1 ATR beyond a known level may create a breakout-retest candidate.

### Candlestick triggers on completed M15 bars
Mathematical, reproducible definitions only:
- bullish engulfing / bearish engulfing;
- hammer-like / shooting-star-like rejection: dominant wick >=45% of range and >=1.8x body;
- strong directional body: body >=60% of candle range and close in directional outer 25% of range;
- doji is recorded but is not an entry trigger.

### Risk
- Entry: next M5 open after the completed M15 trigger.
- Structural stop: beyond the reaction zone or most recent rolling M15 swing, whichever is farther, plus 0.10 M15 ATR.
- Candle-only control uses a fixed 1.0 M15 ATR stop so it does not inherit support/resistance information.
- Reject risk <0.10 ATR or >2.00 ATR.
- One active trade per symbol per strategy family; no stacking duplicate signals while a trade is open.
- Same-M5-bar stop/target ambiguity is pessimistically counted as a loss for the primary metric; also report an ambiguity-neutral metric.
- Maximum hold: 24 calendar hours. Timeout exits at the final available M5 close inside that window and records realized R.

## Frozen strategy families

### A. TCR — Trend Context Rejection
Goal: trend-following pullback into meaningful support/resistance.

Long:
1. D1 structure bullish.
2. H4 structure bullish OR mixed with bullish EMA20>EMA50 and positive 20-bar EMA slope.
3. M15 trades into a support zone.
4. Completed M15 bullish engulfing, hammer-like rejection, or strong bullish body forms at the zone.
5. Entry next M5 open.

Short is symmetric.

Primary target: 2.5R.
Also report 2R and 3R outcome sensitivity without choosing a winner after the fact.

### B. BRC — Breakout Retest Continuation
Goal: trade a trend-aligned break of support/resistance after a retest.

Long:
1. D1 structure bullish.
2. Completed M15 close breaks known resistance by >=0.10 H1 ATR.
3. Within the next 8 M15 bars price retests the broken level within 0.30 H1 ATR.
4. A completed bullish candle trigger forms on the retest and does not close >0.15 H1 ATR back through the failed side.
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
2. Price is at a support/resistance zone in the trend direction.
3. M15 price-action trigger agrees with trend.
4. M15 must not close >0.15 H1 ATR through the invalidation side of the zone.
5. Entry next M5 open.

Primary target: 3R, matching the public 1:3 framing used in Kojo materials.

### E. CANDLE-ONLY negative control
Same candle definitions, no trend, no support/resistance. Entry next M5 open in candle direction, fixed 1.0 M15 ATR stop, 2.5R target. This exists to test whether candle shapes add value by themselves.

## Frozen ablations
TCR:
- `TCR_TREND_ONLY_2.5R`: enter only on a newly established D1+H4 aligned trend state.
- `TCR_SR_NO_CANDLE_2.5R`: trend + support/resistance, no candle gate.
- `TCR_CANDLE_NO_SR_2.5R`: trend + candle, no support/resistance gate.
- `TCR_2.5R`: full contextual strategy.
- Trigger-type results are reported separately for engulfing, rejection and strong-body signals.

DFP:
- `DFP_NO_SR_3R`: D1 trend + H4 50%-61.8% pullback + candle, no support/resistance overlap requirement.
- `DFP_NO_CANDLE_3R`: D1 trend + H4 50%-61.8% pullback + support/resistance overlap, no candle requirement.
- `DFP_3R`: full contextual strategy.
- Trigger-type results are reported separately.

These are descriptive ablations, not post-hoc promotion candidates.

## Metrics
For each family, symbol, year, and pooled sample:
- entered trades, wins, losses, timeouts, ambiguous bars;
- decisive win rate excluding ambiguous bars;
- pessimistic win rate counting same-bar ambiguity as a loss;
- mean R/trade under pessimistic ambiguity treatment;
- ambiguity-neutral mean R;
- median R;
- profit factor;
- max drawdown in R under sequential 1R risk units;
- bootstrap 95% CI for mean R;
- annual results;
- long/short split;
- session split;
- trigger-type split;
- target sensitivity where specified.

## Promotion gate
A V3.5 primary family may be labeled historically promising only if ALL hold:
1. >=200 trades pooled and >=50 trades in each symbol;
2. mean R > +0.10R at the frozen primary target;
3. profit factor >1.10;
4. positive mean R in at least 3 of 4 years;
5. both symbols have non-negative mean R;
6. pooled mean R exceeds the candle-only control by at least +0.05R/trade;
7. bootstrap 95% CI lower bound for pooled mean R is above 0 OR all four yearly mean-R results are positive.

Historical promotion does NOT authorize broker execution. Any historically promising family enters prospective paper/shadow mode first.

## Live architecture if implemented
- Separate engine name: `trend-candle-engine`.
- Separate snapshots/trades from baseline V2.
- No automatic interaction with baseline paper account.
- UI labels it as a challenger engine with its own state and historical/prospective evidence.
- Discord may send challenger alerts only when a complete rule set triggers; alerts must say `Trend-Candle Challenger` and never masquerade as a baseline V2 trade.
