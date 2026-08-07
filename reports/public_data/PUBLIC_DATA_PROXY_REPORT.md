# Public-Data V2 Proxy Research Report

## Purpose

This experiment asks a harder question than the recovered-ledger study:

> Does the core V2 idea still produce useful signal when it is reconstructed with explicit rules and run on an independent public market dataset?

This is **not** claimed to be the exact historical V2 source code. The original implementation is unavailable. The engine is a reproducible proxy built from the recovered description:

`liquidity sweep -> BOS -> fresh POI -> 50% POI entry -> fixed 2.5R target`

## Data

Market data: public `NatoG93/market-data` Hugging Face files for EURUSD, GBPUSD, XAUUSD and NAS100.

- 15-minute bars generate setups and outcomes.
- Matching 5-minute bars are used when both the stop and target can be touched inside the same 15-minute candle.
- The observed files begin in September 2020 and extend into January 2026.
- The run found no duplicate 15-minute timestamps after normalization.

Macro-event context: `Ehsanrs2/Forex_Factory_Calendar`, covering 2007 through 7 April 2025. Because that archive stops in April 2025, raw calendar features are incomplete for the later 2025 market sample and should not be treated as a finished macro model.

## Explicit proxy rules

The first frozen proxy uses:

- prior swing lookback: 20 M15 bars
- BOS reference lookback: 8 bars
- ATR period: 14
- sweep penetration: at least 0.03 ATR beyond the prior swing, followed by a close back inside
- BOS must occur within 6 bars
- POI: last opposite candle from sweep through BOS
- entry: 50% of the POI zone within 8 bars after BOS
- stop: beyond the sweep extreme plus 0.03 ATR
- acceptable risk width: 0.08 to 1.60 ATR
- target: fixed 2.5R
- maximum holding period: 48 M15 bars

These values are now frozen for this benchmark. Changing them creates a new experiment rather than silently improving this one.

## Intrabar finding

The proxy produced 1,080 candidate trades.

- 1,022 had a usable resolved result.
- 58 remained ambiguous even after the available 5-minute check and were excluded from return/model calculations.
- 242 trades required the 5-minute layer to resolve a stop/target ordering question.

That last number matters. About 22% of all generated setups needed lower-timeframe inspection at least once. A pure M15 backtest can therefore materially mis-state this type of strategy if it guesses the order of intrabar events.

## Independent baseline

Across the 1,022 resolved trades:

| Metric | Result |
|---|---:|
| Win rate | 53.03% |
| Expectancy | 0.466R/trade |
| Profit factor | 1.78 |
| Total R | 476.16R |
| Max drawdown | -13.91R |

### By instrument

| Instrument | Resolved trades | Win rate | Expectancy | Profit factor | Max DD |
|---|---:|---:|---:|---:|---:|
| EURUSD | 235 | 57.02% | 0.561R | 2.00 | -10.77R |
| GBPUSD | 260 | 51.15% | 0.360R | 1.55 | -15.31R |
| NAS100 | 243 | 54.32% | 0.619R | 2.14 | -9.55R |
| XAUUSD | 284 | 50.35% | 0.353R | 1.56 | -10.39R |

The fact that all four markets are positive on an independent dataset is enough to continue the research. It is not proof of a live edge because the rules are a reconstructed proxy and the execution costs are research assumptions.

## Year stability

The proxy did not perform equally every year. The full resolved sample had approximately:

| Year | Trades | Expectancy |
|---|---:|---:|
| 2020 partial | 52 | 0.830R |
| 2021 | 205 | 0.338R |
| 2022 | 195 | 0.598R |
| 2023 | 196 | 0.713R |
| 2024 | 181 | **0.049R** |
| 2025 | 189 | 0.500R |
| 2026 partial | 4 | not meaningful |

2024 is the warning year. The raw strategy was close to flat, which is useful because it prevents us from mistaking an average result for a stable edge.

## Walk-forward meta-model

The primary model is LightGBM. Training always uses earlier years and the next year is kept out of training.

Pooled 2023-2025 out-of-sample results:

