from __future__ import annotations

"""Secondary preregistered lifecycle diagnostics for V2 v1.9.

Reads the frozen penetration simulation and answers:
- what happens after shallow/grazed POI touches before midpoint?
- what happens if the theoretical target is delivered before entry?

Does not alter the primary depth-selection gate.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def target_before_entry_table(sim: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for depth, g in sim.groupby("depth", sort=True):
        valid = g[g.risk_valid.astype(bool)].copy()
        stale = valid[valid.target_before_entry.astype(bool)].copy()
        filled = stale[stale.filled.astype(bool)].copy()
        resolved = filled[filled.outcome.isin(["win", "loss"])].copy()
        rows.append({
            "depth": float(depth),
            "valid_risk_setups": int(len(valid)),
            "target_before_entry_n": int(len(stale)),
            "target_before_entry_rate": float(len(stale) / len(valid)) if len(valid) else None,
            "later_fill_rate_keep_waiting": float(filled.shape[0] / len(stale)) if len(stale) else None,
            "later_resolved_fills": int(len(resolved)),
            "later_win_rate_resolved": float((resolved.outcome == "win").mean()) if len(resolved) else None,
            "keep_waiting_opportunity_r": float(stale.gross_r_primary.mean()) if len(stale) else None,
            "cancel_on_target_delivery_opportunity_r": 0.0 if len(stale) else None,
            "keep_minus_cancel_r": float(stale.gross_r_primary.mean()) if len(stale) else None,
            "later_distal_close_rate": float(stale.distal_close_i.notna().mean()) if len(stale) else None,
            "median_later_max_penetration": float(stale.max_penetration.median()) if len(stale) and stale.max_penetration.notna().any() else None,
            "median_bars_to_later_fill": float(filled.bars_to_fill.median()) if len(filled) else None,
        })
    return pd.DataFrame(rows)


def midpoint_first_touch_table(sim: pd.DataFrame) -> pd.DataFrame:
    m = sim[np.isclose(sim.depth, 0.50)].copy()
    m = m[m.risk_valid.astype(bool)]
    rows = []
    for state, g in m.groupby("first_touch_state", dropna=False):
        fills = g[g.filled.astype(bool)]
        resolved = fills[fills.outcome.isin(["win", "loss"])]
        rows.append({
            "first_touch_state": str(state),
            "valid_midpoint_setups": int(len(g)),
            "later_midpoint_fill_rate": float(g.filled.mean()) if len(g) else None,
            "later_resolved_fills": int(len(resolved)),
            "later_win_rate_resolved": float((resolved.outcome == "win").mean()) if len(resolved) else None,
            "midpoint_opportunity_expectancy_r": float(g.gross_r_primary.mean()) if len(g) else None,
            "target_before_midpoint_rate": float(g.target_before_entry.mean()) if len(g) else None,
            "mean_pre_midpoint_favorable_r": float(g.pre_entry_max_favorable_r.mean()) if len(g) else None,
            "distal_close_rate": float(g.distal_close_i.notna().mean()) if len(g) else None,
            "median_max_penetration": float(g.max_penetration.median()) if len(g) and g.max_penetration.notna().any() else None,
        })
    return pd.DataFrame(rows)


def shallow_cohort_summary(mid: pd.DataFrame) -> dict:
    q = mid[mid.first_touch_state.isin(["GRAZED", "SHALLOW"])].copy()
    fills = q[q.filled.astype(bool)]
    resolved = fills[fills.outcome.isin(["win", "loss"])]
    stale = q[q.target_before_entry.astype(bool)]
    return {
        "n": int(len(q)),
        "later_midpoint_fill_rate": float(q.filled.mean()) if len(q) else None,
        "later_resolved_fills": int(len(resolved)),
        "later_midpoint_win_rate_resolved": float((resolved.outcome == "win").mean()) if len(resolved) else None,
        "midpoint_opportunity_expectancy_r": float(q.gross_r_primary.mean()) if len(q) else None,
        "target_before_midpoint_rate": float(q.target_before_entry.mean()) if len(q) else None,
        "target_before_midpoint_n": int(len(stale)),
        "distal_close_rate": float(q.distal_close_i.notna().mean()) if len(q) else None,
        "median_max_penetration": float(q.max_penetration.median()) if len(q) and q.max_penetration.notna().any() else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sim = pd.read_csv(a.input)
    for c in ["risk_valid", "filled", "target_before_entry"]:
        sim[c] = sim[c].astype(str).str.lower().map({"true": True, "false": False}).fillna(False)

    stale = target_before_entry_table(sim)
    first = midpoint_first_touch_table(sim)
    mid = sim[np.isclose(sim.depth, 0.50) & sim.risk_valid].copy()
    shallow = shallow_cohort_summary(mid)
    midpoint_stale = stale[np.isclose(stale.depth, 0.50)]

    summary = {
        "study": "V2 v1.9 POI lifecycle secondary diagnostics",
        "primary_depth_gate_unchanged": True,
        "midpoint_target_before_entry": midpoint_stale.iloc[0].to_dict() if len(midpoint_stale) else None,
        "midpoint_grazed_or_shallow_first_touch": shallow,
        "note": "KEEP_WAITING versus CANCEL_ON_TARGET_DELIVERY applies to the old trade plan only; it does not declare the POI structurally invalid for a future new setup.",
    }
    stale.to_csv(a.out / "v19_target_before_entry_lifecycle.csv", index=False)
    first.to_csv(a.out / "v19_midpoint_first_touch_outcomes.csv", index=False)
    (a.out / "v19_poi_lifecycle_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
