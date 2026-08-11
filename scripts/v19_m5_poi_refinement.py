from __future__ import annotations

"""V2 v1.9 secondary M5 refinement.

Protocol: reports/v19/V19_M5_REFINEMENT_PROTOCOL.md
Research only. Does not alter the first-pass static-depth decision.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from public_data_v2_proxy import load_market

SYMBOLS = ("EURUSD", "GBPUSD")
COMPLETED_YEARS = (2022, 2023, 2024, 2025)
THRESHOLDS = (0.0, 0.10, 0.20, 0.30, 0.40, 0.45)
HORIZONS_H = (1, 2, 4, 8, 24, 48)
REWARD_R = 2.5
BOOT_REPS = 2000
BOOT_SEED = 1910


def boolify(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().map({"true": True, "false": False}).fillna(False)


def penetration(direction: str, lo: float, hi: float, low: float, high: float) -> float:
    w = hi - lo
    if w <= 0:
        return np.nan
    return (hi - low) / w if direction == "long" else (high - lo) / w


def touches(low: float, high: float, price: float) -> bool:
    return low <= price <= high


def outcome_m5(row: pd.Series, m5: pd.DataFrame) -> str:
    """Refine only an M15 ambiguous fill with M5. Keep uncertainty if same M5 bar is ambiguous."""
    if row.outcome not in {"ambiguous_entry_bar", "ambiguous_exit_bar"}:
        return str(row.outcome)
    if pd.isna(row.fill_time):
        return str(row.outcome)

    entry = float(row.entry)
    stop = float(row.stop)
    target = float(row.target)
    direction = str(row.direction)
    fill_ts = pd.Timestamp(row.fill_time)
    if fill_ts.tzinfo is None:
        fill_ts = fill_ts.tz_localize("UTC")
    else:
        fill_ts = fill_ts.tz_convert("UTC")
    bos_ts = pd.Timestamp(row.bos_time)
    if bos_ts.tzinfo is None:
        bos_ts = bos_ts.tz_localize("UTC")
    else:
        bos_ts = bos_ts.tz_convert("UTC")
    end_ts = bos_ts + pd.Timedelta(minutes=15) + pd.Timedelta(hours=48)

    z = m5[(m5.date >= fill_ts) & (m5.date < min(fill_ts + pd.Timedelta(minutes=15), end_ts))]
    if z.empty:
        return "m5_missing_fill_window"
    first_idx = None
    for idx, r in z.iterrows():
        if touches(float(r.low), float(r.high), entry):
            first_idx = int(idx)
            break
    if first_idx is None:
        return "m5_entry_not_observed"

    # Entry M5 bar: if stop/target is also touched, ordering is not knowable.
    r0 = m5.loc[first_idx]
    if direction == "long":
        hit_s0 = float(r0.low) <= stop
        hit_t0 = float(r0.high) >= target
    else:
        hit_s0 = float(r0.high) >= stop
        hit_t0 = float(r0.low) <= target
    if hit_s0 or hit_t0:
        return "ambiguous_m5_entry_bar"

    q = m5[(m5.index > first_idx) & (m5.date < end_ts)]
    for _, r in q.iterrows():
        if direction == "long":
            hs = float(r.low) <= stop
            ht = float(r.high) >= target
        else:
            hs = float(r.high) >= stop
            ht = float(r.low) <= target
        if hs and ht:
            return "ambiguous_m5_exit_bar"
        if hs:
            return "loss"
        if ht:
            return "win"
    return "unresolved"


def depth_summary(g: pd.DataFrame) -> dict[str, Any]:
    valid = g[g.risk_valid].copy()
    filled = valid[valid.filled].copy()
    resolved = filled[filled.outcome_m5.isin(["win", "loss"])].copy()
    amb = filled[filled.outcome_m5.str.startswith("ambiguous")].copy()
    other_unresolved = filled[~filled.outcome_m5.isin(["win", "loss"]) & ~filled.outcome_m5.str.startswith("ambiguous")].copy()
    gross = np.where(valid.outcome_m5.eq("win"), REWARD_R, np.where(valid.outcome_m5.eq("loss"), -1.0, 0.0))
    pess = np.where(valid.outcome_m5.eq("win"), REWARD_R, np.where(valid.outcome_m5.eq("loss"), -1.0, np.where(valid.filled, -1.0, 0.0)))
    opt = np.where(valid.outcome_m5.eq("win"), REWARD_R, np.where(valid.outcome_m5.eq("loss"), -1.0, np.where(valid.filled, REWARD_R, 0.0)))
    return {
        "depth": float(g.depth.iloc[0]),
        "valid_risk_setups": int(len(valid)),
        "fill_rate": float(len(filled) / len(valid)) if len(valid) else None,
        "resolved_fills": int(len(resolved)),
        "win_rate_resolved": float((resolved.outcome_m5 == "win").mean()) if len(resolved) else None,
        "residual_ambiguity_rate_filled": float(len(amb) / len(filled)) if len(filled) else None,
        "other_unresolved_rate_filled": float(len(other_unresolved) / len(filled)) if len(filled) else None,
        "opportunity_expectancy_r": float(np.mean(gross)) if len(valid) else None,
        "opportunity_expectancy_pessimistic_r": float(np.mean(pess)) if len(valid) else None,
        "opportunity_expectancy_optimistic_r": float(np.mean(opt)) if len(valid) else None,
    }


def table(sim: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([depth_summary(g) for _, g in sim.groupby("depth", sort=True)])


def choose_depth(train: pd.DataFrame) -> float:
    t = table(train)
    t = t[(t.resolved_fills >= 100) & t.opportunity_expectancy_r.notna()].copy()
    if t.empty:
        return 0.50
    best = float(t.opportunity_expectancy_r.max())
    q = t[np.isclose(t.opportunity_expectancy_r, best, atol=1e-12)].copy()
    q["mid_dist"] = (q.depth - 0.50).abs()
    return float(q.sort_values(["mid_dist", "depth"]).iloc[0].depth)


def contribution(g: pd.DataFrame) -> np.ndarray:
    return np.where(g.outcome_m5.eq("win"), REWARD_R, np.where(g.outcome_m5.eq("loss"), -1.0, 0.0)).astype(float)


def walkforward(sim: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    yearly, paired = [], []
    for year in sorted(int(y) for y in sim.year.unique() if int(y) >= 2022):
        train = sim[sim.year < year]
        test = sim[sim.year == year]
        if train.empty or test.empty:
            continue
        d = choose_depth(train)
        cand = test[np.isclose(test.depth, d)].set_index("setup_id")
        mid = test[np.isclose(test.depth, 0.50)].set_index("setup_id")
        common = cand.index.intersection(mid.index)
        mask = cand.loc[common, "risk_valid"].to_numpy(bool) & mid.loc[common, "risk_valid"].to_numpy(bool)
        common = common[mask]
        c = cand.loc[common].copy(); m = mid.loc[common].copy()
        cg = contribution(c); mg = contribution(m); delta = cg - mg
        yearly.append({
            "year": year, "chosen_depth": d, "paired_setups": int(len(common)),
            "candidate_opportunity_r": float(cg.mean()) if len(cg) else None,
            "midpoint_opportunity_r": float(mg.mean()) if len(mg) else None,
            "delta_r": float(delta.mean()) if len(delta) else None,
            "candidate_fill_rate": float(c.filled.mean()) if len(c) else None,
            "midpoint_fill_rate": float(m.filled.mean()) if len(m) else None,
        })
        for sid, dv in zip(common, delta):
            paired.append({"year": year, "setup_id": sid, "chosen_depth": d, "delta_r": float(dv), "symbol": c.loc[sid, "symbol"]})
    return pd.DataFrame(yearly), pd.DataFrame(paired)


def bootstrap(paired: pd.DataFrame) -> dict[str, Any]:
    if paired.empty:
        return {"n": 0, "point": None, "low95": None, "high95": None}
    x = paired.delta_r.to_numpy(float)
    rng = np.random.default_rng(BOOT_SEED)
    vals = np.empty(BOOT_REPS)
    for i in range(BOOT_REPS):
        vals[i] = float(np.mean(x[rng.integers(0, len(x), len(x))]))
    return {"n": int(len(x)), "point": float(x.mean()), "low95": float(np.quantile(vals, .025)), "high95": float(np.quantile(vals, .975)), "reps": BOOT_REPS, "seed": BOOT_SEED}


def pair_delta(paired: pd.DataFrame) -> dict[str, Any]:
    out = {}
    for s in SYMBOLS:
        q = paired[paired.symbol == s]
        out[s] = {"n": int(len(q)), "mean_delta_r": float(q.delta_r.mean()) if len(q) else None}
    return out


def first_index_touch(z: pd.DataFrame, price: float) -> int | None:
    m = (z.low.to_numpy(float) <= price) & (z.high.to_numpy(float) >= price)
    if not m.any():
        return None
    return int(z.index[np.flatnonzero(m)[0]])


def threshold_events(setups: pd.DataFrame, m5_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, s in setups.iterrows():
        sym = str(s.symbol); direction = str(s.direction)
        m5 = m5_by_symbol[sym]
        bos = pd.Timestamp(s.bos_time)
        if bos.tzinfo is None: bos = bos.tz_localize("UTC")
        else: bos = bos.tz_convert("UTC")
        start = bos + pd.Timedelta(minutes=15)
        end = start + pd.Timedelta(hours=48)
        z = m5[(m5.date >= start) & (m5.date < end)]
        if z.empty:
            continue
        lo, hi = float(s.poi_low), float(s.poi_high)
        mid = (lo + hi) / 2.0
        stop = float(s.stop); atr = float(s.atr)
        risk = (mid - stop) if direction == "long" else (stop - mid)
        risk_atr = risk / atr if atr > 0 else np.nan
        if not (np.isfinite(risk_atr) and risk > 0 and .08 <= risk_atr <= 1.60):
            continue
        proximal = hi if direction == "long" else lo
        one_r = mid + risk if direction == "long" else mid - risk
        two5_r = mid + REWARD_R * risk if direction == "long" else mid - REWARD_R * risk
        lows = z.low.to_numpy(float); highs = z.high.to_numpy(float)
        pens = np.array([penetration(direction, lo, hi, l, h) for l, h in zip(lows, highs)])
        mid_touch_mask = (lows <= mid) & (highs >= mid)

        for th in THRESHOLDS:
            candidate = np.flatnonzero((pens >= th) & (~mid_touch_mask))
            if not len(candidate):
                continue
            pos = int(candidate[0]); event_idx = int(z.index[pos]); event_time = pd.Timestamp(z.loc[event_idx, "date"])
            after = z[(z.index > event_idx)]
            if after.empty:
                continue
            mid_idx = first_index_touch(after, mid)
            distal = lo if direction == "long" else hi
            distal_idx = first_index_touch(after, distal)
            mid_time = pd.NaT if mid_idx is None else pd.Timestamp(m5.loc[mid_idx, "date"])
            distal_time = pd.NaT if distal_idx is None else pd.Timestamp(m5.loc[distal_idx, "date"])
            before_mid = after if mid_idx is None else after[after.index < mid_idx]
            if len(before_mid):
                if direction == "long":
                    fav_r = max(0.0, (float(before_mid.high.max()) - proximal) / risk)
                    fav_atr = max(0.0, (float(before_mid.high.max()) - proximal) / atr)
                    hit1 = bool((before_mid.high >= one_r).any())
                    hit25 = bool((before_mid.high >= two5_r).any())
                else:
                    fav_r = max(0.0, (proximal - float(before_mid.low.min())) / risk)
                    fav_atr = max(0.0, (proximal - float(before_mid.low.min())) / atr)
                    hit1 = bool((before_mid.low <= one_r).any())
                    hit25 = bool((before_mid.low <= two5_r).any())
            else:
                fav_r = fav_atr = 0.0; hit1 = hit25 = False

            rec: dict[str, Any] = {
                "setup_id": s.setup_id, "symbol": sym, "direction": direction, "year": int(s.year),
                "threshold": float(th), "event_time": event_time,
                "event_penetration": float(pens[pos]), "midpoint_later": mid_idx is not None,
                "hours_to_midpoint": None if mid_idx is None else float((mid_time - event_time) / pd.Timedelta(hours=1)),
                "distal_later": distal_idx is not None,
                "hours_to_distal": None if distal_idx is None else float((distal_time - event_time) / pd.Timedelta(hours=1)),
                "hit_1r_before_midpoint": hit1, "hit_2p5r_before_midpoint": hit25,
                "max_favorable_r_before_midpoint": float(fav_r), "max_favorable_atr_before_midpoint": float(fav_atr),
                "m15_distal_close": pd.notna(s.get("distal_close_time", pd.NaT)),
            }
            for h in HORIZONS_H:
                rec[f"midpoint_within_{h}h"] = bool(mid_idx is not None and (mid_time - event_time) <= pd.Timedelta(hours=h))
                rec[f"distal_within_{h}h"] = bool(distal_idx is not None and (distal_time - event_time) <= pd.Timedelta(hours=h))
                hh = after[after.date <= event_time + pd.Timedelta(hours=h)]
                if mid_idx is not None:
                    hh = hh[hh.index < mid_idx]
                if direction == "long":
                    rec[f"hit_1r_before_midpoint_within_{h}h"] = bool(len(hh) and (hh.high >= one_r).any())
                    rec[f"hit_2p5r_before_midpoint_within_{h}h"] = bool(len(hh) and (hh.high >= two5_r).any())
                else:
                    rec[f"hit_1r_before_midpoint_within_{h}h"] = bool(len(hh) and (hh.low <= one_r).any())
                    rec[f"hit_2p5r_before_midpoint_within_{h}h"] = bool(len(hh) and (hh.low <= two5_r).any())
            rows.append(rec)
    return pd.DataFrame(rows)


def reaction_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for th, g in events.groupby("threshold", sort=True):
        r: dict[str, Any] = {
            "threshold": float(th), "events": int(len(g)),
            "event_penetration_median": float(g.event_penetration.median()),
            "later_midpoint_rate_48h": float(g.midpoint_later.mean()),
            "later_distal_rate_48h": float(g.distal_later.mean()),
            "m15_distal_close_rate_48h": float(g.m15_distal_close.mean()),
            "hit_1r_before_midpoint_rate": float(g.hit_1r_before_midpoint.mean()),
            "hit_2p5r_before_midpoint_rate": float(g.hit_2p5r_before_midpoint.mean()),
            "median_max_favorable_r_before_midpoint": float(g.max_favorable_r_before_midpoint.median()),
            "median_max_favorable_atr_before_midpoint": float(g.max_favorable_atr_before_midpoint.median()),
            "median_hours_to_midpoint": float(g.loc[g.midpoint_later, "hours_to_midpoint"].median()) if g.midpoint_later.any() else None,
        }
        for h in HORIZONS_H:
            r[f"midpoint_within_{h}h_rate"] = float(g[f"midpoint_within_{h}h"].mean())
            r[f"hit_1r_before_midpoint_within_{h}h_rate"] = float(g[f"hit_1r_before_midpoint_within_{h}h"].mean())
            r[f"hit_2p5r_before_midpoint_within_{h}h_rate"] = float(g[f"hit_2p5r_before_midpoint_within_{h}h"].mean())
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--sim", type=Path, required=True)
    ap.add_argument("--setups", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)

    sim = pd.read_csv(a.sim)
    setups = pd.read_csv(a.setups)
    for c in ("risk_valid", "filled", "target_before_entry"):
        if c in sim: sim[c] = boolify(sim[c])
    for c in ("fill_time", "bos_time"):
        sim[c] = pd.to_datetime(sim[c], utc=True, errors="coerce")
    for c in ("bos_time", "distal_close_time"):
        if c in setups: setups[c] = pd.to_datetime(setups[c], utc=True, errors="coerce")

    m5_by_symbol: dict[str, pd.DataFrame] = {}
    for sym in SYMBOLS:
        x = load_market(a.data_dir / f"{sym}-5m.feather", sym).reset_index(drop=True)
        x["date"] = pd.to_datetime(x.date, utc=True)
        m5_by_symbol[sym] = x

    sim["outcome_m5"] = sim.outcome.astype(str)
    for sym in SYMBOLS:
        idxs = sim.index[(sim.symbol == sym) & sim.filled & sim.outcome.isin(["ambiguous_entry_bar", "ambiguous_exit_bar"])].tolist()
        m5 = m5_by_symbol[sym]
        for idx in idxs:
            sim.at[idx, "outcome_m5"] = outcome_m5(sim.loc[idx], m5)

    completed = sim[sim.year.isin(COMPLETED_YEARS)].copy()
    t = table(completed)
    yearly, paired = walkforward(sim)
    pc = paired[paired.year.isin(COMPLETED_YEARS)].copy()
    boot = bootstrap(pc)
    pdlt = pair_delta(pc)

    events = threshold_events(setups, m5_by_symbol)
    events_completed = events[events.year.isin(COMPLETED_YEARS)].copy()
    rs = reaction_summary(events_completed)

    midpoint = t[np.isclose(t.depth, .50)].iloc[0].to_dict() if np.isclose(t.depth, .50).any() else None
    best = t.sort_values("opportunity_expectancy_r", ascending=False).iloc[0].to_dict() if len(t) else None
    ycomp = yearly[yearly.year.isin(COMPLETED_YEARS)]
    noninf = int((ycomp.delta_r >= 0).sum()) if len(ycomp) else 0
    decision = "KEEP_MIDPOINT_RESEARCH_ONLY"
    if (
        boot.get("low95") is not None and boot["low95"] > 0 and noninf >= 3
        and all(pdlt[s]["mean_delta_r"] is not None and pdlt[s]["mean_delta_r"] >= 0 for s in SYMBOLS)
    ):
        decision = "M5_STATIC_DEPTH_CANDIDATE_PASSES_HISTORICAL_GATE"

    summary = {
        "study": "V2 v1.9 M5 POI refinement",
        "protocol": "reports/v19/V19_M5_REFINEMENT_PROTOCOL.md",
        "m5_rows": {s: int(len(m5_by_symbol[s])) for s in SYMBOLS},
        "m15_ambiguous_rows_before_refinement": int(sim.outcome.isin(["ambiguous_entry_bar", "ambiguous_exit_bar"]).sum()),
        "residual_m5_ambiguous_rows": int(sim.outcome_m5.str.startswith("ambiguous_m5").sum()),
        "midpoint_completed": midpoint,
        "best_descriptive_completed": best,
        "walkforward": yearly.to_dict(orient="records"),
        "walkforward_completed_bootstrap_candidate_minus_midpoint": boot,
        "walkforward_completed_pair_delta": pdlt,
        "walkforward_noninferior_years": noninf,
        "decision": decision,
        "reaction_completed": rs.to_dict(orient="records"),
        "boundary": "M5 public OHLC reduces but cannot eliminate intrabar/execution ambiguity; no broker-edge claim.",
    }

    sim.to_csv(a.out / "v19_m5_refined_depth_rows.csv", index=False)
    t.to_csv(a.out / "v19_m5_depth_table_completed_2022_2025.csv", index=False)
    yearly.to_csv(a.out / "v19_m5_walkforward_yearly.csv", index=False)
    paired.to_csv(a.out / "v19_m5_walkforward_paired.csv", index=False)
    events.to_csv(a.out / "v19_m5_penetration_events.csv", index=False)
    rs.to_csv(a.out / "v19_m5_reaction_summary_completed_2022_2025.csv", index=False)
    (a.out / "v19_m5_refinement_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
