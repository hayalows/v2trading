from __future__ import annotations

"""V2 v2.4 exit / break-even / partial-profit research.

Protocol: reports/v24/V24_EXIT_RISK_PROTOCOL.md
Research only. Public M15/M5 OHLC is not broker execution truth.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from public_data_v2_proxy import load_market, SYMBOL_COST
from v19_poi_penetration_research import detect_pois

SYMBOLS = ("EURUSD", "GBPUSD")
TEST_YEARS = (2022, 2023, 2024, 2025)
ENTRY_HORIZON = 192
HOLD_HORIZON = 1920
REWARD_R = 2.5
MIN_RISK_ATR = 0.08
MAX_RISK_ATR = 1.60
BASE_RISK_PCT = 0.01
START_EQUITY = 500.0

POLICIES: dict[str, dict[str, Any]] = {
    "timeout_48": {"timeout": 48},
    "timeout_96": {"timeout": 96},
    "timeout_192": {"timeout": 192},
    "hold_sltp": {"timeout": None},
    "be_075": {"trigger": 0.75, "partial": 0.0},
    "be_100": {"trigger": 1.00, "partial": 0.0},
    "be_125": {"trigger": 1.25, "partial": 0.0},
    "be_150": {"trigger": 1.50, "partial": 0.0},
    "p25_100_be": {"trigger": 1.00, "partial": 0.25},
    "p33_100_be": {"trigger": 1.00, "partial": 0.33},
    "p50_100_be": {"trigger": 1.00, "partial": 0.50},
    "p25_150_be": {"trigger": 1.50, "partial": 0.25},
    "p33_150_be": {"trigger": 1.50, "partial": 0.33},
    "p50_150_be": {"trigger": 1.50, "partial": 0.50},
}


def touch(row: pd.Series, level: float) -> bool:
    return float(row.low) <= level <= float(row.high)


def level_for_r(direction: str, entry: float, risk: float, r: float) -> float:
    return entry + r * risk if direction == "long" else entry - r * risk


def m15_entry(df: pd.DataFrame, setup: pd.Series) -> int | None:
    entry = (float(setup.poi_low) + float(setup.poi_high)) / 2.0
    start = int(setup.bos_i) + 1
    end = min(len(df), start + ENTRY_HORIZON)
    for i in range(start, end):
        if touch(df.iloc[i], entry):
            return i
    return None


def m5_start_index(m5: pd.DataFrame, m15_ts: pd.Timestamp, direction: str, entry: float) -> int | None:
    end = m15_ts + pd.Timedelta(minutes=15)
    start_i = int(m5.date.searchsorted(m15_ts, side="left"))
    end_i = int(m5.date.searchsorted(end, side="left"))
    for i in range(start_i, min(end_i, len(m5))):
        if touch(m5.iloc[i], entry):
            return i
    return None


def mtm_r(direction: str, close: float, entry: float, risk: float) -> float:
    raw = (close - entry) / risk if direction == "long" else (entry - close) / risk
    return float(np.clip(raw, -1.0, REWARD_R))


def simulate_policy(m15: pd.DataFrame, m5: pd.DataFrame, setup: pd.Series, policy_name: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    direction = str(setup.direction)
    entry = (float(setup.poi_low) + float(setup.poi_high)) / 2.0
    stop = float(setup.stop)
    atr = float(setup.atr)
    risk = entry - stop if direction == "long" else stop - entry
    risk_atr = risk / atr if atr > 0 else np.nan
    if not (np.isfinite(risk_atr) and risk > 0 and MIN_RISK_ATR <= risk_atr <= MAX_RISK_ATR):
        return None

    entry_i = m15_entry(m15, setup)
    if entry_i is None:
        return None
    entry_ts = pd.Timestamp(m15.iloc[entry_i].date)
    m5_i = m5_start_index(m5, entry_ts, direction, entry)
    if m5_i is None:
        return {"setup_id": setup.setup_id, "symbol": setup.symbol, "direction": direction, "year": int(setup.year), "entry_time": entry_ts, "policy": policy_name, "status": "ambiguous_entry_source", "gross_r": np.nan, "net_r": np.nan, "bars_held": np.nan, "risk_atr": risk_atr, "cost_as_r": np.nan}

    target = level_for_r(direction, entry, risk, REWARD_R)
    trigger_r = policy.get("trigger")
    partial = float(policy.get("partial", 0.0))
    trigger = level_for_r(direction, entry, risk, float(trigger_r)) if trigger_r is not None else None
    timeout = policy.get("timeout")
    max_bars = int(timeout) if timeout is not None else HOLD_HORIZON
    deadline_ts = entry_ts + pd.Timedelta(minutes=15 * max_bars)
    end_m5_i = int(m5.date.searchsorted(deadline_ts, side="left"))
    path = m5.iloc[m5_i:min(end_m5_i, len(m5))]
    if path.empty:
        return None

    active_be = False
    realized = 0.0
    remaining = 1.0
    partial_done = False
    exit_time = None
    status = None
    gross_r = np.nan

    for _, row in path.iterrows():
        lo, hi = float(row.low), float(row.high)
        hit_orig_stop = lo <= stop if direction == "long" else hi >= stop
        hit_be = lo <= entry if direction == "long" else hi >= entry
        hit_tp = hi >= target if direction == "long" else lo <= target
        hit_trigger = False
        if trigger is not None and not active_be:
            hit_trigger = hi >= trigger if direction == "long" else lo <= trigger

        if not active_be:
            if hit_orig_stop and (hit_tp or hit_trigger):
                status = "ambiguous_5m"; exit_time = pd.Timestamp(row.date); break
            if hit_orig_stop:
                gross_r = -1.0; status = "loss"; exit_time = pd.Timestamp(row.date); break
            if hit_tp:
                if trigger is not None and partial > 0:
                    realized = partial * float(trigger_r); remaining = 1.0 - partial
                    gross_r = realized + remaining * REWARD_R; partial_done = True; status = "target"
                else:
                    gross_r = REWARD_R; status = "target"
                exit_time = pd.Timestamp(row.date); break
            if hit_trigger:
                if hit_be:
                    status = "ambiguous_5m"; exit_time = pd.Timestamp(row.date); break
                active_be = True
                if partial > 0:
                    realized = partial * float(trigger_r); remaining = 1.0 - partial; partial_done = True
                continue
        else:
            if hit_be and hit_tp:
                status = "ambiguous_5m"; exit_time = pd.Timestamp(row.date); break
            if hit_be:
                gross_r = realized; status = "breakeven_after_trigger" if partial == 0 else "partial_then_be"; exit_time = pd.Timestamp(row.date); break
            if hit_tp:
                gross_r = realized + remaining * REWARD_R; status = "target_after_be" if partial == 0 else "partial_then_target"; exit_time = pd.Timestamp(row.date); break

    if status is None:
        if timeout is not None:
            bar_end = min(len(m15) - 1, entry_i + int(timeout))
            close = float(m15.iloc[bar_end].close)
            gross_r = realized + remaining * mtm_r(direction, close, entry, risk)
            status = "timeout"; exit_time = pd.Timestamp(m15.iloc[bar_end].date)
        else:
            status = "censored_hold"; exit_time = pd.Timestamp(path.iloc[-1].date)

    base_cost = float(SYMBOL_COST[str(setup.symbol)]["spread"] + SYMBOL_COST[str(setup.symbol)]["slippage"])
    cost_as_r = base_cost / risk
    stressed_cost_as_r = cost_as_r * (1.0 + (partial if partial_done else 0.0))
    net_r = float(gross_r - stressed_cost_as_r) if np.isfinite(gross_r) else np.nan
    held = (exit_time - entry_ts).total_seconds() / 900.0 if exit_time is not None else np.nan
    return {"setup_id": setup.setup_id, "symbol": setup.symbol, "direction": direction, "year": int(setup.year), "entry_time": entry_ts, "exit_time": exit_time, "policy": policy_name, "status": status, "gross_r": gross_r, "net_r": net_r, "bars_held": held, "risk_atr": risk_atr, "cost_as_r": stressed_cost_as_r}


def equity_stats(g: pd.DataFrame, risk_pct: float = BASE_RISK_PCT) -> dict[str, float | None]:
    x = g[np.isfinite(g.net_r)].sort_values(["entry_time", "setup_id"]).copy()
    if x.empty:
        return {"final_equity": None, "max_drawdown": None, "log_growth": None}
    eq = START_EQUITY; peak = eq; max_dd = 0.0; log_g = 0.0
    for r in x.net_r.astype(float):
        mult = max(1e-9, 1.0 + risk_pct * r)
        eq *= mult; log_g += float(np.log(mult)); peak = max(peak, eq); max_dd = max(max_dd, (peak - eq) / peak)
    return {"final_equity": float(eq), "max_drawdown": float(max_dd), "log_growth": float(log_g)}


def summarize(g: pd.DataFrame) -> dict[str, Any]:
    scored = g[np.isfinite(g.net_r)].copy(); e = equity_stats(scored, BASE_RISK_PCT)
    if scored.empty: return {"n": 0, **e}
    wins = scored.net_r > 0; losses = scored.net_r < 0
    gains = scored.loc[wins, "net_r"].sum(); pain = -scored.loc[losses, "net_r"].sum()
    return {"n": int(len(scored)), "ambiguous_or_censored": int((~np.isfinite(g.net_r)).sum()), "mean_net_r": float(scored.net_r.mean()), "median_net_r": float(scored.net_r.median()), "positive_rate": float(wins.mean()), "loss_rate": float(losses.mean()), "zeroish_rate": float((scored.net_r.abs() < 0.03).mean()), "target_rate": float(scored.status.str.contains("target").mean()), "profit_factor": float(gains / pain) if pain > 0 else None, **e}


def walk_forward(rows: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for year in TEST_YEARS:
        train = rows[(rows.year < year) & np.isfinite(rows.net_r)].copy(); test = rows[(rows.year == year) & np.isfinite(rows.net_r)].copy(); choices = []
        for name, g in train.groupby("policy"):
            if len(g) < 100: continue
            st = summarize(g); choices.append((float(st["log_growth"] or -1e9), -float(st["max_drawdown"] or 1.0), float(st["mean_net_r"] or -1e9), name))
        if not choices: continue
        choices.sort(reverse=True); selected = choices[0][3]
        for name in [selected, "timeout_48", "hold_sltp"]:
            g = test[test.policy == name]; st = summarize(g)
            out.append({"year": year, "role": "selected" if name == selected else "comparator", "policy": name, **st})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", type=Path, required=True); ap.add_argument("--out", type=Path, required=True); ap.add_argument("--start", default="2020-01-01"); args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    all_rows = []; setup_counts = {}
    for symbol in SYMBOLS:
        m15 = load_market(args.data_dir / f"{symbol}-15m.feather", symbol); m5 = load_market(args.data_dir / f"{symbol}-5m.feather", symbol)
        start = pd.Timestamp(args.start, tz="UTC"); m15 = m15[m15.date >= start].reset_index(drop=True); m5 = m5[m5.date >= start].reset_index(drop=True)
        setups = detect_pois(m15, symbol); setup_counts[symbol] = int(len(setups))
        for _, s in setups.iterrows():
            for name, policy in POLICIES.items():
                rec = simulate_policy(m15, m5, s, name, policy)
                if rec is not None: all_rows.append(rec)
    rows = pd.DataFrame(all_rows); rows.to_csv(args.out / "v24_exit_policy_rows.csv", index=False)
    completed = rows[rows.year.isin(TEST_YEARS)].copy(); summary = {name: summarize(g) for name, g in completed.groupby("policy")}; yearly = {str(y): {name: summarize(g) for name, g in completed[completed.year == y].groupby("policy")} for y in TEST_YEARS}; wf = walk_forward(rows)
    risk_overlays = {str(rp): {name: equity_stats(g[np.isfinite(g.net_r)], rp) for name, g in completed.groupby("policy")} for rp in [0.005, 0.01, 0.015, 0.02]}
    payload = {"protocol": "V24_EXIT_RISK_PROTOCOL", "setup_counts": setup_counts, "rows": int(len(rows)), "completed_rows": int(len(completed)), "summary": summary, "yearly": yearly, "walk_forward": wf, "risk_overlays": risk_overlays, "boundaries": ["Public OHLC/M5 structural proxy only.", "No broker bid/ask execution truth.", "M5 same-candle unresolved ordering remains ambiguous.", "Partial exits receive an extra friction stress but exact broker costs are unknown."]}
    (args.out / "v24_exit_policy_summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    ranked = sorted(summary.items(), key=lambda kv: (kv[1].get("log_growth") or -1e9), reverse=True)
    lines = ["# V2 v2.4 Exit / Break-even / Partial Profit Results", "", "Research only. Protocol was frozen before this run.", "", f"- Reconstructed Stage-6 setups: {sum(setup_counts.values()):,}", f"- Policy simulation rows: {len(rows):,}", "", "## Completed 2022-2025 policy ranking at 1% risk", "", "| Policy | n | Mean net R | Positive | Full target | $500 final equity | Max DD |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, st in ranked:
        lines.append(f"| {name} | {st.get('n',0)} | {st.get('mean_net_r',float('nan')):.4f} | {100*st.get('positive_rate',0):.1f}% | {100*st.get('target_rate',0):.1f}% | ${st.get('final_equity',float('nan')):.2f} | {100*st.get('max_drawdown',0):.2f}% |")
    lines += ["", "## Chronological walk-forward selections", ""]
    for r in wf:
        if r["role"] == "selected": lines.append(f"- {r['year']}: prior-history selection `{r['policy']}` -> {r.get('mean_net_r', float('nan')):.4f}R mean, ${r.get('final_equity', float('nan')):.2f} from the $500 yearly-reset reporting base.")
    lines += ["", "## Interpretation rule", "", "Descriptive ranking is not enough to replace the baseline. The chronological walk-forward record and prospective shadow sample control any future promotion.", "", "## Risk", "", "1.00% remains the reporting baseline. 1.50% and 2.00% are exposure overlays only; a win streak does not activate them.", "", "## Boundary", "", "The v0.4 executable-label failure remains in force. These results are public-data research, not live-money validation."]
    (args.out / "V24_EXIT_POLICY_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
