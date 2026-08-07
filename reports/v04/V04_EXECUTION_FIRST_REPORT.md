# V2 Quant v0.4 — Execution First

## Executive decision

**Live gate: FAIL.**

V2 Quant v0.4 tested the frozen v0.3 price-ranking model against independently reconstructed executable labels rather than its original M15/M5 candle labels. The test was deliberately score-stratified and pre-registered before the tick results were known.

The result is materially negative:

- 64 score-stratified trades were selected across EURUSD, GBPUSD, NAS100 and XAUUSD.
- All 64 Dukascopy tick windows downloaded successfully.
- 61 trades produced clear executable win/loss labels.
- 31 met the pre-registered trusted-execution criteria.
- Source M15/M5 vs executable-tick outcome agreement was only **59.0%**.
- The frozen v0.3 price score achieved only **0.389 AUC** against executable tick labels.
- The 95% bootstrap interval for that AUC was approximately **0.191–0.606**.
- The same 61 trades had **+0.381R** expectancy under the source M15/M5 labels but **-0.612R** under the executable tick reconstruction.
- Median fill spread was **0.153R**, which passed the pre-registered 0.20R median-spread gate.
- Therefore spread alone does not explain the failure.

No score inversion, threshold change, symbol exclusion or model retraining was performed after seeing these results.

---

## 1. Pre-registered test design

The v0.4 question was:

> Does the already-frozen v0.3 price-ranking signal still discriminate good from bad setups when trade outcomes are reconstructed from executable bid/ask ticks rather than M15/M5 OHLC labels?

The tick sample was not selected from historical winners or losers. For each of four symbols, the full v0.3 out-of-sample score distribution was split into eight rank bins and two trades were selected from each bin.

This produced:

| Symbol | Trades | Score bins | Per bin |
|---|---:|---:|---:|
| EURUSD | 16 | 8 | 2 |
| GBPUSD | 16 | 8 | 2 |
| NAS100 | 16 | 8 | 2 |
| XAUUSD | 16 | 8 | 2 |
| **Total** | **64** | | |

The live tick gate was fixed before the run:

1. at least 40 clear executable labels;
2. at least 20 trusted labels;
3. source-vs-tick agreement at least 80%;
4. frozen price-model AUC on tick labels at least 0.55;
5. median fill spread no more than 0.20R.

The independent XAUUSD M1 gate separately required at least 40 comparable OOS trades, at least 75% label agreement and AUC at least 0.55.

---

## 2. Executable relabeling

The tick engine uses the correct side of the market:

- long limit entry: **ask** must reach the entry;
- short limit entry: **bid** must reach the entry;
- long stop/target exit: **bid**;
- short stop/target exit: **ask**.

Cross-broker price levels are translated by one constant basis offset estimated strictly before the setup entry using the latest completed source M15 close and contemporaneous Dukascopy midpoint. The offset cannot use future information.

For every replay the engine records:

- fill price and time;
- fill delay;
- bid/ask spread at fill as a fraction of planned risk;
- median and p90 spread during the early execution window;
- stop slippage as R;
- executable R outcome;
- execution-quality tier.

### Tick replay summary

| Metric | Result |
|---|---:|
| Requested trades | 64 |
| Successful tick windows | 64 |
| Clear executable labels | 61 |
| Trusted labels | 31 |
| Fill rate | 96.9% |
| M15/M5 vs tick agreement | **59.0%** |
| Agreement 95% CI | **46.5%–70.5%** |
| Median fill spread | **0.153R** |
| p90 fill spread | **0.655R** |
| Median stop slippage | **0.024R** |
| p90 stop slippage | **0.215R** |

The sample therefore had enough labels and enough low-friction labels, and its median spread passed the predefined friction gate. It still failed the outcome-agreement and model-discrimination gates.

---

## 3. Did the v0.3 model survive executable labels?

No.

The frozen score was evaluated without retraining, sign flipping or threshold changes.

| Metric | Source-candle labels | Executable tick labels |
|---|---:|---:|
| Same clear sample size | 61 | 61 |
| Expectancy | **+0.381R** | **-0.612R** |
| Price-model AUC | historically >0.70 on source OOS labels | **0.389** |

The tick-label AUC bootstrap 95% interval was approximately **0.191–0.606**. This sample is still too small to prove that the true executable-label AUC is below 0.50, but it clearly fails the pre-registered minimum of 0.55 and gives no basis for live deployment.

A result below 0.50 is **not** treated as permission to invert the signal. Inverting after observing the answer would be post-hoc optimization.

---

## 4. Spread-filter falsification

