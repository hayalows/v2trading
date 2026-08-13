# V3.1 Early Setup Quality — Results

## Question
Can V2 identify higher-quality EURUSD/GBPUSD paper setups earlier, reliably enough to make the product more intuitive, without pretending to know which individual trade will win?

## Frozen boundary
- EURUSD + GBPUSD only.
- Same historical V2 setup universe used by the stop-distance research.
- V3.0 breathing-room policy evaluated at 4 pips EURUSD / 5 pips GBPUSD.
- Outcome label: full 2.5R win versus loss/timeout; ambiguous paths excluded.
- Historical model testing is chronological/walk-forward.
- No current-trade win probability is exposed.
- No quality grade is allowed to move the entry, stop, target or account dollar risk automatically.

## 1. Pre-entry geometry alone is not reliable enough
A regularized logistic model used only information available before the POI interaction: symbol, direction, session, POI width/ATR, BOS displacement/ATR, sweep-to-BOS bars, candidate risk/ATR, structural risk pips, ATR pips and whether the breathing-room floor would apply.

Walk-forward results:

| Test year | AUC | Model Brier | Base-rate Brier |
|---|---:|---:|---:|
| 2022 | 0.5286 | 0.21980 | 0.21846 |
| 2023 | 0.5421 | 0.21151 | 0.21031 |
| 2024 | 0.5069 | 0.19854 | 0.19774 |
| 2025 | 0.5381 | 0.22114 | 0.22065 |

Decision: **REJECT_PRE_ENTRY_GEOMETRY_AS_WINNER_DETECTOR**.

The discrimination is only slightly above random and calibration does not improve reliably. V2 should therefore not label a setup "high probability" before the market interacts with the POI.

## 2. The first POI interaction is the earliest useful quality signal
Adding the first-interaction state materially improved discrimination:

| Test year | AUC | Model Brier | Base-rate Brier |
|---|---:|---:|---:|
| 2022 | 0.5728 | 0.21369 | 0.21846 |
| 2023 | 0.5894 | 0.20804 | 0.21031 |
| 2024 | 0.5522 | 0.19789 | 0.19774 |
| 2025 | 0.5898 | 0.21558 | 0.22065 |

Pooled OOS AUC was about **0.580**. This is useful as a qualitative attention layer, but still too modest for a visible current-trade probability.

## 3. Direct midpoint interaction versus prior shallow touch
Completed-year 2022–2025 results under the 4/5-pip breathing-room policy:

| First-interaction pattern | n | Win rate | Mean R |
|---|---:|---:|---:|
| Direct midpoint on first interaction | 316 | 42.405% | +0.5004R |
| Prior shallow/grazing touch before later midpoint | 805 | 27.329% | -0.00067R |
| Close through distal boundary | 48 | 8.33% | -0.7083R |

Month-cluster bootstrap, direct minus prior-shallow:
- win-rate difference: **+15.08 percentage points**
- 95% interval: **+6.42 to +23.92 percentage points**
- mean-R difference: **+0.501R**
- 95% interval: **+0.199R to +0.807R**

The direct-first-interaction advantage was positive in nearly every year/pair slice. The weakest slice was GBPUSD 2023, where direct and shallow outcomes were similar.

Decision: **PROMOTE_FIRST_INTERACTION_TO_QUALITATIVE_SETUP_QUALITY**.

## Product labels
V3.1 uses plain-language labels rather than probabilities:

- **Waiting for first interaction** — POI exists but has not been touched.
- **Zone interaction** — price has begun touching the zone but the midpoint has not been reached.
- **Strong interaction** — the midpoint is reached on the first recorded POI interaction.
- **Weakened setup** — price touched the POI shallowly before returning later to the midpoint.
- **Late return** — the move had already delivered about 2.5R before returning to entry.
- **Broken setup** — structural invalidation/close-through.

These labels describe observed setup quality. They do not assert that the next trade will win.

## Why microstructure is not promoted to winner authority yet
FX research supports the idea that order flow contains short-horizon information, but out-of-sample economic value from richer order-book predictors is inconsistent. V2 therefore keeps public BID/ASK spread, tick activity and execution-path checks as friction/data-quality evidence only.

Future prospective challenger work should test:
1. spread as a fraction of stop distance,
2. executable-side entry confirmation,
3. tick/activity regime,
4. short-horizon price acceleration after first interaction,
5. scheduled-event proximity,
6. cross-pair state coherence.

Each candidate must beat a simple base-rate benchmark prospectively before it can influence the quality label.

## Live learning
`paper_trade_quality_snapshots` freezes checkpoints at:
- armed,
- first POI touch,
- entry,
- close.

The V3.1 release timestamp is stored in `v31_quality_release`; only observations whose actual checkpoint timestamp is after the release count as prospective evidence.

## Current live-journal denominator
At release time the entered journal contained:
- 1 win,
- 2 losses,
- 1 numeric timeout,
- 1 ambiguous outcome.

So:
- decisive win rate = 1 / (1 + 2) = **33.3%**,
- scored-closure win share including the timeout = 1 / (1 + 2 + 1) = **25.0%**,
- ambiguous outcome excluded from both.

The sample is far too small to estimate a stable live edge.
