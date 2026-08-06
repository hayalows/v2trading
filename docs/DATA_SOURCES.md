# Data Sources and Research Use

## Price / candles

### MetaTrader 5 Python integration
Use the local MT5 terminal to export the broker's own M1/M15 bars with `copy_rates_range`. This should be the primary reproduction source because the old Strategy Lab was connected to MT5.

### Dukascopy historical data
Use as an independent robustness source. Dukascopy provides bars and tick history and its historical-data export supports Forex, commodities and indices. Tick history includes bid/ask information, which is useful for fill and intrabar validation.

## Macro

### FRED / ALFRED
FRED provides official economic/financial time series. ALFRED/vintage data is preferred when revisions would otherwise create look-ahead bias. Daily end-of-day fields must be lagged for intraday prediction.

Candidate series families include Treasury yields, real yields, volatility/risk measures, oil, credit and exchange-rate proxies. Exact IDs should be frozen in a data manifest before the historical macro experiment begins.

## News

### GDELT
Use DOC 2.0 for recent/shadow monitoring and article/timeline queries. Use bulk GDELT Event/GKG archives for a reproducible historical news panel. Store query definitions and retrieval dates.

### Financial NLP
FinBERT is a useful baseline for finance-language sentiment but sentiment must be transformed into asset-specific impact/relevance. A "hawkish Fed" headline can be positive for USD and negative for gold, so generic sentiment is not enough.

## Foundation models

### Kronos
Open-source financial candlestick foundation model trained on a very large multi-market K-line corpus. Candidate use: forecast/path/volatility features, never assumed profitability.

### Chronos-family models
Candidate use: probabilistic forecasts and covariate-aware time-series features. Must be benchmarked against simple models and price-only baselines.

## Research references

- MQL5 Python `copy_rates_range` documentation
- Dukascopy Historical Data / IHistory documentation
- GDELT DOC 2.0 API documentation
- FRED series observations documentation
- Shi et al., *Kronos: A Foundation Model for the Language of Financial Markets* (2025; AAAI 2026)
- Araci, *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models* (2019)
- *The impact of monetary surprises on exchange rates: Results from textual and high-frequency analysis*, Journal of International Money and Finance (2025)
- World Gold Council, *Gold Outlook 2026*
