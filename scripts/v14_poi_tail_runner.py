from __future__ import annotations

"""Long-tail runner for the preregistered v1.4 POI waiting-time study.

The primary 8/24-bar decision rule remains unchanged. This runner only extends the
observation tail so the implementation does not replace the old 8-bar boundary with
another arbitrary cutoff.
"""

import v14_poi_waiting_time_study as study

study.HORIZONS = [8, 12, 16, 24, 32, 48, 72, 96, 144, 192]
study.MAX_FOLLOW = max(study.HORIZONS)

if __name__ == "__main__":
    study.main()
