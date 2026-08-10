# V2 Intelligence Lab v1.3 — automatic paper-trade engine

## Purpose
Record deterministic research paper trades automatically from the live V2 formation engine. This is not broker execution and must never be presented as an executable fill record.

## Frozen paper-trade protocol
A paper trade may be armed only after the live engine has confirmed BOS and a fresh POI (Stage 6+ with `fresh=true`).

- Instrument scope: EURUSD, GBPUSD.
- Entry: 50% midpoint of the live POI zone.
- Entry timing: only a future completed M15 bar after the BOS bar may fill the midpoint. No retroactive same-BOS-bar fill.
- Entry expiry: 8 completed M15 bars after BOS.
- Stop: sweep extreme plus/minus a 0.03 ATR buffer, using ATR captured when the trade is armed.
- Risk gate: 0.08–1.60 ATR, matching the public proxy research protocol.
- Target: fixed 2.5R.
- Maximum hold: 48 M15 bars after entry.
- Outcome: win, loss, timeout, ambiguous, expired, invalid.
- If stop and target are both touched by the same M15 bar, the engine must attempt public 5m path resolution. If ordering is still ambiguous, record `ambiguous`; never choose the profitable ordering.
- Reference/display prices do not trigger entries or exits. Only same-source completed structural bars do.
- Costs are not deducted because no broker execution feed is connected. Gross research R and execution-truth warning are stored separately.

## Integrity
Paper trades are a new derived research layer. They do not change the Stage 0–8 detector, campaign definitions, or historical validation rules. The engine is idempotent: one paper-trade plan per sweep/campaign source setup.

## Charting
The free TradingView embed remains an audit chart. Its embed does not expose our application to the Advanced Charts drawing API. The app therefore adds a separate controlled Research Chart using TradingView Lightweight Charts, on which POI, entry, SL, TP, and paper-trade event markers can be drawn programmatically.
