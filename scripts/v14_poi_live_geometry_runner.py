from __future__ import annotations

"""Run the v1.4 POI waiting-time study with exact live-scanner POI geometry.

The older public V2 proxy intentionally defines a directional POI sub-zone:
- long: [candle low, candle open]
- short: [candle open, candle high]

The live Stage-6 scanner and paper engine instead use the full high-low range of
the last opposite M15 candle between sweep and BOS.  v1.4 lifecycle research must
therefore patch only POI geometry before invoking the frozen waiting-time study.
No sweep, BOS, ATR, risk, target, outcome, cost, or waiting-horizon rules change.
"""

import pandas as pd

import public_data_v2_proxy as proxy
import v14_poi_waiting_time_study as study


def find_live_poi(
    df: pd.DataFrame,
    sweep_i: int,
    bos_i: int,
    direction: str,
) -> tuple[int, float, float] | None:
    """Last opposite candle from sweep through BOS; use its full low-high range."""
    segment = df.iloc[sweep_i : bos_i + 1]
    if direction == "long":
        opposite = segment[segment["close"] < segment["open"]]
    else:
        opposite = segment[segment["close"] > segment["open"]]
    if opposite.empty:
        return None
    idx = int(opposite.index[-1])
    return idx, float(df.at[idx, "low"]), float(df.at[idx, "high"])


def main() -> None:
    proxy.find_poi = find_live_poi
    study.proxy.find_poi = find_live_poi
    study.main()


if __name__ == "__main__":
    main()
