# V3.6 Zero-Base Quant Discovery Protocol

Status: **FROZEN BEFORE FIRST V3.6 RESULT**

Purpose: search for a repeatable EURUSD/GBPUSD strategy with a meaningfully higher win rate **and** positive net expectancy without using any prior V2/V3 setup, stage, POI, sweep, BOS, candlestick-engine, Kojo/Dapo proxy, or prior trade outcome as a feature.

## Research boundary

This is a new study from raw public market data. Previous V2/V3 engines may be compared only after the V3.6 candidate is frozen. They cannot define entries, features, labels, filters, stops, targets, or ranking.

No strategy is promoted merely because it has a high in-sample win rate. A 70% win-rate strategy with negative expectancy is rejected.

## Data

Primary source: Dukascopy public historical **bid** OHLCV via `dukascopy-node`.

Primary universe: EURUSD and GBPUSD.

Primary history target: 2005-01-01 through 2025-12-31, or the maximum common clean history actually returned by the provider.

Primary discovery bars: M15. Finalist sequencing check: M5 over 2015-2025 when feasible.

Flat weekend bars are excluded. Data are UTC. Only information known at the completed signal bar may be used.

## Chronological partitions

The study is chronological, never random-shuffled.

- Discovery/training: 2005-2016.
- Validation/model selection: 2017-2020.
- Confirmation: 2021-2022.
- **Untouched final holdout: 2023-2025.**

The final holdout is opened only after candidate family, direction logic, stop, target/RR, probability/score threshold and trading-hours rule are frozen from pre-2023 data.

For ML, yearly expanding-window predictions are used; the model for a year may train only on prior years. No future bar from the evaluated year enters fitting or scaling.

## Transaction-cost model

Because the historical source is bid OHLC, net results must deduct conservative round-trip friction:

- EURUSD baseline: 0.8 pip/trade.
- GBPUSD baseline: 1.0 pip/trade.
- stress test: 1.5 pips EURUSD and 2.0 pips GBPUSD.

Finalists must remain positive under baseline costs; preferred candidates remain positive under stress costs.

## Candidate hypothesis families

The search is deliberately broader than chart-pattern trading and is generated only from raw price/time/volume and the companion USD pair:

1. time-series momentum / trend continuation;
2. Donchian/range breakout;
3. volatility-compression breakout;
4. pullback-with-trend continuation;
5. short-horizon mean reversion / z-score exhaustion;
6. previous-day high/low breakout;
7. previous-day false-break/reversion;
8. Asian-range London breakout;
9. intraday/session continuation or reversal;
10. round-number breakout/reversion;
11. cross-pair USD-common-factor confirmation/divergence using EURUSD and GBPUSD only;
12. cost-aware statistical/ML meta-selection from lagged raw-price features.

The rule grid may vary only the preregistered lookbacks/threshold sets contained in the source code. The final report must publish the number of configurations tested.

## Raw feature families for the ML challenger

Only causal features calculated from raw bars:

- lagged returns: 1, 2, 4, 8, 16, 32, 64 M15 bars;
- ATR/range/realised-volatility at multiple trailing horizons;
- close position within trailing 16/32/64/96-bar range;
- distance and slope relative to causal EMAs;
- rolling z-scores and RSI-like bounded momentum;
- body/range/wick ratios as continuous measurements, not named candle setups;
- previous-day high/low distance;
- Asian-session range position;
- UTC hour/day-of-week cyclic features;
- companion-pair returns and EURUSD/GBPUSD relative-return features;
- trailing volatility percentile/regime.

No macro series is used in this first price-only discovery because revised macro data can create point-in-time leakage. Macro/carry can be a later separately preregistered study.

## Exit search

Every viable entry family is evaluated across the same risk/reward grid rather than fixing 2.5R in advance.

Stop distance grid (ATR units):
`0.50, 0.75, 1.00, 1.25, 1.50`

Target reward/risk grid:
`0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00`

Maximum holding horizon: 32 M15 bars (8 hours) for the primary intraday study. Unresolved trades close at the horizon close and are scored by realised R. Same-bar stop+target touches are pessimistically counted as stop-first in M15 discovery; M5 finalist refinement is used to reduce ambiguity.

## Objective

The optimizer does **not** maximize win rate alone.

A candidate must satisfy all of these before it can be considered:

- at least 300 trades before the final holdout;
- net expectancy > 0 after baseline costs;
- profit factor > 1.10 before holdout;
- win rate > 50% before holdout OR, if below 50%, expectancy >= +0.10R/trade;
- positive net expectancy on **both EURUSD and GBPUSD** before holdout;
- positive net expectancy in at least 4 of 6 validation/confirmation years (2017-2022);
- no single year contributes > 45% of cumulative pre-holdout net R;
- stress-cost expectancy is not catastrophically negative (must be > -0.03R/trade).

Ranking among survivors uses a frozen robustness score emphasizing median yearly expectancy, lower-confidence-bound expectancy, profit factor, and win rate, with penalties for parameter fragility and low trade count.

## Multiple testing / overfit controls

- all candidate configurations are counted;
- bootstrap confidence intervals use year/session blocks rather than iid trades;
- finalists receive a probability-of-backtest-overfitting style parameter-neighbourhood check: adjacent stop/RR/lookback settings should not collapse;
- a White/Hansen-style reality-check approximation is reported using bootstrap maxima across candidate returns where computationally feasible;
- ML is evaluated only with expanding-window out-of-sample predictions;
- final 2023-2025 data cannot be used for threshold or parameter selection;
- no post-hoc holdout tuning is allowed. If holdout fails, V3.6 reports failure rather than repairing the rule on holdout.

## Promotion gate on untouched 2023-2025

A candidate may become a live **shadow** engine only if all are true on the untouched holdout:

- >= 120 trades total and >= 40 on each pair;
- net expectancy >= +0.05R/trade after baseline costs;
- profit factor >= 1.10;
- win rate >= 52%;
- positive expectancy on both pairs;
- positive expectancy in at least 2 of 3 holdout years;
- stress-cost expectancy >= 0;
- bootstrap 95% lower bound on mean net R is > -0.02R;
- no evidence that one isolated month/session supplies the majority of gains.

A stronger `PROMOTE` label requires holdout expectancy >= +0.10R, PF >= 1.20 and bootstrap 95% lower bound > 0.

Anything weaker is `REJECT` or `WATCHLIST`; it must not alter the existing V2 paper engine.

## Live boundary

If a candidate survives, it is deployed as a new independent shadow engine with its own snapshots/signals/paper ledger and explicit research label. It must not overwrite the existing baseline engine or its $500 paper account until prospective evidence is accumulated.

If no candidate survives, **nothing will be invented or forced live**. The valid research result is that the tested price-only strategy space did not produce a robust edge.
