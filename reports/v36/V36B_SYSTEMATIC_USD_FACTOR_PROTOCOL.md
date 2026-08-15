# V3.6B Systematic USD-Factor / Breadth Protocol

Status: **FROZEN BEFORE V3.6 OR V3.6B RESULTS ARE USED TO SELECT PARAMETERS**

This is a second independent price-only study. It is not a modification of any V2/V3 engine and it is not a rescue filter chosen from V3.6 outcomes.

## Research hypothesis

Currency returns share systematic components. Published currency-factor research reports that systematic/factor returns can contain momentum while idiosyncratic currency returns contain little momentum. V3.6B therefore asks a narrow question:

> Does broad, causal agreement across major USD exchange rates improve the probability and net expectancy of EURUSD/GBPUSD intraday trades compared with using each target pair in isolation?

This is tested empirically; the literature is motivation, not evidence that the exact intraday rule works.

## Universe and data

Dukascopy public bid M15 OHLCV, UTC, 2005-01-01 through 2025-12-31 where available:

- EURUSD
- GBPUSD
- AUDUSD
- NZDUSD
- USDJPY
- USDCHF
- USDCAD

EURUSD and GBPUSD are the only traded targets. The other pairs are predictors only.

Return signs are normalized so positive `usd_factor_return` always means USD appreciation:
- negate returns for EURUSD/GBPUSD/AUDUSD/NZDUSD;
- retain returns for USDJPY/USDCHF/USDCAD.

To reduce mechanical target leakage, the breadth/factor signal for a target pair is reported both including and **excluding that target pair**. The primary candidate uses leave-one-target-out factor/breadth.

## Chronological partitions

Same absolute partitions as V3.6:
- discovery 2005-2016
- validation 2017-2020
- confirmation 2021-2022
- untouched holdout 2023-2025

The holdout cannot select the factor lookback, breadth threshold, volatility regime, target relative-strength rule, stop or RR.

## Candidate factor definitions

For each completed M15 bar, using only data timestamped at or before that bar:

- USD factor returns over 4, 8, 16, 32, 64 and 96 bars;
- breadth = fraction of available component currencies whose normalized return agrees with the USD factor sign;
- cross-sectional dispersion of normalized returns;
- factor realised volatility;
- target residual/relative return = target USD-normalized return minus leave-one-out USD factor return;
- factor trend persistence = sign agreement between short and longer factor horizons.

## Frozen rule families

1. **Factor continuation**: trade the target in the direction implied by USD factor momentum when breadth exceeds a threshold.
2. **Factor continuation + persistence**: short and long factor horizons agree.
3. **Factor continuation + target confirmation**: target's own normalized return agrees with the leave-one-out factor.
4. **Factor continuation + residual pullback**: systematic USD factor is strong but target temporarily lags/overshoots opposite the factor, seeking catch-up.
5. **Factor reversal control**: deliberately trade against factor after an extreme move; included as a falsification/control family.
6. **Dispersion regime**: compare low-dispersion (broad common shock) and high-dispersion factor states.
7. **Volatility regime**: factor continuation under low/mid/high trailing volatility percentile.
8. **Session-conditioned factor continuation**: Asia, London, London-NY overlap, New York.

Frozen grid:
- factor lookback: 4, 8, 16, 32, 64, 96 M15 bars
- breadth threshold: 0.57, 0.71, 0.86
- factor normalized magnitude threshold: 0, 0.5, 1.0 trailing-vol units
- persistence long horizon: 32, 64, 96 where longer than short horizon
- residual threshold: 0.5 or 1.0 target ATR-scaled return units
- dispersion regime: bottom/middle/top trailing 20-day tercile
- volatility regime: bottom/middle/top trailing 20-day tercile
- sessions: all, 00-07 UTC, 07-12, 12-16, 16-21

Not every Cartesian combination is generated; each family uses only its logically relevant variables. The final report records the exact number tested.

## Exit and cost grid

Identical to V3.6 so comparisons are fair:
- stop: 0.50, 0.75, 1.00, 1.25, 1.50 ATR
- RR: 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00
- horizon: 32 M15 bars
- same-bar target+stop: stop-first pessimistic
- entry: next M15 open
- EURUSD baseline cost 0.8 pip, stress 1.5
- GBPUSD baseline cost 1.0 pip, stress 2.0
- one position per target/config at a time.

## Gates

Prehold and holdout gates are exactly the V3.6 gates. A factor candidate is not allowed a weaker standard because it came from academic motivation.

## Comparison requirement

If V3.6B survives, the report must compare it with:
- the matching target-only momentum signal using the same lookback/exit geometry;
- factor rule with the target pair removed from the breadth calculation;
- factor reversal control.

The systematic factor must add measurable out-of-sample value rather than merely restate the target pair's own trend.

## Live boundary

Only `WATCHLIST` or `PROMOTE` can be deployed, and only as an independent shadow engine with a separate ledger. No historical holdout result is allowed to overwrite V2/V3 baseline trade rules.
