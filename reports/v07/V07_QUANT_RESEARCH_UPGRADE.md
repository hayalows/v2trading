# V2 Quant v0.7 — Quant Research Lab Upgrade

## Objective

Upgrade the live EURUSD/GBPUSD research lab using practices found in mature open-source quantitative research and trading systems, without turning the app into an unvalidated signal engine.

## External systems and methods reviewed

### Microsoft Qlib
Repository: https://github.com/microsoft/qlib

Relevant lesson: treat quantitative research as a full data → feature → model → evaluation → production pipeline, and explicitly account for changing market dynamics rather than assuming stationarity.

### NautilusTrader
Repository: https://github.com/nautechsystems/nautilus_trader

Relevant lesson: research/live parity matters. The same event-time semantics used in research should be preserved in production. For V2 this means formation geometry should use completed bars exactly as the causal replay did.

### vectorbt
Repository: https://github.com/polakowo/vectorbt

Relevant lesson: fast vectorized screening is useful for broad parameter/feature experiments, but screening speed is not a substitute for execution-safe validation. It remains a research acceleration candidate rather than a live dependency.

### River
Repository: https://github.com/online-ml/river

Relevant lesson: streaming data changes. Progressive validation, drift detection and online statistics are more appropriate for a live research stream than training a static model once and assuming the distribution stays fixed.

### ruptures
Repository: https://github.com/deepcharles/ruptures

Relevant lesson: structural breaks should be measured rather than hidden inside one static trend label. v0.7 adds a lightweight causal shift diagnostic now; full change-point models are deferred until the prospective stream is materially larger.

### purgedcv / López de Prado-style validation
Repository: https://github.com/eslazarev/purged-cross-validation

Relevant lesson: overlapping financial labels require purge/embargo logic; model comparison needs multiple-testing controls such as Deflated Sharpe Ratio and Probability of Backtest Overfitting. These remain mandatory gates for any future predictive model.

### skfolio
Documentation: https://skfolio.org/

Relevant lesson: risk models and estimators need out-of-sample stress testing and uncertainty-aware validation. Portfolio optimization is not currently relevant to the two-pair formation detector, so it was not added merely for complexity.

## Implemented in v0.7

### 1. Research/live event-time parity

The formation engine now uses the **last completed M15 close** as its structure price. The separately refreshed public reference price is display-only.

This fixes a subtle mismatch in the previous live implementation, where a fresher current/reference value could affect POI proximity while the causal v0.6 historical replay only had completed candles.

### 2. Directional efficiency

Each timeframe now includes a Kaufman-style efficiency ratio:

`ER = |close_t - close_(t-n)| / sum(|close_i - close_(i-1)|)`

ER approaches 1 when price travels directionally and approaches 0 when the same net move is produced through a highly noisy path.

It supplements the existing EMA/ATR trend score rather than replacing it.

### 3. Rolling volatility percentile

ATR is normalized by price and ranked against the trailing history. The UI therefore distinguishes whether current volatility is low, ordinary or unusually high for that timeframe.

This is more informative than comparing one absolute ATR threshold across currencies and price regimes.

### 4. Regime engine v2

The previous regime label relied mainly on EMA separation and an ATR ratio.

v0.7 combines:

- H4 directional efficiency
- M15 normalized-volatility percentile
- short-term versus baseline true-range expansion
- directional trend state

Labels are descriptive:

- directional trend
- range / mean-reverting
- transition
- volatility expansion
- volatility compression

They are not latent-state probabilities.

### 5. Regime-shift / change-pressure diagnostic

A lightweight causal diagnostic compares recent return volatility with a longer baseline and measures the size of the recent multi-bar move relative to expected volatility.

Output:

- stable
- elevated
- high

This is intentionally simpler than an HMM or offline PELT model. The live prospective stream is currently too small to fit a credible latent-regime model without overfitting.

### 6. Higher-timeframe alignment

D1/H4/H1/M15 directions receive weights 3/3/2/1. The lab reports:

- dominant direction
- absolute alignment percentage
- whether the current V2 formation is supported, mixed or conflicting with that context

This is descriptive confluence, **not P(win)**.

### 7. Prospective sample analytics

The UI now reports the timestamped state stream itself:

