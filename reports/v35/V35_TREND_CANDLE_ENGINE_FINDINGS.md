# V3.5 Trend + Support/Resistance + Candlestick Engine — Findings

Research date: 2026-08-15

Protocol was frozen before the first result in `V35_TREND_CANDLE_ENGINE_PROTOCOL.md`. The successful optimized run was GitHub Actions run `31858185672`, artifact `9239726274`, head SHA `f42a161798a27fa18bb456ae1221d401095305c6`.

## Research boundary

This is a standalone price-action challenger. It generated its own EURUSD/GBPUSD trades from public M5 OHLC over completed years 2022–2025. It did not filter or reuse the baseline V2 sweep/BOS/POI setup universe.

The Kojo and Dapo variants are **public-principles proxies**, not reproductions of private/paid strategies and not claims about either trader's actual performance.

The study combines ideas that are common in public trading education and technical-analysis literature: structural trend (higher highs/higher lows or lower highs/lower lows), support/resistance, breakout/retest, Fibonacci pullback context, and mathematically defined candlestick triggers. Candles were explicitly tested both in context and as a negative control.

## Primary results

| Strategy | N | Decisive WR | Mean R | PF | Bootstrap 95% mean-R CI | Promotion |
|---|---:|---:|---:|---:|---:|---|
| KOJO-PX 3R | 3,032 | 24.88% | **+0.0345R** | 1.049 | [-0.0245, +0.0973] | No |
| BRC 2.5R | 1,428 | 27.65% | -0.0122R | 0.982 | [-0.0904, +0.0671] | No |
| TCR 2.5R | 1,458 | 26.31% | -0.0472R | 0.933 | [-0.1262, +0.0291] | No |
| DFP 3R | 253 | 19.49% | -0.1873R | 0.755 | [-0.3678, +0.0138] | No |
| Candle-only 2.5R control | 22,616 | 27.01% | **-0.0442R** | 0.938 | [-0.0646, -0.0243] | N/A |

Same-M5 stop/target ambiguity is treated pessimistically in the primary mean-R metric. Ambiguity counts were small and do not change the conclusions.

## Frozen promotion gate

A primary family required all of:
1. >=200 pooled trades and >=50 per pair;
2. mean R > +0.10R;
3. profit factor >1.10;
4. positive mean R in at least 3/4 years;
5. both symbols non-negative;
6. at least +0.05R/trade better than the candle-only control;
7. bootstrap 95% lower bound >0 OR all four years positive.

**No primary strategy passed.**

### Kojo public-principles proxy

This was the only primary family with positive pooled expectancy.

- N: 3,032
- mean R: +0.03447R
- PF: 1.0486
- decisive WR: 24.88%
- EURUSD: 1,488 trades, +0.02994R, PF 1.042
- GBPUSD: 1,544 trades, +0.03884R, PF 1.055

Year stability:
- 2022: +0.09033R, PF 1.131
- 2023: -0.00220R, PF 0.997
- 2024: +0.03444R, PF 1.048
- 2025: +0.01884R, PF 1.026

It therefore had non-negative behavior on both pairs and positive mean R in three of four years, and it beat the candle-only control by about +0.0786R/trade. It still failed the frozen gate because the absolute edge is small, PF is below 1.10, mean R is below +0.10R, and the bootstrap confidence interval crosses zero.

**Decision:** keep as a prospective shadow/watchlist family only. Do not make it a baseline V2 rule and do not present it as proven.

### Kojo diagnostic splits — hypotheses only

These were inspected after the primary result and are therefore **post-hoc diagnostics**, not promotable rules:

- Long: 1,540 trades, +0.0682R, PF 1.097
- Short: 1,492 trades, -0.00034R, PF ~1.000
- London–New York overlap: 615 trades, +0.2044R, PF 1.318
- London: 737 trades, -0.1010R, PF 0.867
- Engulfing trigger: 968 trades, +0.0948R, PF 1.136
- Strong-body trigger: 1,200 trades, +0.0449R, PF 1.064
- Rejection trigger: 864 trades, -0.0476R, PF 0.936

