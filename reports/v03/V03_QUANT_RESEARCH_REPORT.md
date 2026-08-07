# V2 Quant v0.3 Research Report

## Executive decision

V2 Quant v0.3 passes **one** research gate and fails the others.

| Component | Decision | Why |
|---|---|---|
| Strict price/setup meta-model | **ACCEPT as research baseline** | Completed-bar-only OOS ranking remains useful across 2023-2025 |
| Economic-event model | **REJECT as incremental filter** | Standalone OOS ranking is weak and a fixed 80/20 blend makes the price model worse |
| XAUUSD macro/geopolitical model | **REJECT as incremental filter** | 2025 is promising, but 2023/2024 are unstable and the fixed blend does not improve overall ranking/calibration |
| Independent M1 execution validation | **FAIL live gate** | Only ~55% outcome agreement with independent one-minute XAUUSD data |
| Dukascopy bid/ask tick audit | **FAIL live gate** | ~54% outcome agreement in the targeted sample and spread is large relative to many proxy stops |

The correct interpretation is not that v0.3 failed. The research process succeeded by separating a relatively stable **setup-ranking signal** from context layers and execution assumptions that do not yet survive falsification.

No live-money execution and no live buy/sell alert should be enabled from these results.

---

## 1. Why v0.3 was necessary

The earlier public-data experiment showed useful out-of-sample ranking, but a deeper timestamp audit found two places where the inputs were too optimistic for a production-grade quant test.

### Leakage correction 1: entry candle information

Some earlier price features could use the final close or volume of the M15 candle containing the entry. At the instant an entry becomes available, that candle has not necessarily finished.

v0.3 therefore computes market state only from **completed M15 bars** available at or before the entry timestamp.

### Leakage correction 2: economic-release surprise

The earlier calendar join could associate an event's eventual `actual - forecast` surprise with a trade occurring before that announcement.

v0.3 separates:

- information about the **next scheduled event**: currency, category, impact and time-to-event;
- information about the **most recent released event**: category, currency, impact and surprise;
- surprise standardization using only previous releases of the same event/currency.

Future actual values are never visible to a pre-release trade.

### Additional point-in-time controls

- Daily macro series are lagged by one calendar day.
- Monthly geopolitical-risk values are exposed only after a conservative post-month-end delay.
- Training trades whose exits overlap the start of the OOS year are purged.
- Model-output joins are one-to-one and occurrence-safe because the human-readable `setup_id` is not globally unique.
- Failed context models are not inverted, reweighted or retuned after observing OOS results.

These controls intentionally make it harder for v0.3 to match the headline performance of the earlier experiment.

---

## 2. Data and model architecture

### Price data

The research continues to use the independent public M15/M5 benchmark for:

- EURUSD
- GBPUSD
- XAUUSD
- NAS100

The frozen proxy event engine remains:

`liquidity sweep -> BOS -> fresh POI -> 50% POI entry -> stop -> fixed 2.5R target`

This is a reproducible reconstruction of the recovered V2 concept, **not** the unavailable original MT5 source code.

### Strict price/setup model

The v0.3 price model is an ensemble of five regularized LightGBM models using only entry-time-available fields including:

- setup risk relative to ATR;
- sweep depth and wick geometry;
- BOS displacement;
- POI width;
- sweep-to-BOS and BOS-to-entry timing;
- estimated execution cost relative to risk;
- completed-bar returns over 1, 4, 16 and 96 M15 bars;
- realized volatility over multiple windows;
- ATR regime;
- recent range position;
- completed-candle body and wick geometry;
- EMA deviation/slope;
- distance from recent highs/lows;
- completed-bar volume/activity z-score;
- session/time information.

### Economic-event model

The separate event model uses only causal event information:

- minutes since the previous relevant event;
- minutes to the next scheduled event;
- previous and next event category/currency;
- expected impact level;
- standardized surprise of the previous release only;
- pre-event/post-event windows;
- number of known recent events and scheduled upcoming events.

