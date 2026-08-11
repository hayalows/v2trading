# EURUSD feed incident — 2026-08-11

## Scope

Research-only V2 EURUSD market-state pipeline. No live-money execution is enabled.

## What was observed

EURUSD produced multiple Stage 3/4 campaigns but no paper plan. Candle-by-candle review showed that the audited campaigns genuinely failed BOS; the paper-plan engine was therefore correct not to arm them.

A separate upstream market-data defect was then identified in Yahoo `EURUSD=X` intraday bars:

- recent 94 M15 EURUSD bars had only 14 distinct closes versus 62 for GBPUSD;
- the minimum/typical EURUSD close step was about 0.000133, roughly 1.33 pips;
- 100% of the tested EURUSD closes were nearly exact reciprocals of Yahoo's four-decimal USD/EUR series;
- Yahoo 5m EURUSD showed the same quantization;
- during the Aug 10 rollover, Yahoo also returned a stale EURUSD M15 window eight bars behind, which allowed an old sweep to reappear because data health was observational rather than a hard veto.

## Corrected architecture

### Canonical EURUSD M15/5m

1. **Dukascopy BID ticks** are the preferred historical intraday source when their recent overlap agrees with the independent Twelve Data series.
2. **Twelve Data EUR/USD 15m, UTC** is a historical failover source. It is no longer necessary to keep EURUSD online by trusting Yahoo if Dukascopy is temporarily unavailable.
3. **Twelve Data EUR/USD 1m, UTC** supplies the current completed-minute tail and the canonical 5m path.
4. Twelve 1m is aggregated only when all expected component minutes are present:
   - 5 rows for a completed 5m candle;
   - 15 rows for a completed M15 candle.
5. Twelve's direct 15m feed is checked against independently fetched/aggregated Twelve 1m data. In the production failover test, 11 complete overlapping M15 bars matched exactly.
6. Dukascopy wins on overlap only while its cross-provider seam passes. Current gate:
   - at least 2 recent overlapping M15 bars;
   - maximum OHLC difference <= 2.0 pips;
   - median close difference <= 1.0 pip.
7. If Dukascopy is unavailable or its seam fails, Twelve direct 15m becomes the historical base automatically while the stricter Twelve 1m-versus-15m consistency gate remains mandatory.
8. Only one canonical series is exposed downstream as `EURUSD canonical structure v1`.

The outage path was exercised during the incident: Dukascopy returned HTTP 503 for recent hourly files, while Twelve Data continued serving 1m and 15m EUR/USD. Twelve's 200-bar 15m sample had 144 unique closes, a 0.00001 minimum non-zero step, and no recurrence of the Yahoo quantization pattern.

## Raw-provider resilience

`dukascopy-raw-sync` stores provider-native data separately from canonical downstream bars.

- normal refresh fetches recent completed hours;
- if the raw store is below the minimum history threshold, the job self-bootstraps a longer history window;
- each hourly fetch has a bounded timeout;
- slow/503 hours are skipped and retried later rather than blocking the canonical state refresh;
- diagnostic bootstrap/probe endpoints used during investigation were retired after cutover.

This means a raw-provider outage does not overwrite the canonical series or silently fall back to Yahoo.

## Fail-closed gates

A EURUSD formation is withheld as `DATA_DEGRADED` when any of these conditions fail:

- current completed M15 lag = 0;
- no recent M15 gaps;
- no duplicate bars;
- no suspicious quantization;
- Twelve 1m/15m consistency gate passes;
- canonical updater is fresh.

Database triggers provide defense in depth:

- deprecated Yahoo EURUSD M15 bars are blocked after the cutover;
- deprecated EURUSD current-state writes cannot overwrite a canonical state;
- unhealthy/deprecated EURUSD history rows are rejected before campaign processing;
- new EURUSD paper plans require a fresh healthy canonical state;
- source-blocked plans cannot contribute prospective POI-depth evidence;
- any legacy Yahoo EURUSD 5m same-bar resolution is censored before it can count as a win/loss.

A separate canonical 5m verifier reconstructs censored same-bar cases from the canonical EURUSD 5m path.

## UI cutover

The browser previously fetched `market-lab?symbol=EURUSD,GBPUSD`, which meant the legacy endpoint could still return a Yahoo-derived EURUSD object directly even after the database rejected its write.

The UI now fetches:

- EURUSD from `eurusd-market-lab`;
- GBPUSD from the legacy GBPUSD-only `market-lab` path.

Therefore both persistence and display consume the canonical EURUSD state.

## Schedule

- minute 0/5/10/...: EURUSD feed watchdog;
- minute 1/6/11/...: canonical EURUSD state refresh;
- minute 2/7/12/...: paper-trade engine;
- minute 3/8/13/...: shadow arena;
- minute 4/9/14/...: canonical EURUSD 5m verifier;
- minute 7 each hour: Dukascopy raw-hour refresh.

The legacy `market-lab` schedule now refreshes GBPUSD only.

## Production validation

A successful canonical failover-capable refresh at 18:56 UTC reported:

- expected completed M15: 18:30 UTC;
- last M15: 18:30 UTC;
- structure lag: 0;
- recent gaps: 0;
- duplicates: 0;
- 68 unique closes in the latest 96 M15 bars;
- minimum non-zero close step: approximately 0.00001 (0.1 pip);
- Twelve 1m-versus-direct-15m seam: exact match in the recent complete overlap;
- Dukascopy-versus-Twelve recent seam: pass;
- max OHLC cross-provider difference: about 1.2 pips;
- median close difference: about 0.3 pips.

The corrected feed still returned `NO_SETUP`, which is important: the remediation fixed market-data fidelity and safeguards; it did not loosen formation or BOS rules to manufacture trades.

## Research boundary

This remains a research market-state and paper-trade system. The canonical feed is not broker execution truth and does not provide executable broker spread, latency, slippage, or fill validation.
