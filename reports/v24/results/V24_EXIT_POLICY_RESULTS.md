# V2 v2.4 Exit / Break-even / Partial Profit Results

Research only. Protocol was frozen before this run.

- Reconstructed Stage-6 setups: 5,590
- Policy simulation rows: 31,654

## Completed 2022-2025 policy ranking at 1% risk

| Policy | n | Mean net R | Positive | Full target | $500 final equity | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| be_075 | 717 | 0.1956 | 35.8% | 36.1% | $1882.09 | 32.23% |
| be_100 | 908 | 0.0537 | 32.7% | 32.9% | $737.89 | 53.97% |
| be_125 | 1062 | -0.0261 | 31.6% | 31.8% | $336.32 | 65.77% |
| p25_100_be | 908 | -0.0668 | 44.9% | 32.9% | $253.21 | 68.63% |
| be_150 | 1199 | -0.0512 | 32.3% | 32.4% | $234.85 | 71.35% |
| p33_100_be | 908 | -0.1053 | 46.6% | 32.9% | $179.51 | 72.69% |
| hold_sltp | 1497 | -0.0655 | 36.1% | 36.3% | $152.65 | 85.32% |
| timeout_96 | 1497 | -0.0665 | 36.1% | 35.4% | $150.44 | 84.52% |
| timeout_192 | 1497 | -0.0710 | 36.0% | 35.5% | $140.74 | 84.80% |
| timeout_48 | 1497 | -0.0743 | 36.5% | 34.6% | $134.31 | 85.10% |
| p25_150_be | 1199 | -0.1274 | 40.7% | 32.4% | $96.54 | 83.51% |
| p50_100_be | 908 | -0.1873 | 47.5% | 32.9% | $86.19 | 83.02% |
| p33_150_be | 1199 | -0.1518 | 42.3% | 32.4% | $72.54 | 86.73% |
| p50_150_be | 1199 | -0.2036 | 43.0% | 32.4% | $39.42 | 92.28% |

## Chronological walk-forward selections

- 2022: prior-history selection `be_075` -> 0.4057R mean, $1004.00 from the $500 yearly-reset reporting base.
- 2023: prior-history selection `be_075` -> 0.3733R mean, $939.65 from the $500 yearly-reset reporting base.
- 2024: prior-history selection `be_075` -> -0.0881R mean, $421.66 from the $500 yearly-reset reporting base.
- 2025: prior-history selection `be_075` -> 0.0970R mean, $591.40 from the $500 yearly-reset reporting base.

## Interpretation rule

Descriptive ranking is not enough to replace the baseline. The chronological walk-forward record and prospective shadow sample control any future promotion.

## Risk

1.00% remains the reporting baseline. 1.50% and 2.00% are exposure overlays only; a win streak does not activate them.

## Boundary

The v0.4 executable-label failure remains in force. These results are public-data research, not live-money validation.