| Cohort | Trades | Win rate | Expectancy | Profit factor | Max DD |
|---|---:|---:|---:|---:|---:|
| All proxy trades | 566 | 52.30% | 0.430R | 1.71 | -13.30R |
| Training-median score (q50) | 295 | 67.80% | 0.820R | 2.82 | -10.00R |
| Training-70th-percentile score (q70) | 170 | 80.59% | 1.130R | 4.74 | -4.88R |

Pooled OOS AUC: **0.729**.

### By OOS year

| Test year | All expectancy | q50 expectancy | q70 expectancy | AUC |
|---|---:|---:|---:|---:|
| 2023 | 0.713R | 0.995R | 1.184R | 0.687 |
| 2024 | 0.049R | 0.434R | 0.846R | 0.736 |
| 2025 | 0.500R | 0.972R | 1.334R | 0.759 |

The strongest practical result here is 2024: the unfiltered proxy was nearly flat, while the model still ranked a smaller subset with better outcomes. That is the behavior we want from a meta-labeler. It still needs more markets, parameter perturbation and a future shadow period before being trusted.

## Execution-cost stress

The base research cost model is deliberately approximate. We therefore multiplied the assumed spread+slippage cost rather than presenting one cost estimate as truth.

| Cost multiple | All expectancy | q50 | q70 |
|---|---:|---:|---:|
| 1.0x | 0.430R | 0.820R | 1.130R |
| 1.5x | 0.216R | 0.515R | 0.744R |
| 2.0x | **0.002R** | 0.209R | 0.358R |
| 3.0x | -0.425R | -0.403R | -0.415R |

The edge is cost-sensitive. Around 2x the assumed friction, the unfiltered strategy is effectively gone. The selective model retains some historical edge at 2x, but it also fails by 3x. This makes real bid/ask and slippage data a high-priority validation task.

## Does the economic calendar improve the model?

Not in its first form.

Ablation on the same OOS years:

| Feature set | Pooled AUC | q50 expectancy | q70 expectancy |
|---|---:|---:|---:|
| Price/setup only | **0.740** | **0.905R** | 1.114R |
| Price/setup + raw calendar fields | 0.728 | 0.827R | **1.136R** |

The calendar features reduced pooled AUC and q50 performance. Therefore raw event proximity/surprise fields should not be forced into the main model.

There is still a signal worth studying. Descriptively:

- no high-impact event within 30 minutes: 978 trades, 0.426R expectancy
- high-impact event within 30 minutes: 44 trades, 1.351R expectancy
- no high-impact event within 120 minutes: 892 trades, 0.427R expectancy
- high-impact event within 120 minutes: 130 trades, 0.734R expectancy

This does **not** prove that news causes better V2 trades. The high-impact sample is small, event timing overlaps with liquid sessions, the calendar archive ends in April 2025, and event effects differ by instrument and surprise direction. The correct next design is a separate point-in-time event-state model, not a generic `news=yes/no` input.

## What the price model appears to use

A separate price-only permutation test on the OOS years puts the strongest variables in roughly this order:

1. risk width relative to ATR (`risk_atr`)
2. estimated execution cost relative to risk (`cost_as_r`)
3. position inside the recent 20-bar range
4. volume/tick-activity z-score
5. ATR / volatility
6. direction
7. BOS-to-entry timing

This gives the strategy a more concrete interpretation: setup geometry, cost, local range location, activity and volatility appear to matter more than simply adding more indicators.

## Current decision

The public-data proxy passes the test required to continue research:

- the core idea remains positive on an independent dataset;
- the result spans four instruments rather than one;
- lower-timeframe sequencing materially changes evaluation;
- the meta-model adds useful OOS ranking, especially in the weak 2024 year;
- the result has a clear execution-cost failure point;
- naive macro/event features did not improve the main model and are retained as a separate research problem.

It does **not** pass a live-money gate yet.

## Next build

1. Keep a **price/setup-only meta-model** as the clean baseline.
2. Build a separate **economic-event state model** using event type, standardized surprise, affected currency, pre-event regime and post-release timing.
3. Build a dedicated **XAUUSD context model** for USD, real yields, oil/risk stress and geopolitical events rather than generic sentiment.
4. Add 1-minute/tick validation on representative and ambiguous trades using an independent source.
5. Run parameter perturbation around every proxy rule to check for a stable region rather than a single lucky setting.
6. Only after those pass, freeze a shadow model and record live alerts before outcomes are known.
