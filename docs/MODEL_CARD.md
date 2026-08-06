# Model Card: V2 Meta-Labeler v0.1

## Purpose
Rank already-valid V2 trade events by estimated probability of reaching target before stop.

## Status
Research only. Not approved for live execution.

## Dataset
Recovered V2 enriched ledger, 2,227 trades, 2020 to July 2026.

## Leakage finding
`m15_v2_setup_score` equals `net_r` exactly in the recovered ledger. It is excluded and blacklisted.

## v0.1 candidate
LightGBM on ten entry-time features:

- symbol
- direction
- risk distance
- spread as R
- bars to entry
- entry hour
- day of week
- sweep-to-BOS minutes
- BOS-to-POI minutes
- POI-to-entry minutes

No realized-return, exit, MFE/MAE or post-exit fields are allowed.

## Validation
Expanding walk-forward OOS tests:

- train through 2022 -> test 2023
- train through 2023 -> test 2024
- train through 2024 -> test 2025
- train through 2025 -> test 2026

The probability thresholds used for q50/q70 selection are computed from training predictions only.

## Current result
Pooled OOS AUC is about 0.648. This is useful ranking information, not strong enough to treat the probability as a literal calibrated forecast without further work.

The q50 and q70 cohorts show higher historical OOS expectancy than the all-V2 baseline. These are provisional because the recovered trade generator itself still requires tick/M1 execution validation and the research process has not yet completed a completely untouched future shadow period.
