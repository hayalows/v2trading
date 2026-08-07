# V2 Quant v0.6 — Prospective Detector Validation

## Question

Can the live V2 Research Lab identify a developing EURUSD or GBPUSD setup **before** the research entry zone is reached, using only information available at each completed M15 candle?

This test does **not** ask whether the eventual trade is profitable. It tests formation detection and warning lead time only.

## Scope

- Core markets: EURUSD and GBPUSD
- Public M15 history: NatoG93/market-data
- Replay start: 2023-01-01
- Replay bars: 154,665 completed M15 bars
- Future bars hidden at every replay step
- Live-equivalent state machine: stages 0–8
- Causal lookback: 120 bars, wider than every live detector dependency
- Independent benchmark: frozen public V2 proxy engine in `scripts/public_data_v2_proxy.py`

## Independent proxy-entry recall

The strongest test uses **279 independently generated V2 proxy entries** and asks whether the live state machine had already emitted the same-direction developing state before each entry.

| Detector state reached before proxy entry | Recall | Entries caught | Median lead time |
|---|---:|---:|---:|
| Stage 3+ — sweep/development | 100.0% | 279 / 279 | 360 min |
| Stage 4+ — sweep confirmed / waiting BOS | 98.9% | 276 / 279 | 345 min |
| Stage 5+ — BOS confirmed | 82.1% | 229 / 279 | 60 min |
| Stage 6+ — fresh POI | 71.3% | 199 / 279 | 60 min |
| Stage 7 — approaching POI | 2.5% | 7 / 279 | 15 min |

### EURUSD

- Proxy entries: 128
- Stage 3 recall: 100.0%, median lead 367.5 min
- Stage 4 recall: 97.7%, median lead 360 min
- Stage 5 recall: 82.8%, median lead 60 min
- Stage 6 recall: 68.0%, median lead 60 min
- Stage 7 recall: 3.9%, median lead 15 min

### GBPUSD

- Proxy entries: 151
- Stage 3 recall: 100.0%, median lead 345 min
- Stage 4 recall: 100.0%, median lead 330 min
- Stage 5 recall: 81.5%, median lead 60 min
- Stage 6 recall: 74.2%, median lead 60 min
- Stage 7 recall: 1.3%, median lead 15 min

## Important counter-result: early stages are noisy

A second replay followed every same-direction Stage 3+ episode and asked whether it reached the lab's own Stage 8 within the next 32 M15 bars (8 hours).

Across EURUSD and GBPUSD:

- Candidate Stage 3+ episodes: 4,272
- Episodes reaching Stage 8 within 8 hours: 225
- Conversion rate: 5.27%

By market, broad Stage 3 conversion was about 5.1% for EURUSD and 5.5% for GBPUSD. Stage 5 and Stage 6 episodes converted more often, but the sample becomes much smaller.

This means **Stage 3 is sensitive but not selective**. It is useful for creating a watchlist, not for calling a trade.

## Interpretation

### What v0.6 supports

The live detector can identify the structural development that precedes the separately generated V2 proxy entry. In this historical causal replay, every independent proxy entry had a same-direction Stage 3 warning beforehand, almost every one had Stage 4 beforehand, and roughly 7 in 10 had already reached the fresh-POI Stage 6 about an hour before entry.

### What v0.6 does not support

It does not show that a Stage 3, Stage 5, Stage 6, or Stage 8 condition is profitable. It does not solve broker execution, spread, slippage, or stop/target sequencing. v0.4 still showed that the historical candle labels are not reliable enough to promote the system to live buy/sell signals.

### UX consequence

The lab should interpret stages as:

- **0–2: No focus / early context**
- **3–4: Watchlist** — useful early warning, but most sequences die
- **5: Structure confirmed** — BOS exists; review the chart
- **6: Mature setup structure** — BOS + fresh POI; this is the strongest practical review state currently supported
- **7: Proximity flag** — useful when it appears, but it is not required and had very low recall against the independent proxy entries
- **8: Research entry-zone event** — record and study; not a trade signal

## Product decision

The automatic live lab is narrowed to EURUSD and GBPUSD. XAUUSD remains an experimental branch because the zero-cost stack mixes a spot reference with a COMEX futures structure proxy. US30 is paused. This reduces data-source ambiguity and makes the prospective research dataset more coherent.

## Current verdict

**Formation detection gate: PASS for research use.**

The detector has demonstrated that it can surface V2-like developing structures before independent proxy entries in strict historical candle-by-candle replay.

**Trading-signal gate: FAIL / not earned.**

The system should continue to be used as a market-structure and setup-discovery research lab, not as an automated buy/sell engine.
