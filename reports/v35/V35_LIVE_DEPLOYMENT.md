# V3.5 Trend-Candle Challenger — Live Deployment

Deployed 2026-08-15.

## Historical research
- Preregistered protocol: `reports/v35/V35_TREND_CANDLE_ENGINE_PROTOCOL.md`
- Successful GitHub Actions run: `31858185672`
- Artifact: `9239726274` (`v35-trend-candle-engine`)
- Frozen data window: completed years 2022–2025, EURUSD + GBPUSD public M5 OHLC
- Findings: `reports/v35/V35_TREND_CANDLE_ENGINE_FINDINGS.md`
- No primary family passed the historical promotion gate.
- `KOJO_PX_3R` is the sole prospective watchlist family because it had a small positive pooled mean R, but it is explicitly not historically promoted.

## Supabase shadow engine
- Edge Function: `trend-candle-engine`
- Active version: 2
- Engine label: `V3.5-trend-candle-alpha.2`
- SHA256: `ce078e40aac2baa185a5940e64873e435d2abbc495d22f54626e60cee8537c7c`
- Cron: `v35-trend-candle-engine-1m`
- Cron job id: 31
- Schedule: every minute
- Tables: `trend_candle_snapshots`, `trend_candle_signals`
- RLS: enabled; no public table policy. Service-role access is used by Edge Functions. Browser access is through the read-only Edge Function response.

The live engine is independent of baseline V2 formation eligibility. It reads market-intelligence context plus completed M15/H1/H4 bars, applies a current-clock FX weekend guard, data-health guard, and a <=30 minute completed-M15 freshness requirement before any challenger signal can be written.

At final Saturday verification, both EURUSD and GBPUSD correctly returned `FX weekend closed` and no candidates.

## Discord
- Edge Function: `discord-trend-candle`
- Active version: 1
- SHA256: `cdc940c98f5b8b508a559dad4f0cfc32675c9b142656b4ba9a384259f9869a9a`
- Cron: `v35-discord-trend-candle-1m`
- Cron job id: 32
- Schedule: every minute
- Alert family: `KOJO_PX_3R` only
- Every message is labeled `Trend-Candle Challenger` and says the family failed historical promotion.
- TCR, BRC and DFP signals may remain in the research ledger but are not pushed as watchlist Discord alerts because their frozen historical expectancy was negative.

Manual final checks returned HTTP 200 for both the V3.5 engine and Discord challenger. No weekend message was sent.

## UI
Files:
- `web/v35-trend-candle.js`
- `web/v35-trend-candle.css`
- loaded by `web/v32-ui.js`

The Focus view contains a separate `Trend + Candle Challenger` card showing:
- market open/blocked state;
- D1/H4/H1/M15 structural trend;
- nearest support and resistance;
- current mathematical candle trigger;
- current standalone candidate, if any;
- historical Kojo watchlist evidence;
- candle-only negative-control result;
- rejected TCR/BRC/DFP results.

The card is intentionally separate from Setup Quality so experimental price-action evidence cannot masquerade as baseline V2 confidence.

UI production commit before this deployment note: `f710c707d147e98483cea57629ea29c13f105831`.
Vercel production deployment for that UI: `dpl_dUEdtd8nDz3bXiorzkNntDWStdza`.

## Baseline boundary
Nothing in V3.5 changes:
- baseline V2 sweep/BOS/POI eligibility;
- frozen 50% POI midpoint entry;
- baseline stop/2.5R target;
- the $500 baseline paper account;
- broker-execution boundary.

V3.5 is a separate shadow research engine intended to accumulate prospective evidence.