### XAUUSD macro/geopolitical model

Gold receives its own model based on lagged:

- 10Y real yield;
- 10Y nominal yield;
- 10Y breakeven inflation;
- broad USD index;
- VIX;
- WTI oil;
- federal funds rate;
- high-yield spread where usable;
- Caldara-Iacoviello geopolitical risk, threat and act indexes;
- selected interactions such as real-yield × USD and GPR × USD.

The macro model is deliberately simpler than the price model: regularized logistic regression. With a small gold trade sample, a more flexible model would increase overfit risk before we have evidence that the macro layer adds stable information.

---

## 3. Strict price model: primary v0.3 result

The expanding-year test uses 2023, 2024 and 2025 as OOS years. Every test year is predicted using only earlier history.

### Pooled OOS result

| Metric | Result |
|---|---:|
| OOS trades | 566 |
| AUC | **0.7128** |
| Brier score | 0.2151 |
| All-trade expectancy | +0.4298R |
| Pooled top 50% score cohort | 283 trades, +0.8085R |
| Pooled top 30% score cohort | 170 trades, +1.2104R |

The AUC is lower than the earlier less-strict experiment. That reduction is expected after removing information that was not definitely available at entry.

The important result is that ranking power did **not disappear**.

### Year-by-year walk-forward

| Test year | AUC | All expectancy | Training-q50 cohort | Training-q70 cohort |
|---|---:|---:|---:|---:|
| 2023 | 0.6959 | +0.7133R | +1.0010R | **+1.3535R** |
| 2024 | 0.6825 | **+0.0494R** | +0.4229R | **+0.8181R** |
| 2025 | 0.7615 | +0.4999R | +0.9975R | **+1.3042R** |

2024 remains the most informative year. The raw proxy was essentially flat, yet the price model still produced useful ordering of setup quality. That is stronger evidence for a meta-label/ranking use case than simply observing high average returns in easy years.

### Serial-dependence-aware uncertainty

A moving-block bootstrap was used as a basic check against treating trades as iid observations.

Approximate 95% intervals:

| Cohort | Mean expectancy | Moving-block 95% interval |
|---|---:|---:|
| All OOS | +0.430R | about **+0.29R to +0.56R** |
| Training-q50 | +0.836R | about **+0.65R to +1.00R** |
| Training-q70 | +1.193R | about **+0.98R to +1.37R** |

This suggests the historical mean is not being created by only a few isolated trades. It is **not** sufficient evidence for deployment because multiple model variants have now been tried. v0.4 should add explicit multiple-testing controls such as Deflated Sharpe Ratio and CSCV/Probability of Backtest Overfitting, with a frozen experiment registry.

---

## 4. Economic-event model: rejected

The separate causal event model did not generalize.

| Test year | Event-model AUC | Brier |
|---|---:|---:|
| 2023 | **0.4475** | 0.2614 |
| 2024 | **0.3432** | 0.3358 |

The archive is incomplete for a clean full-year 2025 event test, so v0.3 does not manufacture a 2025 result.

A predeclared fixed blend was then tested:

`combined = 0.80 × price model + 0.20 × event model`

| Metric | Price only | Price + event |
|---|---:|---:|
| AUC | **0.7128** | 0.7069 |
| Brier | **0.2151** | 0.2172 |
| q50 expectancy | **+0.8085R** | +0.7789R |
| q70 expectancy | **+1.2104R** | +1.1871R |

Decision: **REJECT_AS_INCREMENTAL_FILTER**.

The model is not inverted because an anti-correlated OOS result discovered after testing is not a legitimate new signal. Inverting it now would be post-hoc optimization.

Economic news can still matter to the market. This result says the **current representation is not a stable predictive layer for this V2 setup sample**.

---

## 5. XAUUSD macro/geopolitical model: rejected for now

### Gold price-only baseline

