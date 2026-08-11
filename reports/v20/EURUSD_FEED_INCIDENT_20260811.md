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

1. **Dukascopy BID ticks** are the authoritative historical intraday source.
2. **Twelve Data EUR/USD 1m, UTC** fills the still-unpublished current Dukascopy hour.
3. Twelve 1m is aggregated only when all expected component minutes are present:
   - 5 rows for a completed 5m candle;
   - 15 rows for a completed M15 candle.
4. Dukascopy wins on overlap.
5. Provider overlap is continuously audited. Current gate:
   - at least 2 recent overlapping M15 bars;
   - maximum OHLC difference <= 2.0 pips;
   - median close difference <= 1.0 pip.
6. Only one canonical series is exposed downstream as `EURUSD canonical structure v1`.

## Fail-closed gates

A EURUSD formation is withheld as `DATA_DEGRADED` when any of these conditions fail:

- current completed M15 lag = 0;
- no recent M15 gaps;
- no duplicate bars;
- no suspicious quantization;
- provider seam passes;
- canonical updater is fresh.

Database triggers provide defense in depth:

- deprecated Yahoo EURUSD M15 bars are blocked after the cutover;
- deprecated EURUSD current-state writes cannot overwrite a canonical state;
- unhealthy/deprecated EURUSD history rows are rejected before campaign processing;
- new EURUSD paper plans require a fresh healthy canonical state;
- source-blocked plans cannot contribute prospective POI-depth evidence;
- any legacy Yahoo EURUSD 5m same-bar resolution is censored before it can count as a win/loss.

A separate canonical 5m verifier reconstructs censored same-bar cases from the canonical EURUSD 5m path.

## Schedule

- minute 0/5/10/...: EURUSD feed watchdog;
- minute 1/6/11/...: canonical EURUSD state refresh;
- minute 2/7/12/...: paper-trade engine;
- minute 3/8/13/...: shadow arena;
- minute 4/9/14/...: canonical EURUSD 5m verifier;
- minute 7 each hour: Dukascopy raw-hour refresh.

The legacy `market-lab` schedule now refreshes GBPUSD only.

## Production validation at cutover

A successful canonical refresh around 18:33 UTC reported:

- expected completed M15: 18:15 UTC;
- last M15: 18:15 UTC;
- structure lag: 0;
- recent gaps: 0;
- duplicates: 0;
- 68 unique closes in the latest 96 M15 bars;
- minimum non-zero close step: approximately 0.00001 (0.1 pip);
- provider seam: pass;
- recent overlap bars: 8;
- max OHLC provider difference: about 1.2 pips;
- median close difference: about 0.3 pips.

The corrected feed still returned `NO_SETUP`, which is important: the remediation fixed market-data fidelity and safeguards; it did not loosen formation or BOS rules to manufacture trades.

## Research boundary

This remains a research market-state and paper-trade system. The canonical feed is not broker execution truth and does not provide executable bid/ask, spread, latency, or slippage validation.
