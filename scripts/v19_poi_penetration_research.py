from __future__ import annotations

"""V2 v1.9 POI Penetration Lab.

Preregistered in reports/v19/V19_POI_PENETRATION_PROTOCOL.md before this script was run.
Research only: public OHLC proxy, no broker execution claim.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from public_data_v2_proxy import load_market

SYMBOLS = ("EURUSD", "GBPUSD")
DEPTHS = np.round(np.arange(0.0, 1.0001, 0.05), 2)
COMPLETED_YEARS = (2022, 2023, 2024, 2025)
ATR_N = 14
SWEEP_LOOKBACK = 20
BOS_LOOKBACK = 8
SWEEP_MIN_ATR = 0.03
LIVE_SWEEP_MAX_AGE = 11
STOP_BUFFER_ATR = 0.03
REWARD_R = 2.5
MIN_RISK_ATR = 0.08
MAX_RISK_ATR = 1.60
HORIZON_BARS = 192
BOOT_REPS = 2000
BOOT_SEED = 1909


def tr_array(df: pd.DataFrame) -> np.ndarray:
    h = df.high.to_numpy(float)
    l = df.low.to_numpy(float)
    c = df.close.to_numpy(float)
    prev = np.r_[c[0], c[:-1]]
    return np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))


def rolling_atr(tr: np.ndarray, n: int = ATR_N) -> np.ndarray:
    s = pd.Series(tr)
    return s.rolling(n, min_periods=n).mean().to_numpy(float)


def session_bucket(ts: pd.Timestamp) -> str:
    h = int(ts.hour)
    if 0 <= h < 7:
        return "asia"
    if 7 <= h < 12:
        return "london"
    if 12 <= h < 16:
        return "overlap"
    if 16 <= h < 21:
        return "new_york"
    return "off_hours"


def poi_entry(direction: str, lo: float, hi: float, depth: float) -> float:
    w = hi - lo
    return hi - depth * w if direction == "long" else lo + depth * w


def penetration(direction: str, lo: float, hi: float, bar_low: float, bar_high: float) -> float:
    w = hi - lo
    if w <= 0:
        return np.nan
    return (hi - bar_low) / w if direction == "long" else (bar_high - lo) / w


def touch_level(direction: str, row: pd.Series, price: float) -> bool:
    return float(row.low) <= price <= float(row.high)


def target_hit(direction: str, row: pd.Series, target: float) -> bool:
    return float(row.high) >= target if direction == "long" else float(row.low) <= target


def stop_hit(direction: str, row: pd.Series, stop: float) -> bool:
    return float(row.low) <= stop if direction == "long" else float(row.high) >= stop


def distal_close_through(direction: str, row: pd.Series, lo: float, hi: float) -> bool:
    return float(row.close) < lo if direction == "long" else float(row.close) > hi


def touch_zone(row: pd.Series, lo: float, hi: float) -> bool:
    return float(row.low) <= hi and float(row.high) >= lo


def find_poi_full_candle(df: pd.DataFrame, sweep_i: int, bos_i: int, direction: str) -> tuple[int, float, float] | None:
    for i in range(bos_i, sweep_i - 1, -1):
        opposite = (float(df.iloc[i].close) < float(df.iloc[i].open)) if direction == "long" else (float(df.iloc[i].close) > float(df.iloc[i].open))
        if opposite:
            return i, float(df.iloc[i].low), float(df.iloc[i].high)
    return None


def detect_pois(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    tr = tr_array(df)
    atr = rolling_atr(tr)
    o = df.open.to_numpy(float)
    h = df.high.to_numpy(float)
    l = df.low.to_numpy(float)
    c = df.close.to_numpy(float)
    times = pd.to_datetime(df.date, utc=True)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    start = max(ATR_N + 2, SWEEP_LOOKBACK + 2, BOS_LOOKBACK + 2)

    for i in range(start, len(df) - 2):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        prior_h = float(np.max(h[i - SWEEP_LOOKBACK:i]))
        prior_l = float(np.min(l[i - SWEEP_LOOKBACK:i]))
        bear = h[i] > prior_h + SWEEP_MIN_ATR * a and c[i] < prior_h
        bull = l[i] < prior_l - SWEEP_MIN_ATR * a and c[i] > prior_l
        candidates = []
        if bear:
            candidates.append("short")
        if bull:
            candidates.append("long")
        if not candidates:
            continue

        pre0 = max(0, i - BOS_LOOKBACK)
        if pre0 == i:
            continue
        bos_high = float(np.max(h[pre0:i]))
        bos_low = float(np.min(l[pre0:i]))

        for direction in candidates:
            bos_i = -1
            end = min(len(df), i + LIVE_SWEEP_MAX_AGE + 2)
            for j in range(i + 1, end):
                if (direction == "long" and c[j] > bos_high) or (direction == "short" and c[j] < bos_low):
                    bos_i = j
                    break
            if bos_i < 0:
                continue
            poi = find_poi_full_candle(df, i, bos_i, direction)
            if poi is None:
                continue
            poi_i, lo, hi = poi
            if hi <= lo:
                continue
            key = (symbol, direction, times.iloc[i].isoformat(), times.iloc[bos_i].isoformat(), times.iloc[poi_i].isoformat())
            if key in seen:
                continue
            seen.add(key)
            sweep_extreme = float(l[i] if direction == "long" else h[i])
            stop = sweep_extreme - STOP_BUFFER_ATR * a if direction == "long" else sweep_extreme + STOP_BUFFER_ATR * a
            bos_ref = bos_high if direction == "long" else bos_low
            bos_disp = abs(float(c[bos_i]) - bos_ref) / a
            rows.append({
                "setup_id": f"{symbol}:{direction}:{times.iloc[i].isoformat()}",
                "symbol": symbol,
                "direction": direction,
                "sweep_i": i,
                "bos_i": bos_i,
                "poi_i": poi_i,
                "sweep_time": times.iloc[i],
                "bos_time": times.iloc[bos_i],
                "poi_time": times.iloc[poi_i],
                "year": int(times.iloc[bos_i].year),
                "session": session_bucket(times.iloc[bos_i]),
                "poi_low": lo,
                "poi_high": hi,
                "poi_width": hi - lo,
                "atr": float(a),
                "zone_width_atr": float((hi - lo) / a),
                "sweep_extreme": sweep_extreme,
                "stop": float(stop),
                "bos_reference": bos_ref,
                "bos_displacement_atr": float(bos_disp),
                "sweep_to_bos_bars": int(bos_i - i),
            })
    return pd.DataFrame(rows)


def zone_diagnostics(df: pd.DataFrame, setup: pd.Series) -> dict[str, Any]:
    start = int(setup.bos_i) + 1
    end = min(len(df), start + HORIZON_BARS)
    lo, hi = float(setup.poi_low), float(setup.poi_high)
    direction = str(setup.direction)
    first_touch_i = None
    first_pen = None
    max_pen = -np.inf
    distal_close_i = None
    for j in range(start, end):
        r = df.iloc[j]
        p = penetration(direction, lo, hi, float(r.low), float(r.high))
        if np.isfinite(p):
            max_pen = max(max_pen, p)
        if first_touch_i is None and touch_zone(r, lo, hi):
            first_touch_i = j
            first_pen = max(0.0, p)
        if distal_close_i is None and distal_close_through(direction, r, lo, hi):
            distal_close_i = j
    if first_touch_i is None:
        state = "UNTOUCHED"
    else:
        p = float(first_pen)
        if p < 0.25:
            state = "GRAZED"
        elif p < 0.50:
            state = "SHALLOW"
        elif p < 1.00:
            state = "DEEP"
        elif distal_close_i is None or distal_close_i > first_touch_i:
            state = "DISTAL_TOUCHED"
        else:
            state = "CLOSE_THROUGH_DISTAL"
    return {
        "first_zone_touch_i": first_touch_i,
        "first_zone_touch_time": pd.NaT if first_touch_i is None else pd.Timestamp(df.iloc[first_touch_i].date),
        "first_touch_penetration": np.nan if first_pen is None else float(first_pen),
        "max_penetration": np.nan if max_pen == -np.inf else float(max_pen),
        "first_touch_state": state,
        "distal_close_i": distal_close_i,
        "distal_close_time": pd.NaT if distal_close_i is None else pd.Timestamp(df.iloc[distal_close_i].date),
    }


def simulate_depth(df: pd.DataFrame, setup: pd.Series, depth: float, zdiag: dict[str, Any]) -> dict[str, Any]:
    direction = str(setup.direction)
    lo, hi = float(setup.poi_low), float(setup.poi_high)
    entry = poi_entry(direction, lo, hi, depth)
    stop = float(setup.stop)
    atr = float(setup.atr)
    risk = entry - stop if direction == "long" else stop - entry
    risk_atr = risk / atr if atr > 0 else np.nan
    risk_valid = bool(np.isfinite(risk_atr) and risk > 0 and MIN_RISK_ATR <= risk_atr <= MAX_RISK_ATR)
    target = entry + REWARD_R * risk if direction == "long" else entry - REWARD_R * risk
    start = int(setup.bos_i) + 1
    end = min(len(df), start + HORIZON_BARS)

    fill_i = None
    target_before_entry = False
    pre_fav_r = 0.0
    if risk > 0:
        for j in range(start, end):
            r = df.iloc[j]
            if touch_level(direction, r, entry):
                fill_i = j
                break
            if target_hit(direction, r, target):
                target_before_entry = True
            fav = (float(r.high) - entry) / risk if direction == "long" else (entry - float(r.low)) / risk
            pre_fav_r = max(pre_fav_r, fav)

    outcome = "not_filled"
    exit_i = None
    gross_r = 0.0
    post_mfe_r = np.nan
    post_mae_r = np.nan
    if fill_i is not None:
        highs = []
        lows = []
        for j in range(fill_i, end):
            r = df.iloc[j]
            highs.append(float(r.high)); lows.append(float(r.low))
            hs = stop_hit(direction, r, stop)
            ht = target_hit(direction, r, target)
            if j == fill_i and (hs or ht):
                outcome = "ambiguous_entry_bar"
                exit_i = j
                break
            if hs and ht:
                outcome = "ambiguous_exit_bar"
                exit_i = j
                break
            if hs:
                outcome = "loss"
                exit_i = j
                gross_r = -1.0
                break
            if ht:
                outcome = "win"
                exit_i = j
                gross_r = REWARD_R
                break
        if exit_i is None:
            outcome = "unresolved"
        if risk > 0 and highs:
            if direction == "long":
                post_mfe_r = (max(highs) - entry) / risk
                post_mae_r = (entry - min(lows)) / risk
            else:
                post_mfe_r = (entry - min(lows)) / risk
                post_mae_r = (max(highs) - entry) / risk

    return {
        "setup_id": setup.setup_id,
        "symbol": setup.symbol,
        "direction": direction,
        "year": int(setup.year),
        "session": setup.session,
        "bos_time": setup.bos_time,
        "sweep_time": setup.sweep_time,
        "poi_time": setup.poi_time,
        "depth": float(depth),
        "entry": float(entry),
        "stop": stop,
        "target": float(target),
        "risk": float(risk),
        "risk_atr": float(risk_atr) if np.isfinite(risk_atr) else np.nan,
        "risk_valid": risk_valid,
        "filled": fill_i is not None,
        "fill_time": pd.NaT if fill_i is None else pd.Timestamp(df.iloc[fill_i].date),
        "bars_to_fill": np.nan if fill_i is None else int(fill_i - start + 1),
        "outcome": outcome,
        "gross_r_primary": float(gross_r),
        "gross_r_pessimistic": float(-1.0 if outcome.startswith("ambiguous") else gross_r),
        "gross_r_optimistic": float(REWARD_R if outcome.startswith("ambiguous") else gross_r),
        "target_before_entry": bool(target_before_entry),
        "pre_entry_max_favorable_r": float(max(0.0, pre_fav_r)),
        "post_mfe_r": post_mfe_r,
        "post_mae_r": post_mae_r,
        "poi_low": float(setup.poi_low),
        "poi_high": float(setup.poi_high),
        "zone_width_atr": float(setup.zone_width_atr),
        "bos_displacement_atr": float(setup.bos_displacement_atr),
        "sweep_to_bos_bars": int(setup.sweep_to_bos_bars),
        **zdiag,
    }


def summarize_depth(g: pd.DataFrame) -> dict[str, Any]:
    valid = g[g.risk_valid].copy()
    filled = valid[valid.filled].copy()
    resolved = filled[filled.outcome.isin(["win", "loss"])].copy()
    amb = filled[filled.outcome.str.startswith("ambiguous")].copy()
    unresolved = filled[filled.outcome == "unresolved"].copy()
    denom = len(valid)
    return {
        "depth": float(g.depth.iloc[0]),
        "setups": int(len(g)),
        "valid_risk_setups": int(denom),
        "fill_rate": float(len(filled) / denom) if denom else None,
        "resolved_fills": int(len(resolved)),
        "win_rate_resolved": float((resolved.outcome == "win").mean()) if len(resolved) else None,
        "ambiguous_rate_filled": float(len(amb) / len(filled)) if len(filled) else None,
        "unresolved_rate_filled": float(len(unresolved) / len(filled)) if len(filled) else None,
        "expectancy_per_resolved_fill_r": float(resolved.gross_r_primary.mean()) if len(resolved) else None,
        "opportunity_expectancy_r": float(valid.gross_r_primary.sum() / denom) if denom else None,
        "opportunity_expectancy_pessimistic_r": float(valid.gross_r_pessimistic.sum() / denom) if denom else None,
        "opportunity_expectancy_optimistic_r": float(valid.gross_r_optimistic.sum() / denom) if denom else None,
        "target_before_entry_rate": float(valid.target_before_entry.mean()) if denom else None,
        "median_bars_to_fill": float(filled.bars_to_fill.median()) if len(filled) else None,
        "median_post_mfe_r": float(filled.post_mfe_r.median()) if len(filled) else None,
        "median_post_mae_r": float(filled.post_mae_r.median()) if len(filled) else None,
    }


def depth_table(sim: pd.DataFrame, mask: pd.Series | None = None) -> pd.DataFrame:
    x = sim if mask is None else sim[mask]
    rows = [summarize_depth(g) for _, g in x.groupby("depth", sort=True)]
    return pd.DataFrame(rows)


def first_touch_summary(sim: pd.DataFrame) -> pd.DataFrame:
    base = sim[sim.depth == 0.50].copy()
    out = []
    for state, g in base.groupby("first_touch_state", dropna=False):
        out.append({
            "first_touch_state": state,
            "setups": int(len(g)),
            "midpoint_fill_rate": float(g.filled.mean()),
            "midpoint_target_before_entry_rate": float(g.target_before_entry.mean()),
            "mean_pre_midpoint_favorable_r": float(g.pre_entry_max_favorable_r.mean()),
            "median_max_penetration": float(g.max_penetration.median()) if g.max_penetration.notna().any() else None,
            "distal_close_rate": float(g.distal_close_i.notna().mean()),
        })
    return pd.DataFrame(out)


def choose_depth(train: pd.DataFrame) -> float:
    tab = depth_table(train)
    tab = tab[(tab.resolved_fills >= 100) & tab.opportunity_expectancy_r.notna()].copy()
    if tab.empty:
        return 0.50
    best = tab.opportunity_expectancy_r.max()
    q = tab[np.isclose(tab.opportunity_expectancy_r, best, atol=1e-12)].copy()
    q["mid_dist"] = (q.depth - 0.50).abs()
    q = q.sort_values(["mid_dist", "depth"])
    return float(q.iloc[0].depth)


def walkforward(sim: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    yearly = []
    paired = []
    for year in sorted(int(y) for y in sim.year.unique() if int(y) >= 2022):
        train = sim[sim.year < year].copy()
        test = sim[sim.year == year].copy()
        if train.empty or test.empty:
            continue
        d = choose_depth(train)
        cand = test[np.isclose(test.depth, d)].set_index("setup_id")
        mid = test[np.isclose(test.depth, 0.50)].set_index("setup_id")
        common = cand.index.intersection(mid.index)
        common = common[cand.loc[common, "risk_valid"].to_numpy(bool) & mid.loc[common, "risk_valid"].to_numpy(bool)]
        c = cand.loc[common]
        m = mid.loc[common]
        delta = c.gross_r_primary.to_numpy(float) - m.gross_r_primary.to_numpy(float)
        yearly.append({
            "year": year,
            "chosen_depth": d,
            "paired_setups": int(len(common)),
            "candidate_opportunity_r": float(c.gross_r_primary.mean()) if len(c) else None,
            "midpoint_opportunity_r": float(m.gross_r_primary.mean()) if len(m) else None,
            "delta_r": float(delta.mean()) if len(delta) else None,
            "candidate_fill_rate": float(c.filled.mean()) if len(c) else None,
            "midpoint_fill_rate": float(m.filled.mean()) if len(m) else None,
        })
        for sid, dv in zip(common, delta):
            paired.append({"year": year, "setup_id": sid, "chosen_depth": d, "delta_r": float(dv), "symbol": c.loc[sid, "symbol"]})
    return pd.DataFrame(yearly), pd.DataFrame(paired)


def bootstrap_delta(paired: pd.DataFrame) -> dict[str, Any]:
    if paired.empty:
        return {"n": 0, "point": None, "low95": None, "high95": None}
    x = paired.delta_r.to_numpy(float)
    rng = np.random.default_rng(BOOT_SEED)
    vals = np.empty(BOOT_REPS)
    for i in range(BOOT_REPS):
        idx = rng.integers(0, len(x), len(x))
        vals[i] = float(np.mean(x[idx]))
    return {
        "n": int(len(x)), "point": float(np.mean(x)),
        "low95": float(np.quantile(vals, 0.025)), "high95": float(np.quantile(vals, 0.975)),
        "reps": BOOT_REPS, "seed": BOOT_SEED,
    }


def pair_delta(paired: pd.DataFrame) -> dict[str, Any]:
    out = {}
    for sym in SYMBOLS:
        q = paired[paired.symbol == sym]
        out[sym] = {"n": int(len(q)), "mean_delta_r": float(q.delta_r.mean()) if len(q) else None}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(args.start, tz="UTC")

    all_setups = []
    all_sim = []
    for sym in SYMBOLS:
        df = load_market(args.data_dir / f"{sym}-15m.feather", sym)
        df = df[df.date >= start].reset_index(drop=True)
        setups = detect_pois(df, sym)
        if setups.empty:
            continue
        for _, s in setups.iterrows():
            z = zone_diagnostics(df, s)
            all_setups.append({**s.to_dict(), **z})
            for d in DEPTHS:
                all_sim.append(simulate_depth(df, s, float(d), z))

    setups = pd.DataFrame(all_setups)
    sim = pd.DataFrame(all_sim)
    if sim.empty:
        raise RuntimeError("No POI simulations produced")

    table_all = depth_table(sim)
    table_completed = depth_table(sim, sim.year.isin(COMPLETED_YEARS))
    first_touch = first_touch_summary(sim)
    yearly, paired = walkforward(sim)
    boot = bootstrap_delta(paired[paired.year.isin(COMPLETED_YEARS)])
    pdlt = pair_delta(paired[paired.year.isin(COMPLETED_YEARS)])

    completed_year_rows = yearly[yearly.year.isin(COMPLETED_YEARS)]
    positive_years = int((completed_year_rows.delta_r >= 0).sum()) if len(completed_year_rows) else 0
    fill_ok = True
    if len(completed_year_rows):
        ratios = completed_year_rows.candidate_fill_rate / completed_year_rows.midpoint_fill_rate.replace(0, np.nan)
        fill_ok = bool((ratios.fillna(1.0) >= 0.5).all() or (completed_year_rows.delta_r > 0).all())
    decision = "KEEP_MIDPOINT_RESEARCH_ONLY"
    if (
        boot.get("low95") is not None and boot["low95"] > 0
        and positive_years >= 3
        and all((pdlt[s]["mean_delta_r"] is not None and pdlt[s]["mean_delta_r"] >= 0) for s in SYMBOLS)
        and fill_ok
    ):
        decision = "STATIC_DEPTH_CANDIDATE_PASSES_HISTORICAL_GATE"

    through_2025 = sim[sim.year <= 2025]
    latest_training_depth = choose_depth(through_2025)
    mid = table_completed[np.isclose(table_completed.depth, 0.50)].iloc[0].to_dict() if np.isclose(table_completed.depth, 0.50).any() else {}
    best_descriptive = table_completed.sort_values("opportunity_expectancy_r", ascending=False).iloc[0].to_dict()

    summary = {
        "study": "V2 v1.9 POI Penetration Lab",
        "protocol": "reports/v19/V19_POI_PENETRATION_PROTOCOL.md",
        "symbols": list(SYMBOLS),
        "setups": int(len(setups)),
        "simulation_rows": int(len(sim)),
        "depth_grid": [float(x) for x in DEPTHS],
        "completed_years": list(COMPLETED_YEARS),
        "midpoint_completed": mid,
        "best_descriptive_completed": best_descriptive,
        "walkforward": yearly.to_dict(orient="records"),
        "walkforward_completed_bootstrap_candidate_minus_midpoint": boot,
        "walkforward_completed_pair_delta": pdlt,
        "walkforward_noninferior_years": positive_years,
        "latest_training_depth_through_2025": latest_training_depth,
        "decision": decision,
        "interpretation": "OHLC structural proxy only; no broker bid/ask or queue execution truth.",
    }

    setups.to_csv(args.out / "v19_poi_setups.csv", index=False)
    sim.to_csv(args.out / "v19_poi_depth_simulations.csv", index=False)
    table_all.to_csv(args.out / "v19_depth_table_all.csv", index=False)
    table_completed.to_csv(args.out / "v19_depth_table_completed_2022_2025.csv", index=False)
    first_touch.to_csv(args.out / "v19_first_touch_states.csv", index=False)
    yearly.to_csv(args.out / "v19_walkforward_yearly.csv", index=False)
    paired.to_csv(args.out / "v19_walkforward_paired.csv", index=False)
    (args.out / "v19_poi_penetration_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