- number of live observations
- state transitions
- Stage-5 arrivals
- Stage-6 arrivals
- recent state path
- explicit sample-maturity warning

The app refuses to turn the first few hours/days of observations into a win rate.

### 8. Data-quality gate

For recent M15 history the engine checks:

- expected last completed M15 start time
- lag in completed bars
- timestamp gaps
- duplicate timestamps
- reference-price fetch status
- exact structure source
- explicit absence of broker execution truth

The website now calls the system **Near-live research** rather than implying tick-level execution data.

## Independent historical context audit

The v0.7 context diagnostics were then run independently over public EURUSD/GBPUSD M15 history from 2023 onward. This was a descriptive audit, not a parameter-optimization exercise. The thresholds were not changed after observing the result.

The mathematical sanity gate passed for both pairs:

- efficiency ratio remained inside [0, 1]
- volatility percentile remained inside [0, 100]
- shift score remained inside [0, 100]
- stable, elevated and high shift states all occurred in meaningful sample sizes

### EURUSD

77,389 eligible M15 observations:

| Shift state | N | Share | Median next 1h absolute move | Median next 4h absolute move |
|---|---:|---:|---:|---:|
| Stable | 67,376 | 87.1% | 3.54 bps | 7.61 bps |
| Elevated | 7,144 | 9.2% | 5.75 bps | 11.21 bps |
| High | 2,869 | 3.7% | 7.36 bps | 13.11 bps |

### GBPUSD

77,284 eligible M15 observations:

| Shift state | N | Share | Median next 1h absolute move | Median next 4h absolute move |
|---|---:|---:|---:|---:|
| Stable | 67,341 | 87.1% | 3.87 bps | 8.22 bps |
| Elevated | 7,033 | 9.1% | 6.55 bps | 12.67 bps |
| High | 2,910 | 3.8% | 7.84 bps | 14.64 bps |

The ordering was monotonic on both markets: elevated/high shift states were followed by larger **absolute** market movement than stable states at both 1h and 4h horizons.

This supports the diagnostic's intended use as a **change/movement-risk indicator**. It does **not** show direction, profitability or that a V2 setup should be traded when shift risk is high.

## Current live smoke test

After v0.7 deployment the force-refresh completed for both core pairs.

- EURUSD: recent M15 quality had zero detected gaps, zero duplicates and zero completed-bar lag.
- GBPUSD: recent M15 quality had zero detected gaps, zero duplicates and zero completed-bar lag.
- Prospective state history was still an early sample (18 observations per pair at the smoke-test timestamp), therefore the application correctly withheld statistical inference.

The new diagnostics also produced differentiated states rather than one generic trend label: EURUSD's active short watchlist was context-conflicting with the weighted higher-timeframe direction, while GBPUSD was classified as volatility expansion with mixed context.

## What was deliberately NOT added

### HMM / latent regime model

Deferred. A flexible HMM on a tiny prospective dataset would create unstable state labels and false precision. Revisit after a materially larger point-in-time stream exists.

### Online predictive model / River classifier

Deferred. River is relevant once labels can arrive progressively, but current outcome labels are still blocked by the execution problem. Online learning without trustworthy targets would only automate bad labels.

### Reinforcement learning

Rejected for this stage. There is no justified reward process or execution simulator strong enough to support it.

### Portfolio optimization

Not relevant while the product is a two-pair setup research lab rather than a capital-allocation engine.

### New win probability

Explicitly rejected. v0.4 still blocks this because the execution labels did not transfer reliably across feeds.

## Research gates going forward

1. Keep accumulating timestamped prospective observations without changing historical rows.
2. Do not infer live conversion rates from fewer than 100 observations per pair; treat that only as descriptive monitoring.
3. Prefer at least 1,000 prospective state observations per pair before fitting a first live-regime classifier/HMM experiment.
4. Require enough independent Stage-5/Stage-6 episodes before estimating their forward-return distributions.
5. When a predictive model is attempted, use purge/embargo and CPCV/PBO/DSR-style multiple-testing controls rather than one walk-forward result.
6. No live money recommendation until broker/executable labeling is solved.

## Current verdict

v0.7 makes the lab substantially better at **describing the market and explaining why a formation deserves attention**.

It improves trend quality, regime awareness, drift/change diagnostics, data transparency and prospective research discipline without pretending that these additions solve profitability or execution.
