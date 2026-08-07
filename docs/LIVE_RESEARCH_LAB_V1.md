# V2 Research Lab v1 — Zero-Cost Live Market Architecture

## Purpose

V2 Research Lab v1 turns the project from a backtest-only dashboard into a live market-state research tool while keeping live trading and buy/sell signals disabled.

The lab is designed to answer:

- What is each market doing now?
- What are D1/H4/H1/M15 trend states?
- What market regime is present?
- Is price near a meaningful liquidity area?
- Has a V2-like liquidity sweep occurred?
- Has BOS occurred after that sweep?
- Is a fresh POI available?
- Is price approaching or inside the research POI?
- How fresh and trustworthy is the underlying free data?

It does **not** answer "should I buy or sell now?"

## Zero-cost constraint

This version uses only services/accounts already present in the project and public/no-key market sources.

- Supabase Free: database, Edge Functions and Cron.
- Vercel Hobby: public research UI.
- GitHub: source of truth and CI.
- Yahoo Finance public chart endpoint: public chart/history reference.
- exchangerate.dev anonymous endpoint: EUR/USD and GBP/USD live reference mid-rates when available.
- goldprice.dev anonymous endpoint: XAU/USD spot reference plus bid/ask when available.
- TradingView free widget: interactive chart visualization only; its data is not fed into the research engine.

No paid API key is required.

## Instrument mapping

| Research symbol | Live/reference price | Structure chart | Important limitation |
|---|---|---|---|
| EURUSD | exchangerate.dev; Yahoo fallback | Yahoo EURUSD=X | Public reference, not broker execution feed |
| GBPUSD | exchangerate.dev; Yahoo fallback | Yahoo GBPUSD=X | Public reference, not broker execution feed |
| XAUUSD | goldprice.dev spot; Yahoo fallback | COMEX GC=F | Futures structure is a proxy for spot XAU/USD |
| US30 | Yahoo YM=F | E-mini Dow futures YM=F | Futures context is a proxy for a broker US30 CFD |

## Architecture

```text
Public/no-key data sources
         |
         v
Supabase Edge Function: market-lab
         |
         +--> validate/filter bars
         +--> D1/H4/H1/M15 trend model
         +--> volatility/regime classifier
         +--> swing/liquidity context
         +--> V2 formation state machine
         +--> deterministic research narrative
         |
         v
Supabase Postgres
  market_states        current state
  market_bars          growing research bar archive
  market_state_history 15-minute observation history
  provider_cache       rate-limit protection
         |
         v
Vercel V2 Research Lab
```

Supabase Cron invokes the market-lab Edge Function every five minutes. The function only appends a state-history observation roughly every 15 minutes, controlling database growth while building a time series for later validation.

## Formation state machine

The V2 engine is observational and deterministic.

0. `NO_SETUP`
1. `LIQUIDITY_NEARBY`
2. `POI_USED` / previous sequence no longer fresh
3. `SWEEP_CONFIRMED`
4. `WAITING_FOR_BOS`
5. `BOS_CONFIRMED`
6. `FRESH_POI_IDENTIFIED`
7. `APPROACHING_POI`
8. `ENTRY_ZONE_REACHED`

Stage 8 is explicitly labelled a **research entry zone**, not a signal.

## Trend model

For each timeframe, the engine evaluates completed bars using:

- EMA20 location;
- EMA20 vs EMA50 separation;
- short EMA20 slope;
- ATR-normalized distances.

The score is deliberately clipped before classification so malformed or anomalous bars cannot create absurd confidence values.

Output:

- bullish
- bearish
- mixed
- strength 0–100

## Regime model

Current classifications:

- trending
- ranging
- transition
- volatility expansion
- volatility compression

The classifier combines H4 EMA separation relative to ATR with M15 ATR relative to its recent median.

## Data-quality rules

- zero/negative/malformed OHLC bars are rejected;
- incomplete bars are excluded from analysis;
- XAUUSD and US30 proxy status is visible in both API and UI;
- broker execution truth is marked unavailable;
- free-provider failures fall back to cached state rather than inventing prices;
- state refresh errors do not overwrite the last valid state;
- all research output is labelled research-only.

## Why this is useful even before v0.5 MT5 validation

v0.4 showed that the old candle labels could not be trusted as executable outcomes across independent feeds. That invalidates using the old probability model for live signals, but it does **not** invalidate observing market structure.

Therefore v1 focuses on facts that can be determined at the current timestamp:

- price/reference state;
- completed-bar trend;
- liquidity and swing locations;
- structural sweep/BOS/POI progression;
- regime;
- data freshness.

This allows the project to start collecting a prospective dataset now. Later, each observed state can be compared with future outcomes without rewriting history.

## Next research uses of the new history

Once enough observations accumulate, the lab can study:

1. transition probabilities between formation stages;
2. how often a sweep reaches BOS;
3. how often a BOS creates a fresh POI;
4. how often price reaches that POI;
5. regime-conditioned formation completion rates;
6. D1/H4 alignment vs formation completion;
7. market/session differences;
8. proxy-vs-broker divergence when a broker feed eventually becomes available.

Those are safer and more informative next questions than immediately training another prediction model.