These patterns are interesting enough to preregister as future hypotheses, but using them now as filters would be data snooping.

## TCR — trend + support/resistance + candle

Primary TCR 2.5R:
- N 1,458
- decisive WR 26.31%
- mean R -0.04718R
- PF 0.933
- EURUSD -0.04098R
- GBPUSD -0.05232R

By year:
- 2022 +0.03082R
- 2023 +0.02959R
- 2024 -0.04301R
- 2025 -0.20121R

Target sensitivity did not rescue it:
- 2R: -0.04749R, PF 0.928
- 3R: -0.01489R, PF 0.979

Ablations:
- trend + S/R without candle: N 3,081, -0.01259R, PF 0.982
- trend + candle without S/R: N 2,940, -0.04506R, PF 0.936
- trend-only state change: N 258, -0.07712R, PF 0.893

Interpretation: S/R appears more useful than the generic candle gate inside this particular TCR formulation, but the full family is not profitable enough historically to promote.

## Breakout-retest continuation

BRC 2.5R:
- N 1,428
- decisive WR 27.65%
- mean R -0.01223R
- PF 0.982

By year:
- 2022 +0.07761R
- 2023 -0.02712R
- 2024 -0.13890R
- 2025 +0.04779R

Both symbols were slightly negative. This is near flat before considering real broker-specific friction, so it is not a credible live edge under the frozen definition.

## Dapo public-principles Fibonacci pullback proxy

DFP 3R:
- N 253
- decisive WR 19.49%
- mean R -0.18733R
- PF 0.755
- EURUSD -0.20972R
- GBPUSD -0.16367R
- all four years negative

2.5R sensitivity was also -0.18728R.

Ablations:
- no S/R overlap: N 670, -0.07507R, PF 0.898
- no candle requirement: N 511, -0.03588R, PF 0.951

Interpretation: this exact mechanical translation of the public principles fails. That does **not** establish that Dapo Willis's actual/private trading approach fails; it establishes that V2 should not adopt this particular proxy.

## Candlestick-only control

Candle-only 2.5R:
- N 22,616
- mean R **-0.04416R**
- PF 0.938
- bootstrap 95% CI [-0.06456, -0.02432]
- EURUSD -0.04977R
- GBPUSD -0.03849R
- all four years negative

This is strong evidence against treating engulfing/rejection/strong-body shapes as standalone trade signals in V2. Candles remain contextual evidence.

## Main research conclusions

1. **Yes, a separate trend/S&R/candle engine is technically viable.** It can create trades independently of baseline V2.
2. **Candlestick patterns alone should not be traded by V2.** The large negative-control sample is negative with a confidence interval below zero.
3. **Generic trend + S/R + candle confirmation is not automatically an edge.** TCR remained negative.
4. **The exact Dapo public-principles proxy should be rejected.** It was materially negative.
5. **Breakout-retest is close to flat but not good enough.** It should remain research-only.
6. **The Kojo public-principles proxy is the only live watchlist candidate.** Its small positive expectancy is sufficiently interesting for prospective shadow tracking, but nowhere near strong enough for promotion.
7. **Post-hoc Kojo clues—long direction, overlap session and engulfing triggers—must be tested prospectively or in a newly preregistered independent study before use as filters.**

## Live V3.5 architecture

A separate Supabase shadow engine now exists:
- Edge Function: `trend-candle-engine`
- tables: `trend_candle_snapshots`, `trend_candle_signals`
- cadence: 1 minute
- market-analysis input is independent of baseline V2's Stage-3+ snapshot gate
- its signals do not alter the baseline $500 paper account or baseline trade eligibility
- weekend/market-closed state blocks new challenger signals

The live engine continuously stores trend, S/R, candle and candidate state. Only historically defensible families should be surfaced as active watchlist alerts; rejected variants remain available for research diagnostics rather than being marketed as trade signals.
