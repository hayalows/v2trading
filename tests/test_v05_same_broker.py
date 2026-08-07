from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v05_same_broker_relabel import Trade, quality, relabel_m1, relabel_ticks

UTC = "UTC"


def trade(direction: str = "long") -> Trade:
    if direction == "long":
        return Trade("T1", "EURUSD", "long", pd.Timestamp("2025-01-02 10:00:00", tz=UTC), 1.1000, 1.0990, 1.1025, "win", 2.5)
    return Trade("T2", "EURUSD", "short", pd.Timestamp("2025-01-02 10:00:00", tz=UTC), 1.1000, 1.1010, 1.0975, "loss", -1.0)


def test_tick_long_uses_ask_for_entry_and_bid_for_target():
    t = trade("long")
    ticks = pd.DataFrame({
        "time": pd.to_datetime(["2025-01-02 10:00:00Z", "2025-01-02 10:00:01Z", "2025-01-02 10:00:02Z"]),
        "bid": [1.0998, 1.0999, 1.1025],
        "ask": [1.1001, 1.1002, 1.1027],
    })
    # Bid touching the limit is insufficient for a buy: the ask must reach it.
    out = relabel_ticks(t, ticks)
    assert out["execution_outcome"] == "no_fill"

    ticks.loc[1, "ask"] = 1.1000
    ticks.loc[1, "bid"] = 1.0998
    out = relabel_ticks(t, ticks)
    assert out["execution_outcome"] == "win"
    assert out["filled"] == 1
    assert out["fill_time"] == ticks.loc[1, "time"]
    assert out["execution_r"] >= 2.49


def test_tick_short_stop_uses_ask_and_captures_slippage():
    t = trade("short")
    ticks = pd.DataFrame({
        "time": pd.to_datetime(["2025-01-02 10:00:00Z", "2025-01-02 10:00:01Z", "2025-01-02 10:00:02Z"]),
        "bid": [1.1000, 1.1006, 1.1010],
        "ask": [1.1002, 1.1008, 1.1013],
    })
    out = relabel_ticks(t, ticks)
    assert out["execution_outcome"] == "loss"
    assert out["stop_slippage_r"] > 0
    assert out["execution_r"] < -1.0


def test_m1_same_bar_stop_and_target_is_retained_as_ambiguous():
    t = trade("long")
    m1 = pd.DataFrame({
        "time": pd.to_datetime(["2025-01-02 10:00:00Z", "2025-01-02 10:01:00Z"]),
        "open": [1.1001, 1.1000],
        "high": [1.1004, 1.1030],
        "low": [1.0998, 1.0988],
        "close": [1.1000, 1.1005],
        "spread": [1, 1],
    })
    out = relabel_m1(t, m1, point=0.0001)
    assert out["execution_outcome"].startswith("ambiguous")


def test_quality_requires_low_spread_and_slippage_for_trusted_tick():
    good = {"label_source": "tick_direct", "execution_outcome": "win", "fill_spread_r": 0.10, "stop_slippage_r": 0.0}
    bad = {"label_source": "tick_direct", "execution_outcome": "loss", "fill_spread_r": 0.30, "stop_slippage_r": 0.0}
    assert quality(good) == "trusted_tick"
    assert quality(bad) == "tick_high_friction"
