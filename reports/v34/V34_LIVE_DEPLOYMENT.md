# V3.4 Live Deployment Record

Date: 2026-08-14

## Production policy

V3.4 changes market understanding and prospective research capture. It does **not** change the frozen baseline paper-trade entry, stop or target.

## Supabase

### market-intelligence

- Function ID: `437af9cc-9ed9-4380-8d76-9cba607d589b`
- Version: 3
- Status: ACTIVE
- JWT verification: enabled
- SHA256: `376a14d211598ed28617f9944b9b12c662af26152e0bfc6f43f48d3b9d2f0be0`
- Live output version: `V3.4-market-map-alpha.3`

Responsibilities:

- structural trend on M15/H1/H4/D1/W1/MN1
- EMA direction retained separately
- prior day/week/month high-low map
- repeated H4 high/low clusters
- nearest liquidity normalized by M15 ATR
- session ranges
- candle body/wick classification
- BOS displacement and strict three-candle FVG diagnostics
- POI candle/freshness diagnostics when available
- persists the current market map under `market_states.details.marketIntelligence`

Higher-timeframe daily source is cleaned of non-positive OHLC before weekly/monthly aggregation.

### market-intelligence-runner

- Function ID: `8d0d265e-3457-4f4a-b803-402d23b399bf`
- Version: 4
- Status: ACTIVE
- SHA256: `d4f384feff2a6b6c760042551de7d4ca211c74bfd15744a1bdb05cc5be166387`

Responsibilities:

- invokes the protected market-intelligence function
- freezes Stage-3+ context in `market_intelligence_snapshots`
- links snapshots to active formation campaigns and paper trades when available

### prospective snapshots

Table: `public.market_intelligence_snapshots`

- RLS enabled
- no browser write policy
- service-role research writes only
- one frozen observation per completed M15 bar / stage / direction / market-map version

Initial verified snapshots:

- EURUSD short Stage 3, completed bar 2026-08-14 12:30 UTC
- GBPUSD short Stage 3, completed bar 2026-08-14 12:30 UTC

### recurring collection

- pg_cron job ID: `28`
- name: `v34-market-intelligence`
- schedule: `4,19,34,49 * * * *`
- active: true

This is positioned a few minutes after M15 boundaries so the core market-state engine has time to ingest the completed structural candle before V3.4 freezes the research context.

### trader-brief

- Function ID: `c6adf3e2-09a6-4c39-b661-a99e5c7b8798`
- Version: 2
- Status: ACTIVE
- SHA256: `5edf4140035ef569467c33bf0674d520a741a3e3831c239eee3e5156ecdeac71`
- Output version: `V3.4 Trader Brief market-map`

It exposes a compact `marketMap` object for each pair while retaining the research boundary and unchanged frozen trade rules.

## Frontend

Files added:

- `web/v34-market-map.js`
- `web/v34-market-map.css`

Loader updated:

- `web/v29-market-context.js`

The Focus view now shows a compact Market Map:

- MN / W / D / 4H / 1H / 15M structural direction
- current formation versus higher-timeframe structure
- nearest mapped liquidity
- current M15 candle classification
- BOS displacement/FVG/POI impulse context once BOS exists
- explicit `Does not veto trades` boundary

## Vercel production

Pinned Git commit:

`26f14c4ce9abd5fe401b238c5fe2469cfb1a880d`

Deployment:

- ID: `dpl_7UGm8KGLLnjGEWZDvL8pvquPbyUn`
- State: READY
- Target: production
- Alias: `v2trading.vercel.app`
- Alias error: none

Production bootstrap was fetched after deployment and verified to contain the exact pinned commit above.

## Safety / research boundary

The V3.4 historical promotion study rejected all tested hard context filters. Therefore:

- Monthly/Weekly alignment does not cancel a baseline trade.
- FVG does not create a trade.
- candlestick patterns do not delay the midpoint entry.
- session does not create/cancel a trade.
- Dapo/Kojo proxy rules do not control production.
- the midpoint entry, structural stop and 2.5R target remain frozen.

V3.4 improves what the engine **knows and records**, then collects prospective evidence before allowing any new context rule to influence the baseline.
