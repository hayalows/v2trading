from __future__ import annotations

"""Pandas 3 compatibility runner for V2 Quant v0.3.

GitHub's current pandas build can preserve different datetime resolutions after
CSV/Feather parsing (for example datetime64[us, UTC] vs datetime64[ns, UTC]).
`merge_asof` requires exact matching dtypes. This wrapper normalizes datetime join
keys to UTC nanoseconds and removes stale helper join keys before subsequent as-of
merges. It changes no research logic, features, labels, lags, thresholds, or model
parameters.
"""

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

_original_merge_asof = pd.merge_asof


def _as_ns_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce").astype("datetime64[ns, UTC]")


def _merge_asof_compat(left, right, *args, **kwargs):
    l = left.copy()
    r = right.copy()
    left_on = kwargs.get("left_on")
    right_on = kwargs.get("right_on")
    on = kwargs.get("on")

    if on is not None:
        left_on = right_on = on

    if left_on is not None and right_on is not None:
        # A prior as-of merge can leave the previous right-side helper key on the
        # left frame. Drop it before a new join so pandas does not create _x/_y
        # suffixes that break the caller's normal post-merge cleanup.
        if right_on != left_on and right_on in l.columns:
            l = l.drop(columns=[right_on])
        if is_datetime64_any_dtype(l[left_on].dtype):
            l[left_on] = _as_ns_utc(l[left_on])
        if is_datetime64_any_dtype(r[right_on].dtype):
            r[right_on] = _as_ns_utc(r[right_on])

    return _original_merge_asof(l, r, *args, **kwargs)


pd.merge_asof = _merge_asof_compat

import v03_quant_stack


if __name__ == "__main__":
    v03_quant_stack.main()
