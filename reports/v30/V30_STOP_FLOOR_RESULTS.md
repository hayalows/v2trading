# V2 v3.0 — Stop breathing-room results

## Decision
**KEEP THE CURRENT STRUCTURAL STOP AS CANONICAL. SHADOW-TEST MINIMUM STOP FLOORS.**

The multi-year M5 replay does not justify replacing the sweep-extreme + 0.03 ATR structural stop with one fixed pip stop. The useful intervention is a **minimum breathing-room floor**: never tighten the structural stop; widen only unusually tight plans.

Two research candidates emerged:

1. **Performance candidate:** 3 pip minimum on EURUSD and GBPUSD.
2. **Breathing-room candidate:** 4 pip minimum on EURUSD and 5 pip minimum on GBPUSD.

Neither is promoted automatically.

## Frozen study
- Exact V1.9 Stage-6 setup universe.
- 2,090 independent completed-year midpoint setups in 2022–2025.
- Entry unchanged at 50% POI midpoint.
- Existing sweep stop + 0.03 ATR never tightened.
- Candidate risk = max(structural risk, pip floor).
- Candidate floors: 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15 pips.
- Target remains 2.5R from the candidate risk distance.
- Existing 0.08–1.60 ATR risk-distance gate retained.
- 192 M15-bar entry wait; 48 M15 bars post-entry.
- Public M5 path sequencing; same-M5 ordering remains ambiguous.

## What the existing structural stop already does
Completed-year baseline median risk distance:
- EURUSD: **3.88 pips**; p90 **9.24 pips**.
- GBPUSD: **5.22 pips**; p90 **14.15 pips**.

So V2 already gives structurally wide trades more room. The problem is the unusually tight tail, not the normal stop.

## Performance candidate — 3 pip minimum on both pairs
EURUSD:
- eligibility 99.2%
- resolved win rate 31.9%
- primary opportunity expectancy +0.073R vs +0.062R baseline
- M5 ambiguity among fills 25.3% vs 35.2% baseline

GBPUSD:
- eligibility 99.7%
- resolved win rate 32.1%
- primary opportunity expectancy +0.088R vs +0.061R baseline
- M5 ambiguity among fills 26.6% vs 33.0% baseline

Combined primary delta vs baseline: about **+0.019R/setup**. A secondary month-cluster bootstrap over 48 months produced an approximate 95% interval of **-0.005R to +0.043R**, so the profit improvement is **not statistically secure**.

## Breathing-room candidate — EURUSD 4 pips / GBPUSD 5 pips
This policy is closer to each pair's natural median structural risk and materially reduces path uncertainty.

EURUSD 4-pip floor:
- eligibility 92.3%
- primary expectancy +0.055R vs +0.062R baseline
- pessimistic expectancy -0.102R vs -0.220R baseline
- ambiguity among fills 19.6% vs 35.2%

GBPUSD 5-pip floor:
- eligibility 95.3%
- primary expectancy +0.070R vs +0.061R baseline
- pessimistic expectancy -0.082R vs -0.217R baseline
- ambiguity among fills 18.1% vs 33.0%

Combined:
- eligibility 93.9%
- primary expectancy +0.0628R vs +0.0616R baseline — essentially unchanged
- ambiguous M5 outcomes 323 vs 586 baseline, about **45% fewer**
- pessimistic expectancy -0.0917R vs -0.2187R baseline

A secondary month-cluster bootstrap for the primary-return delta spans roughly **-0.037R to +0.040R**, so this is best interpreted as a market-breathing/execution-quality candidate, not proven extra alpha.

## How much adverse movement did historical winners need?
Under the unchanged structural baseline, before reaching 2.5R:

EURUSD winners (n=166):
- median MAE 1.60 pips
- 80th percentile 3.40 pips
- 90th percentile **5.10 pips**
- 95th percentile **5.75 pips**

GBPUSD winners (n=182):
- median MAE 1.95 pips
- 80th percentile 4.85 pips
- 90th percentile **6.25 pips**
- 95th percentile **9.07 pips**

This does **not** mean every stop should be 5–9 pips. It shows why the stop should remain structural and why 1–2 pip plans deserve special scrutiny.

## Why not simply use 7–10 pips everywhere?
Wider floors reduce same-bar ambiguity, but they also push the 2.5R target farther away and cause many setups to fail the existing 1.60 ATR risk-distance gate. Eligibility falls sharply as the floor rises. The structural stop already becomes 7–15+ pips when the setup itself requires that much room.

## Live sample sanity check
The live paper sample remains far too small for inference, but it currently contains entered risks around 1.01, 1.62, 2.23, 3.22 and 7.45 pips. The 1.01-pip case is ambiguous, the 1.62- and 2.23-pip cases are losses, the 3.22-pip EURUSD case reached +2.5R, and the 7.45-pip GBPUSD case timed out at a partial loss. This is directionally consistent with investigating the tight-stop tail, but **n=5 is not evidence**.

## Recommended next experiment
Keep canonical P&L frozen and prospectively shadow every new entry with:
- canonical structural stop
- 3-pip performance floor
- EURUSD 4-pip / GBPUSD 5-pip breathing-room floor

Use the public BID/ASK/tick execution layer whenever available. Require at least 30 paired entered observations before descriptive comparison and 100 before an evidence-ready decision. Compare paired R, stop-outs that later reach target, exact-tick ambiguity, MAE, timeout rate, pair/year/session stability, and account drawdown under fixed 1% dollar risk.

## Boundary
Public M5 OHLC cannot determine ordering inside one five-minute candle and is not a broker fill feed. The historical result therefore supports a prospective challenger, not an automatic stop-rule change.
