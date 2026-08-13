# V2 v3.0 — Stop breathing-room protocol

## Question
Does V2 improve if unusually tight structural stops are widened to a minimum pip floor, giving normal FX movement more room while keeping the existing setup logic?

## Frozen before results
- EURUSD and GBPUSD only.
- Entry remains the 50% midpoint of the full opposite-candle POI.
- The existing structural stop (sweep extreme plus 0.03 ATR buffer) is never tightened.
- Candidate stop distance = max(existing structural risk distance, candidate pip floor).
- Candidate floors: 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15 pips.
- Target remains 2.5R and is recomputed from the candidate stop distance.
- Existing 0.08–1.60 ATR risk-distance gate remains in force.
- Entry may occur during the next 192 completed M15 bars (48 hours of trading bars).
- Once entered, the candidate is followed for 48 completed M15 bars (12 hours of trading bars).
- M5 public OHLC is used for sequencing. Same-M5 stop/target ordering remains ambiguous.
- Ambiguous outcomes are shown as primary (0R), pessimistic (-1R) and optimistic (+2.5R) bounds.
- Completed test years: 2022–2025. Earlier data is used for chronological selection.
- Walk-forward floor selection uses only earlier years and maximizes pessimistic opportunity expectancy subject to at least 85% candidate eligibility.
- Paired bootstrap compares walk-forward candidate vs the unchanged structural-stop baseline.

## Evaluation
For every pair/floor/year report eligibility, fill rate, target wins, stop losses, timeouts, ambiguity, resolved win rate, primary/pessimistic/optimistic R expectancy, median risk pips and p90 risk pips.

Also report maximum adverse excursion (MAE) among baseline historical winners to quantify how much room winning trades typically required before reaching 2.5R.

## Decision discipline
Do not promote a pip floor merely because it has the highest pooled win rate. Prefer a region that is stable across pairs/years, improves or preserves pessimistic expectancy, reduces sensitivity to spread/noise, and survives chronological walk-forward comparison.

Any candidate remains research-only until prospective paper observations accumulate. Dollar risk remains separate: V2 can keep 1% paper-account risk by reducing position size when the stop distance is wider.
