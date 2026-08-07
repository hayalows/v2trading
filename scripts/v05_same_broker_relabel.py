from __future__ import annotations

"""Relabel original V2 trades from the same MT5 broker export.

Preferred path: direct bid/ask ticks from ``v05_mt5_export.py``.
Fallback path: broker M1 bid OHLC plus the bar spread field. Fallback labels are marked
lower quality and any same-minute stop/target ordering ambiguity is retained rather
than guessed.
"""

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

COL_ALIASES = {
    "symbol": ["symbol", "instrument", "ticker", "pair"],
    "direction": ["direction", "side", "trade_direction"],
    "entry_time": ["entry_time", "entry_datetime", "open_time", "time_entry", "entry_timestamp"],
    "exit_time": ["exit_time", "exit_datetime", "close_time", "time_exit", "exit_timestamp"],
    "entry": ["entry", "entry_price", "price_entry", "open_price", "entry_level"],
    "stop": ["stop", "stop_price", "stop_loss", "sl", "sl_price"],
    "target": ["target", "target_price", "take_profit", "tp", "tp_price"],
    "net_r": ["net_r", "r", "result_r", "realized_r", "pnl_r"],
    "outcome": ["outcome", "result", "trade_outcome", "label"],
    "setup_id": ["setup_id", "trade_id", "id", "signal_id"],
}


def norm_name(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


def find_col(frame: pd.DataFrame, logical: str, required: bool = True) -> str | None:
    lookup = {norm_name(c): c for c in frame.columns}
    for candidate in COL_ALIASES[logical]:
        hit = lookup.get(norm_name(candidate))
        if hit is not None:
            return hit
    if required:
        raise ValueError(f"Could not find {logical!r} column. Tried {COL_ALIASES[logical]}; columns={list(frame.columns)}")
    return None


def normalize_direction(v: object) -> str:
    s = str(v).strip().lower()
    if s in {"long", "buy", "bull", "bullish", "1"}:
        return "long"
    if s in {"short", "sell", "bear", "bearish", "-1"}:
        return "short"
    raise ValueError(f"Unknown direction {v!r}")


def normalize_outcome(v: object, net_r: float | None) -> str:
    s = str(v).strip().lower() if v is not None and not pd.isna(v) else ""
    if s in {"win", "winner", "tp", "profit", "1", "true"}:
        return "win"
    if s in {"loss", "loser", "sl", "stop", "0", "false"}:
        return "loss"
    if net_r is not None and np.isfinite(net_r):
        return "win" if net_r > 0 else "loss"
    return "unknown"


@dataclass
class Trade:
    setup_id: str
    symbol: str
    direction: str
    entry_time: pd.Timestamp
    entry: float
    stop: float
    target: float
    source_outcome: str
    source_net_r: float | None

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)


def load_ledger(path: Path, reward_r: float = 2.5) -> pd.DataFrame:
    if path.suffix.lower() in {".parquet", ".pq"}:
        raw = pd.read_parquet(path)
    else:
        raw = pd.read_csv(path, low_memory=False)
    cols = {k: find_col(raw, k, required=k not in {"exit_time", "target", "net_r", "outcome", "setup_id"}) for k in COL_ALIASES}
    rows = []
    for i, r in raw.iterrows():
        try:
            direction = normalize_direction(r[cols["direction"]])
            entry = float(r[cols["entry"]])
            stop = float(r[cols["stop"]])
            risk = abs(entry - stop)
            if not np.isfinite(risk) or risk <= 0:
                continue
            target = np.nan
            if cols["target"] is not None:
                target = pd.to_numeric(pd.Series([r[cols["target"]]]), errors="coerce").iloc[0]
            if not np.isfinite(target):
                target = entry + reward_r * risk if direction == "long" else entry - reward_r * risk
            net_r = None
            if cols["net_r"] is not None:
                x = pd.to_numeric(pd.Series([r[cols["net_r"]]]), errors="coerce").iloc[0]
                net_r = float(x) if np.isfinite(x) else None
            outcome_value = r[cols["outcome"]] if cols["outcome"] is not None else None
            ts = pd.to_datetime(r[cols["entry_time"]], utc=True, errors="coerce")
            if pd.isna(ts):
                continue
            sid = str(r[cols["setup_id"]]) if cols["setup_id"] is not None else f"LEDGER_{i:06d}"
            rows.append({
                "setup_id": sid,
                "symbol": str(r[cols["symbol"]]).strip().upper(),
                "direction": direction,
                "entry_time": ts,
                "entry": entry,
                "stop": stop,
                "target": float(target),
                "risk_distance": risk,
                "source_outcome": normalize_outcome(outcome_value, net_r),
                "source_net_r": net_r,
            })
        except (ValueError, TypeError):
            continue
    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("No usable trades found in ledger after column mapping")
    return out.sort_values("entry_time").reset_index(drop=True)


