# V3.6 Global Holdout Lock

Status: **FROZEN BEFORE READING ANY 2023-2025 RESULT FROM V3.6B OR V3.6C**

## Why this exists

V3.6 now contains several independently preregistered research branches. Opening 2023-2025 separately for every branch would turn the final holdout into another tuning set. Therefore the final holdout is treated as a single-use resource across the entire V3.6 research program.

## Branches included before the lock

The currently registered branches are the complete candidate universe allowed to compete for the final holdout:

1. V3.6 deterministic price/time/cross-pair rule grid — 4,240 configurations.
2. V3.6 fixed LightGBM grid — 48 configurations.
3. V3.6B systematic leave-one-target-out USD-factor/breadth study.
4. V3.6C cost-aware high-win-rate LightGBM follow-up — 144 configurations.

No new historical hypothesis may be added after the global winner is selected or after any 2023-2025 metric is read.

## Results already known before this lock

- V3.6 fixed ML: zero pre-holdout survivors. Some variants achieved high pre-2023 win rates, but all failed the frozen robustness/cost gate.
- V3.6 deterministic rule grid: zero pre-holdout survivors in the equivalent frozen full-grid local evaluation. Cloud replication remains auditable but is not needed to select a candidate.

These branches cannot reach the final holdout.

## Global pre-holdout eligibility

A candidate from V3.6B or V3.6C may be considered for the single final holdout only if, using data through 2022:

- it passes its own preregistered branch gate;
- >=300 trades total;
- both EURUSD and GBPUSD have positive net expectancy;
- >=4 of 6 years 2017-2022 have positive mean net R;
- baseline net expectancy >= +0.04R/trade;
- profit factor >= 1.10;
- **stress-cost expectancy >= 0**;
- and either win rate >=55% or baseline expectancy >= +0.10R/trade.

This global filter is intentionally stricter than the original V3.6B allowance of slightly negative stressed expectancy because the user’s research goal is a repeatable higher-win-rate strategy with real economic margin.

## Global ranking

If multiple candidates are eligible, select one without using 2023-2025, lexicographically by:

1. higher pre-2023 stress-cost mean R;
2. higher pre-2023 baseline mean R;
3. higher pre-2023 profit factor;
4. higher pre-2023 win rate;
5. larger trade count.

No subjective override is permitted.

## Single opening of 2023-2025

Only the one global winner may receive expanding-window predictions/signals for 2023-2025 and a final holdout score.

The holdout gate is:
- >=120 trades total and >=40 per pair;
- win rate >=55%;
- mean net R >= +0.05;
- PF >=1.10;
- both pairs positive;
- >=2 of 3 holdout years positive;
- stress mean R >=0;
- monthly block-bootstrap 95% lower bound > -0.02;
- no single month contributes >50% of holdout gains.

`PROMOTE` requires additionally:
- win rate >=58%;
- mean net R >= +0.10;
- PF >=1.20;
- stress mean R >= +0.03;
- bootstrap 95% lower bound >0.

Otherwise the global candidate is WATCHLIST or REJECT according to the gate. No parameter changes are allowed after the holdout is opened.

## Quarantine of obsolete runs

Some earlier GitHub Actions workflows were written before this global lock and may mechanically compute a branch-specific 2023-2025 result after selecting a pre-holdout candidate. Those obsolete artifacts/logs are **quarantined and must not be read or used for research decisions**. Only the global-holdout workflow created under this lock is authoritative.

## Deployment

Historical `PROMOTE` still means shadow deployment first. It does not overwrite the existing V2 $500 paper account. Prospective live evidence is collected in a separate ledger before any future production-rule replacement decision.
