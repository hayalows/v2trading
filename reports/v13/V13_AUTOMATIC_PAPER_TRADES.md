# V2 Intelligence Lab v1.3 — Automatic Paper Trades

## Goal
Turn each eligible live V2 formation into a deterministic background research trade without requiring the user to manually record an entry.

## Paper-trade lifecycle
1. Stage 6+ confirms BOS and a fresh POI.
2. The plan is armed using the 50% POI midpoint.
3. SL is placed beyond the liquidity-sweep extreme with a 0.03 ATR buffer.
4. TP is fixed at 2.5R.
5. Only future completed M15 bars after the BOS candle can trigger the midpoint entry.
6. Entry expires after eight future M15 bars.
7. Once open, stop/target/timeout and MFE/MAE are recorded automatically for up to 48 M15 bars.
8. Same-M15 stop/target or entry/exit conflicts are checked on public 5m data; unresolved ordering is labelled ambiguous.

## Important distinction
These are research paper trades, not broker orders. The current lab has no broker-specific bid/ask, live spread, slippage, tick path, or executable fill confirmation.

## Reliability corrections during build
- Stage-6 recovery reads the recent immutable prospective history so a POI cannot be missed merely because the current state changes before the paper engine runs.
- A 5m-resolved entry candle is not re-evaluated later as if the trade had been open from the candle start.
- Current display/reference prices never trigger entries or exits.
- One paper plan is keyed to one source sweep, making evaluation idempotent.

## Chart architecture
The existing TradingView embed remains the manual audit chart. A new Research Trade Chart uses TradingView Lightweight Charts to render the same completed M15 research bars and programmatic POI, entry, SL, TP and event markers.

## Release gate
The v1.3 CI suite asserts the frozen 8-bar entry window, 48-bar hold, 0.03 ATR stop buffer, 2.5R target, future-only entry, recent Stage-6 history recovery, same-bar ambiguity policy, private RLS-backed journal tables, and chart overlay integration.
