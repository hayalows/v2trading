# V2 Research Lab v1.1 — Five-Lens Intelligence Upgrade

## Goal

The upgrade is designed to make the lab materially more useful without confusing model complexity with evidence quality. The central change is to move from snapshot-only market states to event-sourced formation episodes with measured forward outcomes and explicit abstention when evidence is insufficient.

## Researcher 1 — Quant validation

### Proposal
Use the prospective stream to build Stage-3/5/6 episode labels, then train increasingly sophisticated models only after point-in-time outcomes and sample sizes are sufficient.

### Reviewer 1
Rejected immediate deployment of foundation forecasting models, Transformers, RL, or a new black-box classifier. Chronos/Qlib-style models are useful research candidates, but they cannot repair invalid execution labels or a tiny live calibration sample.

### Accepted
- event-level prospective labels
- fixed forward horizons
- direction-adjusted returns
- MFE/MAE
- sample-size gates
- future purged/embargoed walk-forward evaluation

## Researcher 2 — Market data and microstructure

### Proposal
Treat every formation as an event with explicit event time and preserve the exact observable state at that time.

### Reviewer 2
Requires research/live parity and forbids using a fresher display/reference price for BOS, POI, outcome or episode calculations.

### Accepted
- completed M15 structural prices only
- immutable episode anchor snapshots
- explicit data source and freshness
- broker execution truth remains unavailable and clearly separated

## Researcher 3 — Streaming / adaptive ML

### Proposal
Use rolling evidence and drift-aware modelling because FX distributions are non-stationary.

### Reviewer 3
Rejected training an online supervised model on the current live stream because the sample is too small and outcomes are not mature enough.

### Accepted
- rolling evidence summaries
- episode-level feature capture
- future drift monitoring
- later online/conformal adaptation only after sufficient calibration data

## Researcher 4 — Decision science and uncertainty

### Proposal
Convert model output into an evidence-backed research priority.

### Reviewer 4
Requires abstention. Any number that resembles a win probability must have a defensible calibration set and uncertainty interval.

### Accepted
Research priorities are deterministic and decomposable:
- Background
- Observe
- Review
- Investigate location

Evidence maturity is separate:
- Insufficient evidence
- Early evidence
- Building evidence
- Research-ready

No win probability is displayed.

## Researcher 5 — Mobile UX and human factors

### Proposal
The first mobile viewport should answer five questions:
1. What deserves attention?
2. What episode is active and how old is it?
3. What changed?
4. What must happen next?
5. How much evidence supports the interpretation?

### Reviewer 5
Rejects dense dashboards and raw state-refresh timelines. Requires event significance, progressive disclosure, 48px targets, direct chart access, and explicit research limitations.

## v1.1 architecture

```text
completed M15 state
      ↓
meaningful state transition
      ↓
formation episode
      ↓
stage anchors (3 / 5 / 6)
      ↓
forward outcome measurement
15m / 30m / 1h / 2h / 4h
MFE / MAE
      ↓
rolling evidence summaries
      ↓
research priority + abstention
      ↓
mobile-first V2 intelligence brief
```

## Episode definition

A new episode starts when the pair first enters Stage 3+ or when an active Stage-3+ episode changes direction. An episode ends when the formation drops below Stage 3, changes direction, reaches the maximum observation age, or transitions into a new independent sequence.

Each episode stores:
- symbol and direction
- started/ended time
- maximum stage reached
- first timestamps for Stage 3/4/5/6/7/8
- structural anchor prices for Stage 3/5/6
- point-in-time context snapshot
- data health/source metadata

## Outcome definition

Outcomes are descriptive market movement, not simulated PnL.

For Stage 3, 5 and 6 anchors we measure from completed M15 structural candles:
- raw return at +15m, +30m, +1h, +2h, +4h
- direction-adjusted return in bps
- maximum favorable excursion (MFE) in ATR units
- maximum adverse excursion (MAE) in ATR units

This avoids pretending we know broker fills, spread or slippage.

## Evidence gates

- n < 10 comparable completed anchors: **Insufficient evidence**
- 10–29: **Early evidence**
- 30–99: **Building evidence**
- >=100: **Research-ready descriptive evidence**

Even >=100 does not authorize a trade signal. A predictive model requires a separate preregistered experiment, time-aware validation, calibration and execution-safe labels.

## Future model candidates

Only after episode labels mature:
1. regularized logistic / LightGBM baseline
2. nearest historical analog retrieval
3. calibrated probability or quantile model
4. conformal intervals / abstention layer
5. rolling retraining / drift detection
6. only then compare Chronos/TimesFM/Transformer-style models against the simple baseline

Complexity must beat the simple model out of sample before it can enter the live decision layer.
