import numpy as np
import pandas as pd

from v2trading.live_diagnostics import (
    efficiency_ratio,
    formation_context,
    normalized_atr_percentile,
    shift_diagnostic,
    weighted_trend_alignment,
)


def _bars(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({
        "close": close,
        "high": close * 1.001,
        "low": close * 0.999,
    })


def test_efficiency_ratio_distinguishes_direction_from_chop():
    directional = np.linspace(1.0, 2.0, 40)
    choppy = 1.0 + np.tile([0.01, -0.01], 20).cumsum()
    assert efficiency_ratio(directional, 20) > 0.99
    assert efficiency_ratio(choppy, 20) < 0.15


def test_volatility_percentile_is_bounded():
    close = np.linspace(1.0, 1.2, 160)
    value = normalized_atr_percentile(_bars(close))
    assert 0.0 <= value <= 100.0


def test_weighted_alignment_and_context_are_descriptive():
    labels = {"d1": "bullish", "h4": "bullish", "h1": "bullish", "m15": "bearish"}
    direction, alignment = weighted_trend_alignment(labels)
    assert direction == "bullish"
    assert alignment >= 55
    assert formation_context("long", labels) == "supportive"
    assert formation_context("short", labels) == "conflicting"


def test_balanced_alignment_is_mixed_context_not_false_confluence():
    labels = {"d1": "bullish", "h4": "bullish", "h1": "bearish", "m15": "bearish"}
    direction, alignment = weighted_trend_alignment(labels)
    assert direction == "bullish"
    assert alignment < 55
    assert formation_context("long", labels) == "mixed"
    assert formation_context("short", labels) == "mixed"


def test_shift_diagnostic_is_causal_and_bounded():
    calm = np.exp(np.linspace(0, 0.01, 80))
    shocked = calm.copy()
    shocked[-8:] *= np.exp(np.linspace(0, 0.08, 8))
    a = shift_diagnostic(calm)
    b = shift_diagnostic(shocked)
    assert 0 <= a.score <= 100
    assert 0 <= b.score <= 100
    assert b.score >= a.score
