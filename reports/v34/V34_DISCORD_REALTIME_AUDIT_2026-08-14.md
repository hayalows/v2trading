# V3.4 Discord and Realtime Audit — 2026-08-14

## Scope
Audit of V2 FX Discord delivery, paper-engine cadence, V3.4 market-intelligence freshness, UI exposure, and recent missed-event risk for EURUSD and GBPUSD.

## Findings
- No Stage 5, Stage 6, POI-ready, or new entry-ready formation occurred in the reviewed 24-hour window. Both core pairs remained at or below Stage 4, so there was no hidden trade setup that Discord failed to announce.
- Final recent paper-trade closures had Discord closure records. An intermediate EURUSD ambiguous event was later superseded by the final loss outcome; the final loss notification was sent.
- Core pg_cron jobs showed continuous scheduler execution. Separate HTTP-response auditing found a small number of downstream auxiliary failures/timeouts, proving scheduler success alone is not sufficient as a delivery-health signal.
- Discord generated substantial Stage 3/4 traffic because the underlying completed-M15 formation state repeatedly cycled between sweep-confirmed and waiting-for-BOS. This is structural event frequency, not polling-frequency spam.

## Bugs fixed
1. **Sharp-move pace mismatch**
   - Some 15-minute sharp-move alerts displayed `0.0× recent pace` because a 15-minute move was paired with a mismatched short-window pace multiplier.
   - `fx-market-context` v3 now calculates the multiplier from the selected move window.

2. **Transient setup-quality failure path**
   - A `trade-quality` timeout/500 could make `discord-quality-pulse` fail for that run.
   - `discord-quality-pulse` v2 now retries cleanly, records service health, and does not corrupt prior alert state when one request is transiently unavailable.

3. **V3.4 market map overwrite**
   - Normal market-state refreshes could overwrite `details.marketIntelligence`, causing the live UI/brief/Discord context to temporarily lose V3.4 data.
   - `market-intelligence-runner` v5 refreshes the durable per-M15 snapshot on each V3.4 run.
   - `trade-quality` v4 and `discord-v34-context` v3 use the latest immutable `market_intelligence_snapshots` row as their primary source of truth rather than relying on volatile nested market-state JSON.

## Cadence now active
- Paper-trade engine evaluation: every **1 minute**.
- Core Discord FX pulse: every **1 minute**.
- Discord trade closures: every **1 minute**.
- Discord setup-quality/proximity checks: every **1 minute**.
- V3.4 Discord context and delivery watchdog: every **1 minute**.
- V3.4 higher-timeframe market map: every **5 minutes**, aligned after pair-state refreshes.

One minute is the minimum supported scheduler cadence. The market-structure detector still uses completed M15 evidence; faster polling does not promote incomplete candles into signals. Recomputing the public completed-candle market map every minute would mostly repeat unchanged information while increasing provider/rate-limit risk, so the alert path uses the one-minute floor while the full map remains five-minute.

## New Discord protections
- Independent watchdog checks whether both core FX pulse states are fresh. If the pulse becomes stale for more than four minutes, Discord can report scanner degradation and later restoration.
- New low-noise V3.4 context alerts are reserved for meaningful events such as BOS context, a mature POI, or a nearby mapped liquidity level changing from untouched to swept/rejected or traded-through.
- The V3.4 context service itself checks every minute but does not send a message on every run.
- V3.4 context remains descriptive. It does not alter the frozen midpoint entry, stop, target, or trade eligibility rules.

## UI change
The Focus Setup Quality card now exposes a compact market-map strip with M15, H4, D1, W1 context, weekly range location, and V3.4 map freshness. Full liquidity, candle, FVG/displacement, POI and methodology details remain progressively disclosed under `Why this grade?` to keep mobile uncluttered.

## Research boundary
V2 remains a public-price paper-research system, not broker execution. Faster scanning improves detection and delivery latency but cannot make completed-M15 structural evidence arrive before the candle itself is complete.
