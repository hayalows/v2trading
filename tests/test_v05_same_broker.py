from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v05_same_broker_relabel import SameBrokerStore, Trade, load_ledger, quality, relabel_m1, relabel_ticks

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


def test_load_ledger_accepts_common_aliases_and_infers_2p5r_target(tmp_path):
    p = tmp_path / "ledger.csv"
    pd.DataFrame({
        "trade_id": ["A"],
        "ticker": ["EURUSD"],
        "side": ["buy"],
        "open_time": ["2025-01-02T10:00:00Z"],
        "open_price": [1.1000],
        "sl": [1.0990],
        "realized_r": [2.5],
    }).to_csv(p, index=False)
    got = load_ledger(p)
    assert len(got) == 1
    assert got.loc[0, "direction"] == "long"
    assert abs(got.loc[0, "target"] - 1.1025) < 1e-9
    assert got.loc[0, "source_outcome"] == "win"


def test_store_reads_daily_tick_partitions_without_timezone_reinterpretation(tmp_path):
    root = tmp_path / "export"
    (root / "EURUSD" / "ticks" / "date=2025-01-02").mkdir(parents=True)
    (root / "EURUSD" / "bars").mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({
        "symbols": {"EURUSD": {"metadata": {"point": 0.0001}}},
        "files": [],
    }))
    ticks = pd.DataFrame({
        "time": pd.to_datetime(["2025-01-02 09:59:59Z", "2025-01-02 10:00:01Z"]),
        "bid": [1.0999, 1.1000], "ask": [1.1001, 1.1002],
    })
    ticks.to_parquet(root / "EURUSD" / "ticks" / "date=2025-01-02" / "ticks.parquet", index=False)
    store = SameBrokerStore(root)
    got = store.ticks_for_window("EURUSD", pd.Timestamp("2025-01-02 10:00:00Z"), pd.Timestamp("2025-01-02 10:01:00Z"))
    assert len(got) == 1
    assert got.iloc[0].time == pd.Timestamp("2025-01-02 10:00:01Z")