class SameBrokerStore:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.point: dict[str, float] = {}
        for sym, meta in self.manifest.get("symbols", {}).items():
            self.point[sym.upper()] = float(meta.get("metadata", {}).get("point") or np.nan)
        self._m1: dict[str, pd.DataFrame] = {}
        self._ticks: dict[tuple[str, str], pd.DataFrame] = {}

    def has_symbol(self, symbol: str) -> bool:
        return symbol.upper() in {s.upper() for s in self.manifest.get("symbols", {})}

    def m1(self, symbol: str) -> pd.DataFrame:
        s = symbol.upper()
        if s not in self._m1:
            p = self.root / s / "bars" / "M1.parquet"
            if not p.exists():
                # Exporter sanitizes research symbol but normally this is identical.
                matches = list(self.root.glob(f"*/bars/M1.parquet"))
                p = next((x for x in matches if x.parents[1].name.upper() == s), p)
            f = pd.read_parquet(p)
            f["time"] = pd.to_datetime(f.time, utc=True)
            self._m1[s] = f.sort_values("time").reset_index(drop=True)
        return self._m1[s]

    def ticks_for_window(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        s = symbol.upper()
        days = pd.date_range(start.floor("D"), end.floor("D"), freq="D", tz="UTC")
        frames = []
        for day in days:
            ds = day.date().isoformat()
            key = (s, ds)
            if key not in self._ticks:
                p = self.root / s / "ticks" / f"date={ds}" / "ticks.parquet"
                if not p.exists():
                    self._ticks[key] = pd.DataFrame()
                else:
                    f = pd.read_parquet(p)
                    f["time"] = pd.to_datetime(f.time, utc=True)
                    self._ticks[key] = f.sort_values("time").reset_index(drop=True)
            if not self._ticks[key].empty:
                frames.append(self._ticks[key])
        if not frames:
            return pd.DataFrame()
        f = pd.concat(frames, ignore_index=True)
        return f[(f.time >= start) & (f.time <= end)].copy()


def relabel_ticks(t: Trade, ticks: pd.DataFrame, max_hold_hours: float = 12.0) -> dict:
    if ticks.empty or not {"bid", "ask", "time"}.issubset(ticks.columns):
        return {"label_source": "no_ticks", "execution_outcome": "no_data", "filled": 0}
    w = ticks[(ticks.time >= t.entry_time) & (ticks.time <= t.entry_time + pd.Timedelta(hours=max_hold_hours))].copy()
    w = w[(pd.to_numeric(w.bid, errors="coerce") > 0) & (pd.to_numeric(w.ask, errors="coerce") > 0)]
    if w.empty:
        return {"label_source": "no_ticks", "execution_outcome": "no_data", "filled": 0}
    risk = t.risk
    fill_idx = None
    for idx, r in w.iterrows():
        if (t.direction == "long" and float(r.ask) <= t.entry) or (t.direction == "short" and float(r.bid) >= t.entry):
            fill_idx = idx
            break
    if fill_idx is None:
        return {"label_source": "tick_direct", "execution_outcome": "no_fill", "filled": 0,
                "spread_median_r": float(((w.ask-w.bid)/risk).median())}
    pos = w.index.get_loc(fill_idx)
    fill = w.loc[fill_idx]
    fill_price = min(float(fill.ask), t.entry) if t.direction == "long" else max(float(fill.bid), t.entry)
    fill_spread_r = (float(fill.ask) - float(fill.bid)) / risk
    after = w.iloc[pos:]
    for _, r in after.iterrows():
        bid, ask = float(r.bid), float(r.ask)
        if t.direction == "long":
            if bid <= t.stop:
                return {
                    "label_source": "tick_direct", "execution_outcome": "loss", "filled": 1,
                    "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": bid,
                    "execution_r": (bid-fill_price)/risk, "fill_spread_r": fill_spread_r,
                    "stop_slippage_r": max(0.0, t.stop-bid)/risk,
                    "spread_median_r": float(((after.ask-after.bid)/risk).median()),
                }
            if bid >= t.target:
                return {
                    "label_source": "tick_direct", "execution_outcome": "win", "filled": 1,
                    "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": t.target,
                    "execution_r": (t.target-fill_price)/risk, "fill_spread_r": fill_spread_r,
                    "stop_slippage_r": 0.0, "spread_median_r": float(((after.ask-after.bid)/risk).median()),
                }
        else:
            if ask >= t.stop:
                return {
                    "label_source": "tick_direct", "execution_outcome": "loss", "filled": 1,
                    "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": ask,
                    "execution_r": (fill_price-ask)/risk, "fill_spread_r": fill_spread_r,
                    "stop_slippage_r": max(0.0, ask-t.stop)/risk,
                    "spread_median_r": float(((after.ask-after.bid)/risk).median()),
                }
            if ask <= t.target:
                return {
                    "label_source": "tick_direct", "execution_outcome": "win", "filled": 1,
                    "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": t.target,
                    "execution_r": (fill_price-t.target)/risk, "fill_spread_r": fill_spread_r,
                    "stop_slippage_r": 0.0, "spread_median_r": float(((after.ask-after.bid)/risk).median()),
                }
    last = after.iloc[-1]
    mark = float(last.bid) if t.direction == "long" else float(last.ask)
    rr = (mark-fill_price)/risk if t.direction == "long" else (fill_price-mark)/risk
    return {"label_source": "tick_direct", "execution_outcome": "timeout", "filled": 1,
            "fill_time": fill.time, "exit_time": last.time, "fill_price": fill_price, "exit_price": mark,
            "execution_r": float(np.clip(rr, -2.0, 3.0)), "fill_spread_r": fill_spread_r,
            "stop_slippage_r": 0.0, "spread_median_r": float(((after.ask-after.bid)/risk).median())}


def relabel_m1(t: Trade, m1: pd.DataFrame, point: float, max_hold_hours: float = 12.0) -> dict:
    w = m1[(m1.time >= t.entry_time.floor("min")) & (m1.time <= t.entry_time + pd.Timedelta(hours=max_hold_hours))].copy()
    if w.empty:
        return {"label_source": "m1_spread_approx", "execution_outcome": "no_data", "filled": 0}
    if not np.isfinite(point) or point <= 0:
        point = max(abs(t.entry) * 1e-6, 1e-9)
    spread_px = pd.to_numeric(w.get("spread", 0), errors="coerce").fillna(0) * point
    w["ask_low"] = w.low + spread_px
    w["ask_high"] = w.high + spread_px
    risk = t.risk

    fill_pos = None
    for j, r in w.reset_index(drop=True).iterrows():
        if (t.direction == "long" and float(r.ask_low) <= t.entry) or (t.direction == "short" and float(r.high) >= t.entry):
            fill_pos = j
            break
    if fill_pos is None:
        return {"label_source": "m1_spread_approx", "execution_outcome": "no_fill", "filled": 0}
    w = w.reset_index(drop=True)
    for j in range(fill_pos, len(w)):
        r = w.iloc[j]
        if t.direction == "long":
            stop_hit, tp_hit = float(r.low) <= t.stop, float(r.high) >= t.target
        else:
            stop_hit, tp_hit = float(r.ask_high) >= t.stop, float(r.ask_low) <= t.target
        # Entry ordering inside the fill minute and stop-vs-target ordering cannot be known from M1 OHLC.
        if stop_hit and tp_hit:
            return {"label_source": "m1_spread_approx", "execution_outcome": "ambiguous_m1", "filled": 1}
        if j == fill_pos and (stop_hit or tp_hit):
            return {"label_source": "m1_spread_approx", "execution_outcome": "ambiguous_entry_minute", "filled": 1}
        if stop_hit:
            return {"label_source": "m1_spread_approx", "execution_outcome": "loss", "filled": 1,
                    "execution_r": -1.0, "fill_spread_r": float((spread_px.iloc[min(j, len(spread_px)-1)])/risk)}
        if tp_hit:
            return {"label_source": "m1_spread_approx", "execution_outcome": "win", "filled": 1,
                    "execution_r": abs(t.target-t.entry)/risk, "fill_spread_r": float((spread_px.iloc[min(j, len(spread_px)-1)])/risk)}
    return {"label_source": "m1_spread_approx", "execution_outcome": "timeout", "filled": 1}


def quality(rec: dict) -> str:
    outcome = rec.get("execution_outcome")
    if rec.get("label_source") == "tick_direct" and outcome in {"win", "loss"}:
        spread = pd.to_numeric(pd.Series([rec.get("fill_spread_r")]), errors="coerce").iloc[0]
        slip = pd.to_numeric(pd.Series([rec.get("stop_slippage_r", 0)]), errors="coerce").fillna(0).iloc[0]
        if np.isfinite(spread) and spread <= 0.20 and slip <= 0.10:
            return "trusted_tick"
        return "tick_high_friction"
    if rec.get("label_source") == "m1_spread_approx" and outcome in {"win", "loss"}:
        return "m1_unambiguous"
    if str(outcome).startswith("ambiguous"):
        return "ambiguous"
    return "unresolved"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--export-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reward-r", type=float, default=2.5)
    ap.add_argument("--max-hold-hours", type=float, default=12.0)
    ap.add_argument("--tick-only", action="store_true", help="Do not fall back to M1 when direct ticks are unavailable")
    args = ap.parse_args()

    trades = load_ledger(args.ledger, args.reward_r)
    store = SameBrokerStore(args.export_root)
    missing_symbols = sorted(set(trades.symbol) - {s.upper() for s in store.manifest.get("symbols", {})})
    if missing_symbols:
        print(f"warning: ledger symbols not present in export: {missing_symbols}")

    rows = []
    for rec in trades.to_dict("records"):
        if not store.has_symbol(rec["symbol"]):
            continue
        t = Trade(**rec)
        end = t.entry_time + pd.Timedelta(hours=args.max_hold_hours)
        ticks = store.ticks_for_window(t.symbol, t.entry_time - pd.Timedelta(minutes=5), end)
        result = relabel_ticks(t, ticks, args.max_hold_hours)
        if result.get("execution_outcome") == "no_data" and not args.tick_only:
            result = relabel_m1(t, store.m1(t.symbol), store.point.get(t.symbol, np.nan), args.max_hold_hours)
        result["label_quality"] = quality(result)
        rows.append({**rec, **result})

    out = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    clear = out[out.execution_outcome.isin(["win", "loss"])] if not out.empty else out
    direct = clear[clear.label_source == "tick_direct"] if not clear.empty else clear
    summary = {
        "trades_loaded": int(len(trades)),
        "trades_replayed": int(len(out)),
        "direct_tick_clear": int(len(direct)),
        "m1_fallback_clear": int((clear.label_source == "m1_spread_approx").sum()) if len(clear) else 0,
        "ambiguous": int(out.execution_outcome.astype(str).str.startswith("ambiguous").sum()) if len(out) else 0,
        "no_fill": int((out.execution_outcome == "no_fill").sum()) if len(out) else 0,
        "no_data": int((out.execution_outcome == "no_data").sum()) if len(out) else 0,
        "direct_tick_agreement": float((direct.execution_outcome == direct.source_outcome).mean()) if len(direct) else np.nan,
        "direct_tick_execution_expectancy_r": float(pd.to_numeric(direct.execution_r, errors="coerce").mean()) if len(direct) else np.nan,
        "trusted_tick_count": int((out.label_quality == "trusted_tick").sum()) if len(out) else 0,
    }
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
