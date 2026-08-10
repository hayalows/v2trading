from __future__ import annotations

"""Rerun v1.4 waiting-time research with the exact live POI geometry.

The original public proxy defines a narrower directional POI sub-zone. The live
market scanner uses the entire last-opposite M15 candle [low, high]. This runner
patches only the POI zone geometry while keeping sweep, BOS, stop buffer, risk
filter, target, outcome resolution and waiting-time analysis unchanged.
"""

import json
import sys
from pathlib import Path

import v14_poi_waiting_time_study as study

POI_GEOMETRY = "last_opposite_m15_full_low_high"
RUNNER = "scripts/v141_live_poi_parity.py"

study.HORIZONS = [8, 12, 16, 24, 32, 48, 72, 96, 144, 192]
study.MAX_FOLLOW = max(study.HORIZONS)

_original_find_poi = study.proxy.find_poi


def live_full_candle_poi(df, sweep_i: int, bos_i: int, direction: str):
    found = _original_find_poi(df, sweep_i, bos_i, direction)
    if found is None:
        return None
    poi_i, _old_low, _old_high = found
    return poi_i, float(df.at[poi_i, "low"]), float(df.at[poi_i, "high"])


def _annotate_summary() -> None:
    """Stamp the artifact so proxy-geometry output cannot be mistaken for live parity."""
    try:
        out_i = sys.argv.index("--out") + 1
        out_dir = Path(sys.argv[out_i])
    except (ValueError, IndexError):
        return
    path = out_dir / "v14_summary.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text())
    payload["poi_geometry"] = POI_GEOMETRY
    payload["research_runner"] = RUNNER
    payload["parity_with_live_scanner"] = True
    path.write_text(json.dumps(payload, indent=2, default=str))


study.proxy.find_poi = live_full_candle_poi

if __name__ == "__main__":
    study.main()
    _annotate_summary()
