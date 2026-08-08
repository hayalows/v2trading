# V2 Research Lab v1.0 — Product and UX Overhaul

## Goal

Turn the research prototype into a coherent version-one product that helps a user answer four questions quickly:

1. What deserves attention now?
2. Why does it matter?
3. What changed?
4. What should I investigate next?

The release does not change the execution-truth gate. It improves how the existing prospective research is presented and used.

## Design research

### Material Design 3 / M3 Expressive

Official Material 3 guidance: https://m3.material.io/

Applied ideas:
- adaptive layouts rather than a one-size desktop canvas
- stronger hierarchy and flexible typography
- expressive components used selectively for usability, not decoration
- role-based color tokens instead of one-off colors
- consistent enabled, hover, focus and pressed states
- progressive disclosure for advanced quant details

### Material adaptive canonical layouts

Reference: https://m3.material.io/foundations/layout/canonical-examples/overview

The app now behaves like a supporting-pane/list-detail research product:
- compact: bottom navigation + single-column content
- medium: denser multi-column metric layouts
- expanded: persistent navigation rail + primary/supporting content panes

### Google accessibility guidance

Reference: https://developer.android.com/guide/topics/ui/accessibility/apps.html

Implemented:
- minimum 48px interactive targets
- visible keyboard focus states
- semantic navigation labels
- non-color labels for market/attention state
- reduced-motion support
- readable body-copy sizes and contrast-oriented Material color roles

## Information architecture

### Overview

Primary product surface. Shows:
- attention level
- current research headline
- reasons
- next structural checkpoint
- last meaningful change
- formation, context, regime and data status
- timeframe trend summary

### Chart

TradingView remains a first-class destination and is one tap away from the primary brief. It is framed as a verification surface, not as the product's only source of meaning.

### Research

Shows:
- prospective observation count
- meaningful transition count
- Stage-6 arrivals
- suppressed low-signal Stage 0↔1 flicker
- meaningful transition timeline
- historical causal-validation evidence

### Data trust

Separates:
- public reference price
- public structural candle data
- unavailable broker execution truth

Includes a glossary for stage, context fit, shift risk and directional efficiency.

## Copy strategy

The primary layer translates quant language into decisions about attention.

Examples:
- `supportive` → “Higher timeframes support this direction”
- `conflicting` → “Higher timeframes lean the other way”
- `volatility expansion` → “Volatility is expanding”
- `elevated shift risk` → “Market movement is unusually active”

Technical terms remain available in advanced details and the glossary.

## Visual system

The static web implementation now uses Material-style role tokens:
- primary / on-primary
- primary-container / on-primary-container
- secondary-container
- surface-container hierarchy
- outline / outline-variant
- error roles

Typography uses a Material-like scale:
- display: 32–44px responsive
- headline: 24–28px
- title: 16–22px
- body: 14–16px
- labels: 12–14px

Rounded Material Symbols are used for navigation and action affordances.

## Interaction model

### Compact screens

Bottom navigation keeps Overview, Chart, Research and Data within thumb reach.

### Expanded screens

A navigation rail replaces the bottom bar and the overview uses a primary research card plus a supporting pane.

### Primary CTA

The CTA adapts to research state:
- Background → Open chart
- Watchlist → Watch on chart
- Review now → Review on chart
- Location → Inspect location
- Market closed → Review last session

The CTA never becomes “Buy” or “Sell.”

## Accessibility and interaction safeguards

- all primary interactive controls have at least 48px target size
- `:focus-visible` state is explicit
- active navigation has icon fill + container change, not color alone
- `prefers-reduced-motion` disables nonessential transitions/animation
- aria labels identify primary navigation and refresh action
- selected pair uses `aria-pressed`

## What did not change

v1.0 is a product/experience release, not a profitability-model release.

Still blocked:
- broker-specific bid/ask execution truth
- trustworthy live spread/slippage simulation
- validated Stage-6 win probability
- automated real-money recommendations

## Version-one product principle

The product should feel useful even before predictive modelling is justified.

Its job is currently:

> Continuously observe EURUSD and GBPUSD, identify V2-like structural development, summarize higher-timeframe and regime context, preserve point-in-time research history, and guide the user toward the evidence that deserves inspection.

That is the foundation for future episode-outcome analytics and eventually a research agent, once the prospective sample becomes large enough.
