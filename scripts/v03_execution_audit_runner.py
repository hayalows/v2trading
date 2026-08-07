from __future__ import annotations

"""Compatibility runner for the v0.3 independent XAUUSD M1 audit.

Pandas 3 returns timezone-aware Timestamps in an object ndarray for this CSV. Numpy's
searchsorted then attempts to compare tz-aware pandas objects with a tz-naive
np.datetime64 scalar. This wrapper compares integer UTC nanoseconds instead. It does
not alter any price, entry, stop, target, quote-offset, delay, or outcome rule.
"""

import numpy as np
import pandas as pd

_original_searchsorted = np.searchsorted


def _searchsorted_utc(a, v, side="left", sorter=None):
    arr = np.asarray(a)
    if arr.dtype == object and len(arr):
        first = next((x for x in arr if x is not None), None)
        if isinstance(first, (pd.Timestamp, np.datetime64)):
            ai = pd.to_datetime(arr, utc=True, errors="coerce").astype("int64").to_numpy()
            vi = pd.Timestamp(v).tz_localize("UTC").value if pd.Timestamp(v).tzinfo is None else pd.Timestamp(v).tz_convert("UTC").value
            return _original_searchsorted(ai, vi, side=side, sorter=sorter)
    return _original_searchsorted(a, v, side=side, sorter=sorter)


np.searchsorted = _searchsorted_utc

import v03_execution_audit


if __name__ == "__main__":
    v03_execution_audit.main()
