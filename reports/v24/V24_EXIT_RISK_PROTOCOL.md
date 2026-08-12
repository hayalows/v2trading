# V2 v2.4 Exit, Break-even and Risk Policy Protocol

**Status: frozen before results. Research only.**

## Question

For the frozen V2 EURUSD/GBPUSD midpoint research setup, which exit-management rules retain the strongest chronological out-of-sample expectancy and capital growth without unacceptable drawdown?

This study does not alter the current paper-trade baseline and does not claim broker execution truth.

## Data and setup geometry

- Markets: EURUSD and GBPUSD.
- M15 setup detection and exact full-candle POI geometry are inherited from v1.9/v2.0.
- Entry depth: 50% midpoint only for this exit study, so exit policies are compared on common entry geometry.
- Risk gate: 0.08 to 1.60 ATR.
- Entry observation tail: up to 192 completed M15 bars after BOS, matching the POI lifecycle study.
- Stop: frozen sweep extreme plus/minus 0.03 ATR.
- Full target: fixed 2.5R.
- M5 is used to reduce path-order ambiguity. If event ordering remains unknowable inside the same M5 candle, the policy row stays ambiguous rather than receiving the favourable ordering.
- Primary completed test years: 2022, 2023, 2024, 2025.

## Frozen policy family

Baseline and time policies:

1. `timeout_48`: current 48-M15-bar post-entry research timeout.
2. `timeout_96`: 96-bar mark-to-market timeout.
3. `timeout_192`: 192-bar mark-to-market timeout.
4. `hold_sltp`: no time exit inside a 1,920-M15-bar research observation tail; stop or 2.5R target resolves the trade. Anything still unresolved is censored, not forced to a win/loss.

Break-even policies:

5. `be_075`: move remaining stop to entry after +0.75R.
6. `be_100`: move remaining stop to entry after +1.00R.
7. `be_125`: move remaining stop to entry after +1.25R.
8. `be_150`: move remaining stop to entry after +1.50R.

Partial-profit + break-even policies:

9. `p25_100_be`: realize 25% at +1.00R, move the remaining 75% stop to entry, keep the 2.5R target.
10. `p33_100_be`: realize 33% at +1.00R, move 67% to break-even.
11. `p50_100_be`: realize 50% at +1.00R, move 50% to break-even.
12. `p25_150_be`: realize 25% at +1.50R, move 75% to break-even.
13. `p33_150_be`: realize 33% at +1.50R, move 67% to break-even.
14. `p50_150_be`: realize 50% at +1.50R, move 50% to break-even.

No trailing-stop grid is added in this release. It would enlarge the search space before the simpler family is validated.

## Primary metrics

For each policy and test year:

- resolved trade count;
- ambiguity/censoring rate;
- mean and median R;
- positive-R rate, loss rate, break-even rate and full-target rate;
- profit factor where defined;
- final hypothetical equity from $500 using 1.00% of current equity risked per trade;
- maximum drawdown on that sequential research equity curve;
- expected log-growth contribution at 1% risk.

The $500 account is a reporting convention, not broker sizing advice.

## Chronological selection test

For each test year 2022-2025:

1. Rank policies using only prior years.
2. Require at least 100 resolved training trades.
3. Primary training objective: mean log growth at 1% risk.
4. Tie-break: lower maximum drawdown, then higher mean R.
5. Freeze the selected policy and score it on the next year.
6. Compare it with `timeout_48` and `hold_sltp` on common eligible setups.

A policy is not promoted from descriptive research unless the pooled walk-forward delta versus the baseline is positive, at least 3 of 4 completed test years are non-inferior, and the bootstrap interval does not show material downside large enough to erase the practical gain.

## Risk policy

- Product/reporting baseline: **1.00% risk per trade**.
- Also simulate 0.50%, 1.50% and 2.00% as exposure overlays on the same frozen R stream.
- A winning streak alone never increases risk.
- 1.50% and 2.00% remain research-only until there is a sufficiently large independent prospective sample, positive stressed expectancy, and acceptable drawdown under resampling.
- Risk scaling will be evidence-based and drawdown-aware, not martingale or streak-based.

## POI depth boundary

The existing v2.0 prospective 0%-100% depth shadow grid continues unchanged. This exit study must not use the exit results to retroactively select a POI depth. Entry-depth and exit-policy promotion require separate chronological/prospective gates.

## Interpretation boundary

Public OHLC/M5 data are structural research data. The v0.4 executable-label failure remains in force. Results may change the research shadow layer, but no policy can be called live-money ready without execution-safe bid/ask validation.