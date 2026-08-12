# V2 XAU v0.4 POI Walk-Forward Result

**Research only. Gold parameters are not promoted from this report alone.**

Source rows: 193,544 XAUUSD M15 candles from 2020-01-01 00:00:00+00:00 to 2026-08-12 10:45:00+00:00.

## Completed-year midpoint baseline (2022-2025)

- valid-risk setups: 1,084
- fill rate: 82.56%
- resolved fills: 443
- resolved win rate: 36.79%
- opportunity expectancy: +0.1176R
- ambiguous rate among fills: 50.06%

## Descriptive best depth

- depth: 40.00%
- opportunity expectancy: +0.1222R
- fill rate: 82.58%

The pooled difference versus the 50% midpoint is small and is not accepted as evidence of a better entry rule.

## Chronological walk-forward

| Year | Chosen depth | Candidate R | Midpoint R | Delta |
|---:|---:|---:|---:|---:|
| 2022 | 75.00% | +0.0156R | +0.0214R | -0.0058R |
| 2023 | 5.00% | -0.0405R | +0.1185R | -0.1590R |
| 2024 | 10.00% | +0.0152R | +0.0244R | -0.0091R |
| 2025 | 40.00% | +0.0477R | +0.1023R | -0.0545R |
| 2026 YTD | 65.00% | -0.0581R | +0.0233R | -0.0814R |

Bootstrap paired candidate-minus-midpoint across completed-year paired rows: n=814, point=-0.0522R, 95% interval [-0.1149R, +0.0129R].

**Frozen decision: KEEP_MIDPOINT_RESEARCH_ONLY.**

Important caveat: M15 path ambiguity is high, including 50.06% of filled midpoint cases. This strengthens the requirement for finer-path reconstruction and prospective XAU shadow evidence before any paper-entry promotion.

A descriptive best depth is not a production rule. Promotion requires chronological stability, cost stress, finer-path ambiguity checks and prospective XAU shadow evidence.