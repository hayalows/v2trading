from __future__ import annotations

import pandas as pd

LEAKAGE_COLUMNS = {
    "exit_time", "exit_reason", "gross_r", "net_r", "holding_time_minutes",
    "bars_held", "m15_mfe_r", "m15_mae_r",
    "post_exit_continuation_24h_r", "post_exit_continued_24h",
    "post_exit_continuation_48h_r", "post_exit_continued_48h",
    "post_exit_continuation_72h_r", "post_exit_continued_72h",
    "post_exit_continuation_5td_r", "post_exit_continued_5td",
    "m15_v2_setup_score",
}

BASE_FEATURES = [
    "symbol", "direction", "risk_distance_points", "spread_as_r", "bars_to_entry",
    "entry_hour", "entry_dow", "sweep_to_bos_min", "bos_to_poi_min", "poi_to_entry_min",
]

HTF_FEATURES = [
    "dominant_bias", "intraday_context_score", "runner_context_score",
    "trend_alignment_score", "location_quality_score", "target_room_score",
    "runner_potential_score", "final_htf_belief_score", "final_context_label",
    "monthly_context_score", "weekly_context_score", "daily_context_score",
    "market_regime", "d1_h4_agreement", "w1_mn1_agreement", "trend_alignment",
    "location_bucket", "runner_room_bucket", "htf_alignment_bucket",
]
for _tf in ["mn1", "w1", "d1", "h4", "h1"]:
    HTF_FEATURES.extend([
        f"{_tf}_candle_count", f"{_tf}_regime", f"{_tf}_bias", f"{_tf}_structure_state",
        f"{_tf}_range_position", f"{_tf}_premium_discount", f"{_tf}_target_blocked",
        f"{_tf}_open_room_beyond_tp", f"{_tf}_context_score",
    ])


def prepare_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """Create only features that are knowable by entry time."""
    out = df.copy()
    for col in ["sweep_time", "bos_time", "poi_time", "entry_time", "exit_time"]:
        if col in out:
            out[col] = pd.to_datetime(out[col], utc=True, errors="coerce")
    out["win"] = (out["net_r"] > 0).astype(int)
    out["entry_hour"] = out["entry_time"].dt.hour
    out["entry_dow"] = out["entry_time"].dt.dayofweek
    out["sweep_to_bos_min"] = (out["bos_time"] - out["sweep_time"]).dt.total_seconds() / 60
    out["bos_to_poi_min"] = (out["poi_time"] - out["bos_time"]).dt.total_seconds() / 60
    out["poi_to_entry_min"] = (out["entry_time"] - out["poi_time"]).dt.total_seconds() / 60
    return out


def assert_no_leakage(features: list[str]) -> None:
    bad = sorted(set(features) & LEAKAGE_COLUMNS)
    if bad:
        raise ValueError(f"Leaky features detected: {bad}")