A natural hypothesis was that the disagreement came mainly from wide spreads around tight stops. v0.4 tested fixed spread caps while also requiring stop slippage no greater than 0.10R.

| Fill spread cap | N | Agreement | Tick-label AUC | Executable expectancy | Source expectancy on same trades |
|---:|---:|---:|---:|---:|---:|
| <=0.10R | 18 | 77.8% | 0.338 | **-0.030R** | +0.504R |
| <=0.20R | 31 | 71.0% | 0.280 | **-0.307R** | +0.415R |
| <=0.30R | 40 | 67.5% | 0.371 | **-0.285R** | +0.536R |
| <=0.50R | 42 | 66.7% | 0.357 | **-0.318R** | +0.535R |

The strictest 0.10R friction cohort came close to the agreement target and executable expectancy was nearly flat, but the frozen ranking still failed badly.

This is important: **the problem is not just spread.** Path differences, quote construction, broker/source differences, same-bar sequencing and stop/target placement relative to executable prices matter materially.

---

## 5. Per-symbol diagnostic

These are small diagnostic samples, not population performance estimates.

| Symbol | Clear N | Label agreement | Tick AUC | Median spread | Executable expectancy |
|---|---:|---:|---:|---:|---:|
| EURUSD | 16 | 75.0% | 0.309 | **0.061R** | **+0.201R** |
| GBPUSD | 16 | 56.3% | 0.500 | 0.229R | -0.181R |
| NAS100 | 15 | 60.0% | not estimable* | 0.163R | -1.003R |
| XAUUSD | 14 | 42.9% | not estimable* | 0.232R | -1.616R |

\*AUC is not estimable when the clear tick sample contains only one outcome class.

EURUSD is the only market with positive executable expectancy in this small score-stratified sample. That does **not** validate EURUSD yet, because the model ranking itself was weak and the per-market sample is only 16 trades.

XAUUSD was the weakest cross-broker execution case and should not be used for live conclusions until same-broker data is available.

---

## 6. Independent XAUUSD one-minute check

The independent XAUUSD one-minute dataset provided another path-level falsification.

When restricted to trades that also had frozen v0.3 OOS predictions:

- comparable trades: **44**;
- source M15/M5 vs independent M1 agreement: **52.3%**;
- 95% agreement interval: approximately **37.9%–66.2%**;
- frozen price-model AUC on the M1 labels: **0.378**.

This independently fails the M1 gate and points in the same direction as the tick audit.

---

## 7. Cost-model finding

The original source cost proxy is not useless. Across the clear tick sample, source `cost_as_r` had a Spearman correlation of approximately **0.563** with observed fill spread as R, with p approximately **2.3e-6**.

So the old cost feature does capture real execution-friction variation.

However, getting average friction roughly right is not enough when the underlying win/loss labels change across quote feeds and execution paths.

---

## 8. What v0.4 proves and does not prove

### Supported by this test

- The current M15/M5 source labels are not robust enough to be treated as executable ground truth.
- The frozen v0.3 ranking does not currently survive independent executable relabeling.
- Spread matters, but spread alone does not explain the gap.
- Gold and NAS100 are particularly sensitive in this cross-broker sample.
- The project should not progress to live-money execution or live buy/sell alerts.

### Not established by this test

- It does not prove that the original V2 concept has no edge.
- It does not prove that a true same-broker implementation would lose money.
- It does not estimate live portfolio expectancy from the -0.612R number because the sample was score-stratified rather than population-weighted.
- It does not prove that true executable-label AUC is below 0.50; the confidence interval remains wide.
- Dukascopy is not the same broker/source as the original MT5 V2 data.

The decisive unresolved question is therefore **same-broker label integrity**.

---

## 9. Next build: V2 Quant v0.5 — Same-Broker Reconstruction

v0.5 should not add more machine learning.

Its job is to export and reconstruct the original MT5 broker data so the setup-generation candles and execution labels come from the same market feed.

Priority order:

1. export original-broker M15, M5 and M1 data for all four markets;
2. export ticks with bid/ask whenever broker history permits;
3. store broker symbol metadata: digits, point size, tick size, contract size and session availability;
4. rebuild V2 setup labels from the same broker feed;
5. compare same-broker M15/M5 labels with same-broker M1/tick labels;
6. create explicit label-quality flags for ambiguous bars, missing ticks, no fills and excessive spread/slippage;
7. establish market-specific minimum stop-to-spread requirements;
8. only after label agreement passes a pre-registered gate, retrain a price model using executable labels;
9. begin with EURUSD as the first diagnostic market, then add GBPUSD, gold and the index independently.

Until that test is complete, **live money and live buy/sell signals remain disabled**.
