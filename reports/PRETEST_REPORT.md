# V2 Trading v0.1 Pre-Test Report

## What was tested

The recovered 2,227-trade V2 enriched ledger was used to test whether a small entry-time feature set can rank V2 events out of sample. No random shuffle was used.

The chosen candidate after the first comparison is LightGBM on the base entry-time features. A logistic-regression baseline and models with the large HTF feature block were also run.

## Critical audit finding

`m15_v2_setup_score` equals `net_r` exactly. Any model using that field gets near-perfect results because it sees the realized outcome. It was removed before the valid experiment and is now blacklisted by code/tests.

## Walk-forward results: chosen base LightGBM

| Test year | AUC | Baseline expectancy | q50 coverage | q50 expectancy | q70 coverage | q70 expectancy |
|---|---:|---:|---:|---:|---:|---:|
| 2023 | 0.713 | 0.783R | 58.1% | 1.247R | 38.9% | 1.590R |
| 2024 | 0.623 | 0.525R | 64.9% | 0.664R | 45.9% | 0.859R |
| 2025 | 0.649 | 0.586R | 49.5% | 1.005R | 29.6% | 1.125R |
| 2026 | 0.609 | 0.724R | 36.4% | 1.193R | 17.3% | 1.539R |

Pooled 2023-2026 OOS:

- all V2: 1,128 trades, 48.94% wins, 0.648R expectancy, PF 2.21
- q50 research cohort: 613 trades, 59.05% wins, 0.987R expectancy, PF 3.26
- q70 research cohort: 395 trades, 65.82% wins, 1.211R expectancy, PF 4.27
- pooled OOS AUC: 0.648

A simple IID bootstrap on OOS trade returns gives approximate 95% expectancy intervals:

- all V2: 0.547R to 0.749R
- q50: 0.858R to 1.125R
- q70: 1.050R to 1.370R
- q50-rejected cohort: 0.099R to 0.391R

These intervals do not solve serial dependence or research-selection bias, so they are descriptive rather than final statistical proof.

## Cost stress

The recovered `net_r` already subtracts `spread_as_r`. I stressed total spread-equivalent friction from 1.0x to 2.0x the recovered spread cost.

At 2.0x spread-equivalent cost:

- all V2 expectancy: about 0.591R
- q50 expectancy: about 0.910R
- q70 expectancy: about 1.118R

This stress result is encouraging but it is not a substitute for real slippage/tick replay.

## What the model appears to use

Permutation importance averaged across OOS years suggests the strongest base signals are:

1. risk distance
2. entry hour
3. instrument
4. spread as R
5. POI-to-entry timing

Direction and day-of-week add little in this first model.

This is plausible: session timing, instrument-specific behavior, risk width and transaction friction can change the quality of an intraday setup. It also gives us concrete hypotheses to test directly instead of adding arbitrary indicators.

## HTF result

The large HTF feature block did not consistently beat the smaller base model in the first walk-forward experiment. This repeats the lesson from the earlier HTF Scanner: more context can add noise. HTF remains a candidate explanatory/regime layer, not an automatic permission filter.

## Interpretation

There is a real-looking ranking signal in the recovered trade events after removing the obvious leakage. The result is strong enough to continue research, but not strong enough to declare a production edge.

The next tests with the highest information value are:

1. rebuild the original M15 event engine from raw candles;
2. replay ambiguous outcomes on M1/tick bid-ask data;
3. add point-in-time macro variables;
4. add economic-surprise/event proximity variables;
5. build a historical asset-specific news/geopolitical feature panel;
6. rerun walk-forward and leave-symbol-out tests;
7. freeze the model and run live shadow alerts with no tuning.
