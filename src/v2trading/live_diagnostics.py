"""Causal market-state diagnostics used by V2 Research Lab v0.7.

These functions deliberately describe context rather than predict P(win). Every
calculation is backward-looking and can be reproduced offline against the live
Edge Function implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ShiftDiagnostic:
    risk: str
    score: float
    volatility_ratio: float
    return_shock: float


def efficiency_ratio(close: Iterable[float], period: int = 20) -> float:
    """Kaufman-style directional efficiency in [0, 1]."""
    x = np.asarray(list(close), dtype=float)
    if period <= 0 or x.size <= period:
        return 0.0
    window = x[-(period + 1) :]
    path = np.abs(np.diff(window)).sum()
    if not np.isfinite(path) or path <= 0:
        return 0.0
    return float(np.clip(abs(window[-1] - window[0]) / path, 0.0, 1.0))


def true_range(frame: pd.DataFrame) -> pd.Series:
    h = pd.to_numeric(frame["high"], errors="coerce")
    l = pd.to_numeric(frame["low"], errors="coerce")
    c = pd.to_numeric(frame["close"], errors="coerce")
    prev = c.shift(1)
    return pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)


def normalized_atr_percentile(
    frame: pd.DataFrame, atr_period: int = 14, lookback: int = 120
) -> float:
    """Percentile rank of current ATR/price versus its trailing history."""
    if len(frame) < max(atr_period + 2, 20):
        return 0.0
    close = pd.to_numeric(frame["close"], errors="coerce")
    atr = true_range(frame).rolling(atr_period, min_periods=atr_period).mean()
    normalized = atr / close.abs().clip(lower=1e-12)
    hist = normalized.dropna().iloc[-lookback:]
    if hist.empty:
        return 0.0
    current = float(hist.iloc[-1])
    return float(100.0 * (hist <= current).mean())


def weighted_trend_alignment(labels: Mapping[str, str]) -> tuple[str, float]:
    """Return dominant direction and absolute weighted agreement percentage."""
    weights = {"d1": 3, "h4": 3, "h1": 2, "m15": 1}
    signed = 0.0
    active = 0.0
    for tf, weight in weights.items():
        label = str(labels.get(tf, "mixed")).lower()
        if label == "bullish":
            signed += weight
            active += weight
        elif label == "bearish":
            signed -= weight
            active += weight
    alignment = 0.0 if active == 0 else 100.0 * abs(signed) / active
    direction = "bullish" if signed >= 3 else "bearish" if signed <= -3 else "mixed"
    return direction, float(alignment)


def formation_context(
    formation_direction: str | None, trend_labels: Mapping[str, str]
) -> str:
    dominant, alignment = weighted_trend_alignment(trend_labels)
    expected = "bullish" if formation_direction == "long" else "bearish" if formation_direction == "short" else None
    if expected is None:
        return "neutral"
    if dominant == expected and alignment >= 55:
        return "supportive"
    if dominant not in {"mixed", expected} and alignment >= 55:
        return "conflicting"
    return "mixed"


def shift_diagnostic(close: Iterable[float]) -> ShiftDiagnostic:
    """Simple causal change-pressure diagnostic inspired by stream drift monitoring.

    It intentionally does not fit an HMM or claim a latent regime probability.
    """
    x = np.asarray(list(close), dtype=float)
    if x.size < 52 or np.any(x <= 0):
        return ShiftDiagnostic("unknown", 0.0, 1.0, 0.0)
    r = np.diff(np.log(x))
    recent_vol = float(np.std(r[-8:], ddof=0))
    baseline_vol = float(np.std(r[-50:], ddof=0))
    vol_ratio = recent_vol / baseline_vol if baseline_vol > 0 else 1.0
    move = abs(float(np.log(x[-1] / x[-9])))
    expected = baseline_vol * np.sqrt(8) if baseline_vol > 0 else 1e-12
    return_shock = move / expected
    raw = max(0.0, vol_ratio - 1.0) / 0.8 * 0.55 + max(0.0, return_shock - 1.0) / 2.0 * 0.45
    score = float(np.clip(raw * 100.0, 0.0, 100.0))
    risk = "high" if score >= 70 else "elevated" if score >= 40 else "stable"
    return ShiftDiagnostic(risk, score, float(vol_ratio), float(return_shock))