| Metric | Result |
|---|---:|
| OOS XAUUSD trades | 165 |
| AUC | **0.7118** |
| Brier | 0.2140 |
| All expectancy | +0.4000R |
| q50 expectancy | +0.7169R |
| q70 expectancy | +1.0949R |

### Standalone macro model

| Test year | AUC | Brier |
|---|---:|---:|
| 2023 | 0.5888 | 0.3182 |
| 2024 | **0.4828** | 0.3031 |
| 2025 | **0.6989** | 0.2281 |

The 2025 result is interesting, but 2024 is close to random and overall stability is insufficient.

The predeclared blend was:

`gold_blend = 0.70 × price + 0.30 × macro`

| Metric | Gold price only | Gold price + macro |
|---|---:|---:|
| AUC | **0.7118** | 0.7075 |
| Brier | **0.2140** | 0.2153 |
| q50 expectancy | +0.7169R | **+0.7948R** |
| q70 expectancy | +1.0949R | **+1.1747R** |

The macro blend improves the top-tail historical expectancy but worsens overall ranking and calibration. Under the predefined incremental-information rule, this is not enough.

Decision: **REJECT_AS_INCREMENTAL_FILTER**.

A data-quality note: the high-yield spread feature was unavailable/all-missing for the model sample in this run and was skipped by the imputer. That field should be repaired or removed before another gold-macro experiment.

The 2025 improvement is worth treating as a hypothesis for a future **regime-specific** gold model, not evidence to deploy the current macro layer.

---

## 6. Independent XAUUSD one-minute audit: execution gate fails

A separate XAUUSD one-minute dataset spanning November 2011 to January 2024 was used to replay the overlapping gold trades.

Because independent spot/CFD feeds may differ by a persistent local price basis, each source entry/stop/target was translated using the difference between the last completed source M15 close and the last completed independent M15 close available before entry. No future price was used to calculate the adjustment.

### Results

| Metric | Result |
|---|---:|
| Resolved XAUUSD proxy trades | 284 |
| Trades overlapping independent M1 history | **169** |
| Trades audited | **169** |
| Adjusted entry fill rate | **92.9%** |
| Fill rate after a 1-minute start delay | **92.9%** |
| Remaining same-minute ambiguities | 3 |
| Comparable win/loss outcomes | 152 |
| M15/M5 source vs independent M1 outcome agreement | **55.3%** |
| Median absolute quote-basis difference | about 5.75 bps |

The one-minute audit substantially lowers confidence in the **absolute trade outcome labels** from the M15/M5 proxy.

A ~55% win/loss agreement across independent feeds is too low to claim that historical expectancy is execution-robust.

This does not prove that the structural idea is false. Possible causes include:

- different broker/feed highs and lows;
- timestamp/session conventions;
- CFD versus spot quote construction;
- very tight stops making small feed differences decisive;
- M15/M5 path assumptions that are still too coarse.

But until this disagreement is resolved, it is a live-trading blocker.

---

## 7. Dukascopy bid/ask tick audit: stronger execution warning

A stratified targeted sample was replayed with Dukascopy bid/ask ticks rather than midpoint candles.

The sample intentionally included wins, losses and high-cost/risk setups rather than only attractive historical trades.

### Results

| Metric | Result |
|---|---:|
| Requested trade windows | 16 |
| Successful tick windows | 16 |
| Fetch errors | 0 |
| Causal basis available | 93.75% |
| Raw tick fill rate | 87.5% |
| Basis-adjusted tick fill rate | 87.5% |
| Comparable win/loss outcomes | 13 |
| Raw M15/tick outcome agreement | **53.8%** |
| Basis-adjusted agreement | **53.8%** |
| Median observed spread / strategy risk | **0.55R** |
| 90th-percentile spread / risk | **2.27R** |

Basis alignment did **not** improve outcome agreement. Therefore the disagreement cannot be explained simply by one feed quoting every price a constant amount higher or lower.

