from __future__ import annotations

"""V2 v1.4 research: time-to-POI revisit and late-entry outcomes.

This study does NOT tune the V2 detector. It freezes sweep -> BOS -> POI geometry,
then asks a separate question: after a valid fresh POI exists, how long does price
take to revisit the 50% midpoint and what happens to trades that fill later?

Key discipline:
- candidate detection is independent of the waiting horizon;
- horizons are evaluated after the candidate set is frozen;
- right-censored observations remain censored rather than being called failures;
- unfilled-at-8-bars is not called structural invalidation;
- pre-entry extension is measured before the midpoint fill and never uses post-entry data;
- broker execution truth is still unavailable, so results remain paper research.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import public_data_v2_proxy as proxy

HORIZONS = [8, 12, 16, 24, 32, 48]
MAX_FOLLOW = max(HORIZONS)


def _touches(row: pd.Series, price: float) -> bool:
    return float(row.low) <= price <= float(row.high)


def detect_candidates(m15_raw: pd.DataFrame, m5: pd.DataFrame | None, symbol: str) -> pd.DataFrame:
    cfg = proxy.ProxyConfig()
    df = proxy.add_causal_features(m15_raw, cfg)
    records: list[dict] = []
    warm = max(cfg.swing_lookback, cfg.bos_lookback, cfg.atr_period) + 2

    for i in range(warm, len(df) - 2):
        r = df.iloc[i]
        atr = float(r.atr) if pd.notna(r.atr) else np.nan
        if not np.isfinite(atr) or atr <= 0:
            continue

        candidates: list[tuple[str, float]] = []
        prev_low = float(r.prev_swing_low) if pd.notna(r.prev_swing_low) else np.nan
        prev_high = float(r.prev_swing_high) if pd.notna(r.prev_swing_high) else np.nan
        if np.isfinite(prev_low) and float(r.low) < prev_low - cfg.sweep_min_atr * atr and float(r.close) > prev_low:
            candidates.append(("long", prev_low))
        if np.isfinite(prev_high) and float(r.high) > prev_high + cfg.sweep_min_atr * atr and float(r.close) < prev_high:
            candidates.append(("short", prev_high))

        for direction, swept_level in candidates:
            bos_level = float(r.bos_up_level if direction == "long" else r.bos_dn_level)
            if not np.isfinite(bos_level):
                continue
            bos_i = None
            for j in range(i + 1, min(len(df), i + 1 + cfg.max_bos_bars)):
                c = float(df.iloc[j].close)
                if (direction == "long" and c > bos_level) or (direction == "short" and c < bos_level):
                    bos_i = j
                    break
            if bos_i is None:
                continue

            poi = proxy.find_poi(df, i, bos_i, direction)
            if poi is None:
                continue
            poi_i, zone_low, zone_high = poi
            if not zone_high > zone_low:
                continue

            entry = (zone_low + zone_high) / 2.0
            sweep_extreme = float(r.low if direction == "long" else r.high)
            stop = sweep_extreme - cfg.stop_buffer_atr * atr if direction == "long" else sweep_extreme + cfg.stop_buffer_atr * atr
            risk = entry - stop if direction == "long" else stop - entry
            risk_atr = risk / atr if atr > 0 else np.nan
            if not np.isfinite(risk_atr) or risk <= 0 or not (cfg.min_risk_atr <= risk_atr <= cfg.max_risk_atr):
                continue
            target = entry + cfg.reward_r * risk if direction == "long" else entry - cfg.reward_r * risk

            available = max(0, len(df) - 1 - bos_i)
            end_i = min(len(df) - 1, bos_i + MAX_FOLLOW)
            zone_touch_i = None
            midpoint_i = None
            for k in range(bos_i + 1, end_i + 1):
                bar = df.iloc[k]
                if zone_touch_i is None and float(bar.low) <= zone_high and float(bar.high) >= zone_low:
                    zone_touch_i = k
                if midpoint_i is None and _touches(bar, entry):
                    midpoint_i = k
                    break

            bars_to_zone = (zone_touch_i - bos_i) if zone_touch_i is not None else np.nan
            bars_to_mid = (midpoint_i - bos_i) if midpoint_i is not None else np.nan
            shallow_before_mid = bool(zone_touch_i is not None and midpoint_i is not None and zone_touch_i < midpoint_i)

            # Point-in-time pre-entry extension: how far the market moved in the intended
            # direction after BOS but BEFORE the first midpoint fill. This detects cases
            # where the original directional move may already have delivered the planned TP.
            pre_end = (midpoint_i - 1) if midpoint_i is not None else end_i
            pre = df.iloc[bos_i + 1 : pre_end + 1] if pre_end >= bos_i + 1 else df.iloc[0:0]
            if len(pre):
                if direction == "long":
                    pre_fav_r = (float(pre.high.max()) - entry) / risk
                else:
                    pre_fav_r = (entry - float(pre.low.min())) / risk
            else:
                pre_fav_r = 0.0
            pre_target_reached = bool(pre_fav_r >= cfg.reward_r)

            outcome = f"unfilled_{MAX_FOLLOW}"
            gross_r = np.nan
            net_r = np.nan
            exit_time = pd.NaT
            used_5m = False
            bars_held = np.nan
            if midpoint_i is not None:
                outcome, exit_time, held, used_5m = proxy.resolve_m15_outcome(df, m5, midpoint_i, direction, entry, stop, target, cfg.max_hold_bars)
                bars_held = held
                if outcome.startswith("ambiguous"):
                    gross_r = np.nan
                elif outcome == "win":
                    gross_r = cfg.reward_r
                elif outcome == "loss":
                    gross_r = -1.0
                else:
                    final_i = min(len(df) - 1, midpoint_i + cfg.max_hold_bars)
                    final_close = float(df.iloc[final_i].close)
                    raw_r = (final_close - entry) / risk if direction == "long" else (entry - final_close) / risk
                    gross_r = float(np.clip(raw_r, -1.0, cfg.reward_r))
                cost = proxy.SYMBOL_COST[symbol]["spread"] + proxy.SYMBOL_COST[symbol]["slippage"]
                if np.isfinite(gross_r):
                    net_r = float(gross_r - cost / risk)

            records.append({
                "candidate_id": f"WAIT_{symbol}_{pd.Timestamp(r.date).strftime('%Y%m%d_%H%M')}_{direction}",
                "symbol": symbol,
                "direction": direction,
                "sweep_time": pd.Timestamp(r.date),
                "bos_time": pd.Timestamp(df.iloc[bos_i].date),
                "poi_time": pd.Timestamp(df.iloc[poi_i].date),
                "poi_low": zone_low,
                "poi_high": zone_high,
                "entry": entry,
                "stop": stop,
                "target": target,
                "atr": atr,
                "risk_atr": risk_atr,
                "available_follow_bars": available,
                "zone_touch_bars": bars_to_zone,
                "midpoint_fill_bars": bars_to_mid,
                "filled_within_follow": midpoint_i is not None,
                "shallow_zone_touch_before_midpoint": shallow_before_mid,
                "pre_entry_favorable_r": pre_fav_r,
                "pre_entry_target_reached": pre_target_reached,
                "outcome": outcome,
                "gross_r": gross_r,
                "net_r": net_r,
                "exit_time": exit_time,
                "bars_held": bars_held,
                "used_5m_resolution": used_5m,
            })

    out = pd.DataFrame(records)
    if not out.empty:
        out = out.drop_duplicates(["symbol", "direction", "sweep_time", "bos_time"], keep="first")
        out = out.sort_values(["sweep_time", "symbol", "direction"]).reset_index(drop=True)
    return out


def horizon_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [("ALL", df)] + [(s, g) for s, g in df.groupby("symbol")]
    for symbol, g in groups:
        prev_h = 0
        for h in HORIZONS:
            eligible = g[g.available_follow_bars >= h].copy()
            if eligible.empty:
                continue
            filled = eligible[eligible.midpoint_fill_bars.notna() & (eligible.midpoint_fill_bars <= h)]
            late = eligible[eligible.midpoint_fill_bars.notna() & (eligible.midpoint_fill_bars > prev_h) & (eligible.midpoint_fill_bars <= h)]
            resolved = filled[filled.net_r.notna()]
            late_resolved = late[late.net_r.notna()]
            rows.append({
                "symbol": symbol,
                "horizon_bars": h,
                "horizon_hours": h * 0.25,
                "eligible_candidates": len(eligible),
                "fills": len(filled),
                "fill_rate": len(filled) / len(eligible),
                "incremental_fills_vs_prior_horizon": len(late),
                "filled_net_r_mean": resolved.net_r.mean() if len(resolved) else np.nan,
                "filled_win_rate": (resolved.outcome == "win").mean() if len(resolved) else np.nan,
                "candidate_avg_net_r_unfilled_zero": resolved.net_r.sum() / len(eligible) if len(eligible) else np.nan,
                "late_bucket_net_r_mean": late_resolved.net_r.mean() if len(late_resolved) else np.nan,
                "late_bucket_win_rate": (late_resolved.outcome == "win").mean() if len(late_resolved) else np.nan,
                "late_bucket_resolved": len(late_resolved),
            })
            prev_h = h
    return pd.DataFrame(rows)


def survival_curve(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [("ALL", df)] + [(s, g) for s, g in df.groupby("symbol")]
    for symbol, g in groups:
        times, events = [], []
        for _, r in g.iterrows():
            avail = min(int(r.available_follow_bars), MAX_FOLLOW)
            if avail <= 0:
                continue
            if pd.notna(r.midpoint_fill_bars) and int(r.midpoint_fill_bars) <= avail:
                times.append(int(r.midpoint_fill_bars)); events.append(1)
            else:
                times.append(avail); events.append(0)
        if not times:
            continue
        surv = 1.0
        for t in range(1, MAX_FOLLOW + 1):
            risk = sum(x >= t for x in times)
            ev = sum(e == 1 and x == t for x, e in zip(times, events))
            if risk:
                hazard = ev / risk
                surv *= (1.0 - hazard)
            else:
                hazard = np.nan
            rows.append({"symbol": symbol, "bar": t, "hours": t * 0.25, "at_risk": risk, "fills_at_bar": ev, "hazard": hazard, "survival_not_filled": surv, "cumulative_fill_probability": 1.0 - surv})
    return pd.DataFrame(rows)


def shallow_touch_summary(df: pd.DataFrame) -> pd.DataFrame:
    x = df[df.midpoint_fill_bars.notna()].copy()
    rows = []
    for label, g in [("direct_or_same_bar_midpoint", x[~x.shallow_zone_touch_before_midpoint]), ("shallow_touch_then_later_midpoint", x[x.shallow_zone_touch_before_midpoint])]:
        resolved = g[g.net_r.notna()]
        rows.append({"group": label, "fills": len(g), "resolved": len(resolved), "median_midpoint_fill_bars": g.midpoint_fill_bars.median() if len(g) else np.nan, "net_r_mean": resolved.net_r.mean() if len(resolved) else np.nan, "win_rate": (resolved.outcome == "win").mean() if len(resolved) else np.nan})
    return pd.DataFrame(rows)


def extension_summary(df: pd.DataFrame) -> pd.DataFrame:
    x = df[df.midpoint_fill_bars.notna()].copy()
    rows = []
    buckets = [
        ("target_not_reached_before_entry", x[~x.pre_entry_target_reached]),
        ("target_already_reached_before_entry", x[x.pre_entry_target_reached]),
        ("pre_extension_lt_1R", x[x.pre_entry_favorable_r < 1]),
        ("pre_extension_1_to_2_5R", x[(x.pre_entry_favorable_r >= 1) & (x.pre_entry_favorable_r < 2.5)]),
        ("pre_extension_2_5_to_5R", x[(x.pre_entry_favorable_r >= 2.5) & (x.pre_entry_favorable_r < 5)]),
        ("pre_extension_ge_5R", x[x.pre_entry_favorable_r >= 5]),
    ]
    for label, g in buckets:
        resolved = g[g.net_r.notna()]
        rows.append({
            "group": label,
            "fills": len(g),
            "resolved": len(resolved),
            "median_fill_bars": g.midpoint_fill_bars.median() if len(g) else np.nan,
            "median_pre_entry_favorable_r": g.pre_entry_favorable_r.median() if len(g) else np.nan,
            "net_r_mean": resolved.net_r.mean() if len(resolved) else np.nan,
            "win_rate": (resolved.outcome == "win").mean() if len(resolved) else np.nan,
        })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frames = []
    for symbol in ["EURUSD", "GBPUSD"]:
        m15 = proxy.load_market(args.data_dir / f"{symbol}-15m.feather", symbol)
        m5_path = args.data_dir / f"{symbol}-5m.feather"
        m5 = proxy.load_market(m5_path, symbol) if m5_path.exists() else None
        frames.append(detect_candidates(m15, m5, symbol))
    candidates = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    horizons = horizon_summary(candidates)
    survival = survival_curve(candidates)
    shallow = shallow_touch_summary(candidates)
    extension = extension_summary(candidates)

    candidates.to_csv(args.out / "v14_poi_candidates.csv", index=False)
    horizons.to_csv(args.out / "v14_waiting_horizons.csv", index=False)
    survival.to_csv(args.out / "v14_survival_curve.csv", index=False)
    shallow.to_csv(args.out / "v14_shallow_touch.csv", index=False)
    extension.to_csv(args.out / "v14_pre_entry_extension.csv", index=False)

    all_h = horizons[horizons.symbol == "ALL"].copy()
    h8 = all_h[all_h.horizon_bars == 8].iloc[0] if (all_h.horizon_bars == 8).any() else None
    h24 = all_h[all_h.horizon_bars == 24].iloc[0] if (all_h.horizon_bars == 24).any() else None
    h48 = all_h[all_h.horizon_bars == 48].iloc[0] if (all_h.horizon_bars == 48).any() else None

    decision = "KEEP_8_PENDING_RESEARCH"
    rationale = "Insufficient comparable results."
    if h8 is not None and h24 is not None:
        extra = float(h24.fill_rate - h8.fill_rate)
        late_rows = all_h[all_h.horizon_bars.isin([12, 16, 24])]
        late_n = int(late_rows.late_bucket_resolved.sum())
        late_weighted = np.nan
        if late_n:
            late_weighted = float(np.nansum(late_rows.late_bucket_net_r_mean * late_rows.late_bucket_resolved) / late_n)
        if extra >= 0.05 and late_n >= 30 and np.isfinite(late_weighted) and late_weighted > 0:
            decision = "REPLACE_8_BAR_EXPIRY_WITH_LIFECYCLE_WAIT"
            rationale = f"24-bar waiting recovers {extra:.1%} additional fills and 8-24-bar late fills retain positive mean net R ({late_weighted:.3f}R) in the public proxy."
        else:
            rationale = f"24-bar incremental fill={extra:.1%}; resolved late-fill n={late_n}; weighted late mean R={late_weighted if np.isfinite(late_weighted) else None}."

    summary = {
        "study": "V2 v1.4 POI waiting-time survival study",
        "candidate_count": int(len(candidates)),
        "symbols": candidates.symbol.value_counts().to_dict() if len(candidates) else {},
        "decision": decision,
        "rationale": rationale,
        "horizon_8": h8.to_dict() if h8 is not None else None,
        "horizon_24": h24.to_dict() if h24 is not None else None,
        "horizon_48": h48.to_dict() if h48 is not None else None,
        "principle": "Time without a fill is censoring/staleness, not structural invalidation. Structural invalidation must be defined separately.",
        "execution_warning": "Public completed-bar proxy only; broker executable bid/ask truth remains unavailable.",
    }
    (args.out / "v14_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print(json.dumps(summary, indent=2, default=str))
    print("\nHORIZONS\n", horizons.to_string(index=False))
    print("\nSHALLOW TOUCH\n", shallow.to_string(index=False))
    print("\nPRE-ENTRY EXTENSION\n", extension.to_string(index=False))


if __name__ == "__main__":
    main()
