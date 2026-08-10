from __future__ import annotations

"""Rerun v1.4 waiting-time research with the exact live POI geometry.

The original public proxy defines a narrower directional POI sub-zone. The live
market scanner uses the entire last-opposite M15 candle [low, high]. This runner
patches only the POI zone geometry while keeping sweep, BOS, stop buffer, risk
filter, target, outcome resolution and waiting-time analysis unchanged.
"""

import v14_poi_waiting_time_study as study

study.HORIZONS = [8, 12, 16, 24, 32, 48, 72, 96, 144, 192]
study.MAX_FOLLOW = max(study.HORIZONS)

_original_find_poi = study.proxy.find_poi


def live_full_candle_poi(df, sweep_i: int, bos_i: int, direction: str):
    found = _original_find_poi(df, sweep_i, bos_i, direction)
    if found is None:
        return None
    poi_i, _old_low, _old_high = found
    return poi_i, float(df.at[poi_i, "low"]), float(df.at[poi_i, "high"])


study.proxy.find_poi = live_full_candle_poi

if __name__ == "__main__":
    study.main()
