# V2 v2.6 — FX Entry Depth and Readiness Research

**Status: research only. No automatic rule promotion.**

Active scope is EURUSD + GBPUSD. Gold is excluded from the product/runtime. All results below use public completed-candle research paths rather than broker bid/ask execution.

## Decisions

1. **Keep the canonical entry at the 50% POI midpoint.** A first edge touch is not an entry.
2. **Reject the new conditional-depth challenger for live promotion.** Context-specific depth did not outperform midpoint chronologically.
3. **Reject a geometry-only trade-quality probability model.** Existing pre-entry candle geometry did not beat a simple prior-history base-rate forecast.
4. Use model/research output for **attention and next-event guidance**, not an exact trade ETA or hidden win probability.
5. Prioritise genuinely new information for future accuracy work: finer path/execution data and, where obtainable, FX order-flow/liquidity/depth features.

## Why a POI edge touch is not the trade

The exact-live-geometry waiting study separated clean/direct midpoint interaction from shallow POI mitigation:

| Interaction | Resolved | Mean proxy R | Win rate |
|---|---:|---:|---:|
| Midpoint reached directly / same interaction | 499 | +0.992R | 68.9% |
| Shallow POI touch, midpoint reached later | 807 | +0.041R | 39.5% |

A shallow touch is therefore a **quality/context flag**, not a canonical entry. It is retained as `partially_mitigated` rather than silently discarded.

## Static depth research

V1.9 tested entry depth from the proximal POI edge through the distal edge. Different depths appeared optimal under different descriptive slices and years. The walk-forward selected-depth rule failed to beat the 50% midpoint after the risk gate. This non-stationarity is why the live midpoint was retained.

## V2.6 conditional-depth challenger

The new challenger asks a harder question: can V2 choose a different POI depth *using only information already known at BOS*?

Candidate depth choices: 20%, 30%, 40%, 50%, 60%, 65%, 75%, 85%.

Selection features:
- symbol;
- session;
- POI width / ATR;
- BOS displacement / ATR;
- sweep-to-BOS speed.

Each test year uses only prior years to choose depth. Sparse or weak contexts fall back to 50%. The replay used the frozen V19 M5-refined artifact.

### Chronological results versus 50% midpoint

| Test year | Setups | Mean delta vs midpoint | Pessimistic ambiguity delta | Challenger fill | Midpoint fill |
|---:|---:|---:|---:|---:|---:|
| 2022 | 997 | +0.00201R | -0.00401R | 77.03% | 77.73% |
| 2023 | 1,112 | -0.01709R | -0.03058R | 75.09% | 76.53% |
| 2024 | 1,087 | +0.00736R | +0.00184R | 76.26% | 76.54% |
| 2025 | 1,049 | -0.01954R | -0.03289R | 75.60% | 77.12% |

Pooled neutral delta: **-0.00695R/setup**.

Bootstrap 95% interval: approximately **[-0.01908R, +0.00530R]**.

Pooled pessimistic-ambiguity delta: **-0.01661R/setup** with a bootstrap interval approximately **[-0.03016R, -0.00400R]**.

Only 2 of 4 test years met the preregistered non-inferiority tolerance. The robust promotion gate therefore fails.

**Decision: KEEP_50_MIDPOINT_BASELINE.**

The challenger selected midpoint for about 73.8% of OOS setups anyway; alternative selections were mostly 60%, with smaller 65%, 75% and 85% allocations. The alternatives did not add stable value.

## Can current geometry predict which midpoint trade will win?

A regularised logistic baseline was tested chronologically on clean resolved midpoint fills. Features known before entry were:

- symbol;
- direction;
- session;
- POI width / ATR;
- BOS displacement / ATR;
- sweep-to-BOS bars;
- risk / ATR.

| Test year | n | AUC | Model Brier | Prior-history base Brier |
|---:|---:|---:|---:|---:|
| 2022 | 257 | 0.523 | 0.22788 | 0.22228 |
| 2023 | 294 | 0.525 | 0.22777 | 0.22245 |
| 2024 | 278 | 0.539 | 0.20627 | 0.20580 |
| 2025 | 289 | 0.515 | 0.22878 | 0.22778 |

Pooled AUC: **0.5230**.

Pooled Brier: **0.22271** versus **0.21965** for the simple prior-history base-rate forecast.

**Decision: REJECT_GEOMETRY_ONLY_QUALITY_MODEL.**

This is a useful negative result. More model complexity on the same candle geometry is not justified by these data. A materially better quality model needs new information rather than another learner over the same variables.

## What V2 should research next

FX market-microstructure research supports investigating order flow and liquidity/depth rather than treating OHLC geometry as a complete state description. V2 should treat these as challenger features only, because its current public-price feeds do not provide broker-specific executable order-book truth.

Priority order:
1. M1/tick path data to reduce entry/SL/TP ordering ambiguity.
2. Executable or defensible spread/liquidity proxies by pair and session.
3. FX order-flow / depth / cancellation / imbalance features where a trustworthy source is available.
4. Macro-release state and liquidity regime interactions, evaluated only with information available at decision time.
5. Prospective calibration before any new feature affects the live paper rule.

## Product implication

The product may say **LOW / WATCH / HIGH ATTENTION / ENTRY CHECK / TRACK TRADE** based on observable structural maturity and POI distance. Historical POI revisit frequencies may be shown as lifecycle context. V2 must not translate those base rates into statements such as “a trade will enter in two hours” or publish a current win probability until a genuinely prospective model passes the existing promotion gates.
