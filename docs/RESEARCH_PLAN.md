# V2 Trading Research Plan

## 1. Objective

The objective is not to build a bot that looks profitable in a backtest. It is to test whether the recovered V2 market-structure idea contains an edge that survives point-in-time data controls, realistic costs, walk-forward validation, new market regimes, and live shadow observation.

The frozen V2 engine stays separate. New models may score, rank, explain, or reject a V2 opportunity in research, but they do not silently change the original V2 rules.

Primary target for the meta-model:

> Given that V2 has fired a valid setup, estimate P(2.5R target is reached before the stop | information known by entry time).

This is a better statistical problem than forecasting every next candle.

## 2. Recovered baseline

The recovered enriched ledger contains 2,227 V2 trades from 2020 through July 2026 and 132 columns. The historical aggregate is approximately:

- win rate: 48.72%
- expectancy: 0.656R/trade after recovered spread cost
- profit factor: about 2.23
- maximum drawdown in the full recovered report: about 11.54R

The ledger contains `spread_as_r`. It does not prove realistic slippage, queueing, partial fills, or intrabar stop/target ordering.

## 3. Leakage audit before modeling

A mandatory rule is that every feature must answer: **could this value have been known at the exact entry timestamp?**

The first audit already found a severe research leak: `m15_v2_setup_score` is numerically identical to `net_r`, the realized trade outcome. It is now explicitly blacklisted together with exit fields, MFE/MAE, post-exit continuation fields, and all realized-return fields.

The pipeline should fail loudly if a blacklisted feature is requested.

## 4. Data architecture

### 4.1 Price and execution data

Research hierarchy:

1. Broker/MT5 M1 and M15 history from the same broker family used for live execution.
2. Independent Dukascopy tick/bid-ask history for robustness checks.
3. M1 reconstruction for any M15 trade where stop and target can both be touched inside one bar.
4. Tick replay for final execution validation on ambiguous cases and a representative OOS sample.

Every dataset must record source, timezone, symbol mapping, bid/ask convention, gaps, duplicate treatment, and retrieval timestamp.

### 4.2 Macro data

Candidate point-in-time features:

- US nominal 2Y/10Y yields
- US real yields where available
- yield-curve slope
- VIX/risk stress
- oil/energy returns and volatility
- USD broad/index proxy
- rate differentials relevant to EURUSD and GBPUSD
- gold-specific opportunity-cost and dollar variables
- central-bank decision and macro-release surprise variables

Do not train on revised macro values as if they were known historically. Prefer ALFRED vintages or release-time snapshots. Same-day end-of-day series must be lagged for intraday trades.

### 4.3 Economic-calendar events

For CPI, payrolls, GDP, unemployment, rate decisions, PMIs and similar releases, store:

- event timestamp
- country/currency
- actual
- consensus forecast
- prior value as known before release
- standardized surprise = (actual - consensus) / historical surprise volatility
- minutes before/after entry
- first 1m/5m/15m market reaction

Research should test surprise magnitude, not merely whether an event existed. Recent exchange-rate research finds unexpected monetary-policy decisions have larger immediate effects than expected ones.

### 4.4 News and geopolitical data

News is a contextual state, not a direct buy/sell command.

Historical training requires a point-in-time news archive such as GDELT bulk Event/GKG data or another licensed archive. GDELT DOC 2.0 is useful for recent/shadow monitoring but is officially a rolling recent-news API, so it must not be treated as a complete 2020-2026 training archive.

Candidate event families:

- geopolitical conflict/escalation/ceasefire
- central banks/rate path
- inflation/employment/growth
- oil/energy supply shock
- banking/credit stress
- sovereign/political risk
- central-bank gold demand

For XAUUSD, generic positive/negative FinBERT sentiment is not sufficient. "Strong dollar", "higher real yields", an oil shock, and a war headline have asset-specific meanings and interactions. Build asset-specific direction/relevance labels.

## 5. Model stack

### Model A: frozen V2 event engine

The original M15 sequence remains the event generator:

liquidity sweep -> BOS -> fresh POI -> midpoint/risk entry -> stop -> fixed 2.5R target.

### Model B: V2 meta-labeler

Start with interpretable tabular models because the recovered dataset has only 2,227 trade events.

Baselines:

- logistic regression
- LightGBM

Target: win/loss before costs and net outcome after modeled costs.

Initial features:

- instrument
- direction
- risk distance
- spread as R
- entry hour/day
- time from sweep to BOS
- POI timing
- bars to entry

HTF features are evaluated as an additive group rather than assumed useful.

### Model C: regime model

Candidate methods:

- deterministic volatility/trend buckets first
- Hidden Markov Model only if it improves OOS stability

Regime should capture trend/range, volatility, liquidity session, risk stress, and macro state.

### Model D: news/macro model

Produce an independent state vector, not a trade by itself. Examples:

- central-bank hawkish/dovish surprise
- normalized macro surprise
- conflict/news-volume z-score
- news tone and asset-specific relevance
- real-yield impulse
- USD impulse
- oil-shock impulse

### Model E: time-series foundation model research

Kronos is specifically designed for financial candlesticks. Chronos-class models can also be tested for probabilistic time-series forecasts. They should initially produce features such as expected return distribution, volatility forecast and path asymmetry. They do not get authority over trading until they beat simple baselines OOS.

### Final stack

V2 event + entry-time market features + point-in-time macro/news + optional TSFM forecasts -> calibrated meta-probability -> research confidence tier.

## 6. Validation protocol

No random train/test shuffle.

1. Expanding walk-forward years.
2. Purged time-series validation around overlapping trades.
3. Leave-one-year-out robustness.
4. Leave-one-symbol-out robustness.
5. Parameter perturbation around V2 thresholds.
6. Spread/slippage stress.
7. M1/tick replay on ambiguous M15 outcomes.
8. Probability calibration and Brier score.
9. Deflated Sharpe / multiple-testing controls for strategy searches.
10. Frozen shadow period with no rule changes.

The final untouched test period must be selected before the final model is fitted.

## 7. Acceptance gates

A research model advances only if:

- its OOS ranking is stable across years and symbols;
- improvement is not concentrated in one instrument or one year;
- results remain positive under cost stress;
- probability calibration is acceptable;
- no point-in-time leakage is found;
- M1/tick replay does not materially reverse results;
- a shadow period confirms similar signal quality.

No live-money auto-execution before those gates.

## 8. Product path

Research app first:

- current instrument state
- latest V2 opportunities
- model probability/confidence tier
- market regime
- macro/news context
- reason codes
- historical calibration/performance
- alert feed

Notifications should be phrased as research alerts such as "V2 setup detected / confidence 0.64 / major CPI release in 18 min" rather than guaranteed buy/sell calls.
