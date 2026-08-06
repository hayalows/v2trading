# Research data policy

Raw broker/history files and the recovered enriched trade ledger are intentionally not committed to this public repository.

Reasons:

- broker/vendor historical-data licensing can differ by source;
- the recovered ledger exposes detailed strategy research fields;
- large raw files should remain immutable inputs rather than Git-edited artifacts.

## Recovered ledger used for v0.1

Expected filename:

`FULL_2020_2026_HTF_ENRICHED_TRADE_LEDGER.csv`

Observed rows: `2,227`

Observed columns before derived entry-time fields: `132`

SHA-256:

`6609a7ab93ee710504027f9b559e5d00155d5101e66e58971843d9639205a4ac`

This hash lets a future run verify that it is using the exact same recovered research input.

## New raw data

Use `scripts/mt5_export.py` on the Windows machine with MT5 to export broker M1/M15 data. Keep source, symbol mapping, timezone, retrieval date, spread/bid-ask convention and any gaps in a local data manifest.

Independent tick/bid-ask validation should use a separately licensed/source-appropriate dataset such as Dukascopy and should not be mixed silently with the broker feed.