The spread/risk result is particularly important. In this deliberately stress-oriented sample, the median observed bid/ask spread consumes about half of the planned 1R stop distance, while the 90th percentile exceeds twice the planned stop distance.

That is consistent with the earlier cost-stress result where the unfiltered proxy became essentially flat near 2× assumed friction.

The sample is too small and cross-broker to estimate the true strategy expectancy. It is more than sufficient to show that **tight-stop execution is a first-order model variable, not a small afterthought**.

---

## 8. What v0.3 changes

### Confidence that V2-like setups contain rankable information

**Moderate.**

The strict completed-bar-only model retains an OOS AUC around 0.71 and behaves usefully even in the weak 2024 regime.

### Confidence in the current historical R expectancy as a live number

**Low.**

The independent M1 and tick audits show that the exact sequence of entry/TP/SL is not sufficiently reproducible across feeds. The +0.43R all-trade and +1.21R top-score historical figures should therefore be understood as **proxy research statistics**, not expected live returns.

### Confidence that raw calendar/news features improve the strategy

**Low.**

The causal event model is rejected.

### Confidence that the current XAU macro/geopolitical model improves gold

**Low to moderate as a research hypothesis, low as a deployable filter.**

2025 is encouraging, but aggregate incremental evidence is not stable enough.

---

## 9. v0.3 deployment decision

The proper system state is:

```text
V2 structural setup engine       -> RESEARCH
Strict price meta-model          -> ACCEPTED RESEARCH BASELINE
Economic-event overlay           -> REJECTED
XAU macro/geopolitical overlay   -> REJECTED
Independent M1 execution gate    -> FAILED
Bid/ask tick execution gate      -> FAILED
Live-money execution             -> DISABLED
Live buy/sell signals            -> DISABLED
```

A web dashboard may display research state and historical model scores, but it should not present a current instrument recommendation as if the execution model had passed.

---

## 10. Recommended next research stage: execution-first v0.4

The next version should not add a larger neural network. It should repair the weakest link revealed by v0.3.

### P0 — rebuild labels using execution-aware data

- derive entry, stop and target outcomes from bid/ask or conservative M1 rules;
- distinguish `setup detected` from `order genuinely fillable`;
- measure spread at the actual entry timestamp;
- measure spread/R and reject trades whose risk distance is too tight for available liquidity;
- test market/limit-order assumptions separately;
- preserve no-fill as an outcome rather than pretending every touched midpoint fills.

### P0 — establish a minimum executable geometry

Research surfaces should include:

- risk distance / current spread;
- risk distance / p90 recent spread;
- ATR / spread;
- session liquidity;
- stop width in native ticks/pips/points;
- probability of fill within N minutes;
- slippage stress by instrument and session.

The key question becomes:

> Does the V2 ranking signal remain after excluding setups whose planned geometry is economically smaller than the market's transaction friction?

### P1 — retrain the meta-model on execution-validated labels

Only after the label engine changes should the price model be retrained. Otherwise a more powerful model simply learns to rank noisy historical labels more accurately.

### P1 — multiple-testing controls

Because v0.1-v0.3 have tested multiple model/feature variants, maintain an experiment registry and add:

- Deflated Sharpe Ratio;
- CSCV / Probability of Backtest Overfitting;
- parameter perturbation surfaces;
- block-bootstrap uncertainty;
- frozen model-selection rules.

### P2 — context-model redesign

Economic news and gold macro should return only after the execution baseline is frozen. Their next version should be tested as **incremental residual models**, not as another broad feature dump.

---

## Final research verdict

V2 Quant v0.3 does **not** justify live trading.

It does justify continuing the project.

The strongest result is no longer the headline backtest return. The strongest result is that a timestamp-clean price model still ranks V2-like setups out of sample while a hostile execution audit exposes exactly where the current system is fragile.

That is the kind of result a serious quant process should produce before money is put at risk.
