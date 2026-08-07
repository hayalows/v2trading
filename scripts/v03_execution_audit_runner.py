from __future__ import annotations

"""Compatibility + causal basis runner for the independent XAUUSD M1 audit.

Two implementation issues are handled here without changing setup rules:
1. timezone-aware object arrays are converted once to UTC integer nanoseconds for
   efficient searchsorted;
2. cross-source price levels are translated by the difference between the LAST
   COMPLETED source M15 close and the LAST COMPLETED independent M15 close before
   the trade timestamp. Both values are known pre-entry. This avoids rejecting all
   trades merely because two spot/CFD feeds quote gold on a different local basis.

The audit remains cross-source and therefore diagnostic, not a broker fill guarantee.
"""

import numpy as np
import pandas as pd

_original_searchsorted = np.searchsorted
_index_cache: dict[int, np.ndarray] = {}


def _searchsorted_utc(a, v, side="left", sorter=None):
    arr = np.asarray(a)
    if arr.dtype == object and len(arr):
        first = next((x for x in arr if x is not None), None)
        if isinstance(first, (pd.Timestamp, np.datetime64)):
            key = id(arr)
            ai = _index_cache.get(key)
            if ai is None:
                ai = pd.to_datetime(arr, utc=True, errors="coerce").astype("int64").to_numpy()
                _index_cache[key] = ai
            tv = pd.Timestamp(v)
            vi = tv.tz_localize("UTC").value if tv.tzinfo is None else tv.tz_convert("UTC").value
            return _original_searchsorted(ai, vi, side=side, sorter=sorter)
    return _original_searchsorted(a, v, side=side, sorter=sorter)


np.searchsorted = _searchsorted_utc

import v03_execution_audit


def _causal_level_offset(entry_time: pd.Timestamp, source15: pd.DataFrame, independent15: pd.DataFrame) -> float | None:
    ts = pd.Timestamp(entry_time)
    s = source15[(pd.to_datetime(source15.date, utc=True) + pd.Timedelta(minutes=15)) <= ts]
    q = independent15[(pd.to_datetime(independent15.date, utc=True) + pd.Timedelta(minutes=15)) <= ts]
    if s.empty or q.empty:
        return None
    # Both are the last completed 15-minute observations available at entry.
    return float(q.iloc[-1].close - s.iloc[-1].close)


v03_execution_audit.level_offset = _causal_level_offset

if __name__ == "__main__":
    v03_execution_audit.main()
