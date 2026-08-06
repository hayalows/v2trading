# V2 Trading v0.1 Robustness Notes

## Why this test exists

The first expanding-year walk-forward result showed useful ranking power, but a model can still look good because it has learned instrument-specific quirks. A harsher test therefore removes one instrument completely from training, trains on the other instruments through 2024, and tests only the unseen instrument in 2025-2026.

## Leave-symbol-out + future-time test

| Held-out instrument | Test trades | AUC | Baseline exp. | q50 coverage | q50 exp. | q70 coverage | q70 exp. |
|---|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | 123 | 0.638 | 0.465R | 90.2% | 0.452R | 77.2% | 0.630R |
| GBPUSD | 132 | 0.693 | 0.762R | 84.8% | 0.862R | 68.9% | 1.108R |
| US30 | 112 | 0.603 | 0.783R | 16.1% | 1.294R | 2.7% | 2.447R |
| XAUUSD | 113 | 0.521 | 0.528R | 36.3% | 0.596R | 9.7% | 0.524R |

The US30 q70 cell contains only three trades and must not be interpreted as a reliable estimate.

## Interpretation

This test weakens any claim that one universal v0.1 model is ready for all four markets.

- GBPUSD transfers reasonably well in this harsh setup.
- EURUSD ranking exists, but the q50 threshold does not improve expectancy; only the more selective q70 cohort improves it.
- US30 has some ranking information, but the training-derived thresholds transfer poorly because its scale/geometry differs from the FX pairs.
- XAUUSD is near random by AUC when the model has never seen gold. This is a strong reason to build an instrument-specific gold context layer rather than treating geopolitical/news information as generic market sentiment.

## Calibration check

Pooled OOS probability deciles are not perfectly calibrated. The bottom/middle deciles are noisy, while the highest score buckets show a much clearer monotonic relationship with realized win rate and expectancy. The top score decile averaged about 0.84 predicted probability, 79.6% realized wins, and 1.63R expectancy in the recovered OOS sample.

That means v0.1 should be treated as a ranking model. Before a displayed number is called a literal probability, it needs point-in-time calibration using a separate calibration window.

## Decision

Keep the current LightGBM as a research baseline, not the final algorithm. The next build should split the problem into:

1. a common V2 setup-quality model;
2. instrument-specific calibration or models where justified;
3. a dedicated XAUUSD macro/geopolitical state model;
4. tick/M1 execution validation before any live shadow scoring is trusted.
