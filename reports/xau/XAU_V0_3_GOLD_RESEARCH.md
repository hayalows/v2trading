# V2 XAU v0.3 — Gold Research Lane

**Status: live research infrastructure, no XAU trade-rule promotion.**

## Why XAUUSD is separate

Gold is not treated as a third FX pair by assumption. V2 reuses only scale-normalized structural primitives (completed-candle trends, ATR-normalized sweep/BOS/POI geometry, regime diagnostics). Entry depths, stop geometry, timeouts, break-even rules, partial exits, costs and risk sizing must be revalidated specifically on XAUUSD.

## Data solution

Primary source: Dukascopy XAU/USD public/indicative market data.

The implementation uses two layers:

1. **Historical seed / reconciliation** — `xau-history-seed` downloads public Dukascopy XAU/USD minute history, aggregates M15/H1/H4, retrieves D1 data, and upserts the bars into `market_bars`. It runs daily to repair gaps and reconcile recent history.
2. **Near-live state path** — `xau-state-engine` refreshes the current Dukascopy minute stream, then reads the newest stored M15/H1/H4/D1 bars by timeframe. It computes XAU-specific market state and writes `market_states.XAUUSD`. It runs every minute.

Initial seed on 2026-08-12 recovered 24,198 minute observations from 2026-07-19 through the live session, producing 1,614 M15, 404 H1, 109 H4 and 190 D1 observations before later deduplication/query limits.

Dukascopy's public current-minute path is used as an **indicative reference**, not an executable broker price. ASK/spread is withheld from the canonical state until BID and ASK timestamps are proven aligned. A mathematically impossible negative spread is never coerced into evidence.

## Current state logic

V2 XAU computes:

- D1 / H4 / H1 / M15 directional state and strength
- M15 ATR and rolling volatility percentile
- directional efficiency and regime (trend, range, transition, expansion, compression)
- liquidity sweep detection
- completed-close BOS confirmation
- post-BOS POI identification
- distance to POI in ATR units
- higher-timeframe support/conflict
- regime-shift diagnostics
- data freshness and latest completed M15 timestamp

Stages remain structurally compatible with V2:

0 no setup → 1 liquidity nearby → 3 sweep → 4 wait BOS → 5 BOS → 6 fresh POI → 7 approaching POI → 8 research entry zone.

These stage numbers are a shared observation language, not evidence that FX-calibrated probabilities transfer to gold.

## Macro/event layer

Gold must be evaluated with USD macro risk and geopolitical context. V2's existing macro layer tracks official-confirmed/high-impact USD releases such as CPI. A clean technical state immediately before CPI/FOMC/NFP/PCE is not treated as equivalent to the same geometry in a quiet session.

Macro context is a risk/volatility modifier, not a directional oracle.

## Free-source hierarchy

### Primary
- Dukascopy public XAU/USD minute/candle data: near-live structure + historical reconciliation.

### Secondary references / watchdog candidates
- Twelve Data: XAU/USD and WebSocket support, but the free tier/key limits make it better as a watchdog than V2's primary anonymous feed.
- Alpha Vantage: useful free-key live gold spot/reference endpoint, but not the preferred source for the M15 historical structure V2 needs.
- OANDA practice/API: valuable later for broker-like quote/execution validation, but requires an account/token and must not be mislabeled as anonymous free data.

## Model challengers

No model can replace the structural baseline from a backtest headline. The initial model arena is:

1. **Frozen XAU structural baseline** — current V2 state machine, XAU-calibrated only after historical testing.
2. **Chronos-2** — zero-shot time-series challenger using M15 returns/volatility plus known covariates where available.
3. **TimesFM 2.5** — independent zero-shot foundation-model challenger.
4. **LightGBM / XGBoost controlled tabular challenger** — ATR, efficiency, regime, session, structure, event-distance and liquidity features.
5. **Qlib experiment harness** — chronological training, walk-forward evaluation, model comparison and drift analysis.

Foundation-model output is never interpreted directly as BUY/SELL. Forecasts must be converted to preregistered features or probability forecasts and judged out-of-sample.

The Hugging Face connector returned upstream timeout/502 errors during the 2026-08-12 investigation, so no Hugging Face search result is being claimed as evidence. Chronos-2 and TimesFM were selected from their primary maintained repositories instead.

## XAU validation protocol

Before any XAU paper-entry rule is promoted:

1. Freeze signal-time geometry. Never use future POI status or future maximum penetration as a feature.
2. Reconstruct historical XAUUSD M15 state chronologically.
3. Test POI depth continuously and in 5% bins from 0–100%. The midpoint is a comparator, not an assumed gold optimum.
4. Compare fill rate **and unconditional opportunity expectancy**, not only win rate conditional on fills. Deeper entries can look superior while silently discarding most opportunities.
5. Test exit policies independently: current 48-bar timeout, 96-bar, 192-bar, hold-to-SL/TP, break-even challengers and partial-profit challengers.
6. Resolve intrabar ordering with finer data. If order still cannot be established, mark the row ambiguous rather than choosing the favorable outcome.
7. Apply cost stress using observed/validated XAU spread and slippage assumptions. Public BID-only bars are not execution truth.
8. Split by session, volatility regime and high-impact USD-event proximity.
9. Use chronological walk-forward years/periods. No random train/test split for final acceptance.
10. Start prospective shadow collection after the rules are frozen. Historical success alone cannot promote a live rule.

## Promotion boundary

For now:

- XAU can appear in the web app as **WATCH / WAIT / REVIEW** research state.
- XAU can send one-way structural/data-health alerts to Discord.
- XAU does **not** enter the $500 1%-risk portfolio.
- XAU does **not** inherit EURUSD/GBPUSD POI-depth, exit-policy or risk conclusions.
- No live-money claim is made.

A later XAU paper-trade release requires a separate frozen historical report and prospective gate.

## Sources used for the design

- Dukascopy Trading Tools API documentation — current quotes, historical prices and latest one-minute candles.
- `Leo4815162342/dukascopy-node` — maintained open-source Dukascopy client and active-current-period URL/decoder implementation.
- Amazon Science `chronos-forecasting` — Chronos-2 time-series foundation model.
- Google Research `timesfm` — TimesFM 2.5.
- Microsoft `qlib` — open quantitative research, backtesting and model workflow platform.

This document records the architecture before XAU profitability testing so later results cannot silently rewrite the acceptance criteria.