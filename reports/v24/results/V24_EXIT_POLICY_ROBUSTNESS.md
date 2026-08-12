# V2 v2.4 Exit Policy Robustness Note

**Status: post-result diagnostic. No rule promotion.**

The frozen v2.4 run exposed large policy-dependent M5 ordering ambiguity, especially for early break-even triggers. Comparing only resolved rows would bias the ranking because difficult paths disappear at different rates for different policies.

This diagnostic therefore scores every common 2022-2025 policy row under three explicit assumptions for unresolved M5 paths: pessimistic = -1R, neutral = 0R, optimistic = +2.5R. The neutral case is the primary sensitivity view. Existing V2 spread/slippage approximations are also shown separately as a cost stress.

## Neutral ambiguity comparison

| Policy | Ambiguity | Gross mean R | Cost-stressed mean R | $500 cost-stressed equity |
|---|---:|---:|---:|---:|
| hold_sltp | 12.7% | +0.2353 | -0.1769 | $19.21 |
| timeout_96 | 12.7% | +0.2344 | -0.1778 | $18.93 |
| timeout_192 | 12.7% | +0.2305 | -0.1817 | $17.71 |
| timeout_48 | 12.7% | +0.2275 | -0.1847 | $16.90 |
| be_075 | 58.2% | +0.2090 | -0.2032 | $13.83 |
| be_100 | 47.1% | +0.1875 | -0.2247 | $9.36 |
| be_150 | 30.1% | +0.1787 | -0.2335 | $7.73 |
| be_125 | 38.1% | +0.1714 | -0.2408 | $6.97 |
| p25_150_be | 30.1% | +0.1535 | -0.2868 | $3.17 |
| p25_100_be | 47.1% | +0.1488 | -0.2885 | $3.21 |
| p33_150_be | 30.1% | +0.1454 | -0.3039 | $2.38 |
| p33_100_be | 47.1% | +0.1364 | -0.3089 | $2.28 |
| p50_150_be | 30.1% | +0.1283 | -0.3402 | $1.29 |
| p50_100_be | 47.1% | +0.1101 | -0.3523 | $1.09 |

## What survives the stress test

- Hold-to-SL/TP: +0.2353R neutral structural mean.
- 96-bar timeout: +0.2344R, effectively tied with hold in this structural proxy.
- Current 48-bar timeout: +0.2275R, slightly lower than hold by +0.0077R per setup.
- +0.75R break-even: +0.2090R neutral structural mean, but 58.2% of rows require unresolved intrabar ordering. Its resolved-row headline is therefore not reliable enough for promotion.
- Partial-profit variants do not beat hold or the 96-bar timeout in the neutral all-row structural comparison.

## Decision

**NO_EXIT_POLICY_PROMOTION.** Keep the current paper engine frozen. Run hold-to-SL/TP, 96-bar timeout, break-even and partial-profit rules prospectively in shadow mode. Give priority to obtaining finer path data for the break-even candidates.

The cost-stressed means are negative for every policy in this public-data proxy. That reinforces the existing v0.4 boundary: exit tuning cannot rescue unvalidated execution labels.
