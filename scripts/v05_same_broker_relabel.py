from __future__ import annotations

"""Core same-broker execution relabeling utilities for V2 Quant v0.5.

Use ``v05_same_broker_relabel_runner.py`` as the supported CLI. This module contains
only deterministic parsing, storage and replay logic so tests and the runner share one
implementation.
"""

import json
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


@dataclass(frozen=True)
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
    raw = pd.read_parquet(path) if path.suffix.lower() in {".parquet", ".pq"} else pd.read_csv(path, low_memory=False)
    optional = {"exit_time", "target", "net_r", "outcome", "setup_id"}
    cols = {k: find_col(raw, k, required=k not in optional) for k in COL_ALIASES}
    rows: list[dict] = []
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
                nr = pd.to_numeric(pd.Series([r[cols["net_r"]]]), errors="coerce").iloc[0]
                net_r = float(nr) if np.isfinite(nr) else None
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
                "source_outcome": normalize_outcome(r[cols["outcome"]] if cols["outcome"] is not None else None, net_r),
                "source_net_r": net_r,
            })
        except (ValueError, TypeError, KeyError):
            continue
    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("No usable trades found in ledger after column mapping")
    return out.sort_values("entry_time").reset_index(drop=True)


class SameBrokerStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        self.point = {
            sym.upper(): float(meta.get("metadata", {}).get("point") or np.nan)
            for sym, meta in self.manifest.get("symbols", {}).items()
        }
        self._m1: dict[str, pd.DataFrame] = {}
        self._ticks: dict[tuple[str, str], pd.DataFrame] = {}

    def has_symbol(self, symbol: str) -> bool:
        return symbol.upper() in self.point

    def _symbol_dir(self, symbol: str) -> Path:
        direct = self.root / symbol.upper()
        if direct.exists():
            return direct
        matches = [p for p in self.root.iterdir() if p.is_dir() and p.name.upper() == symbol.upper()]
        if len(matches) == 1:
            return matches[0]
        return direct

    def m1(self, symbol: str) -> pd.DataFrame:
        s = symbol.upper()
        if s not in self._m1:
            p = self._symbol_dir(s) / "bars" / "M1.parquet"
            f = pd.read_parquet(p)
            f["time"] = pd.to_datetime(f.time, utc=True)
            self._m1[s] = f.sort_values("time").reset_index(drop=True)
        return self._m1[s]

    def ticks_for_window(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        s = symbol.upper()
        start = pd.Timestamp(start).tz_convert("UTC") if pd.Timestamp(start).tzinfo else pd.Timestamp(start, tz="UTC")
        end = pd.Timestamp(end).tz_convert("UTC") if pd.Timestamp(end).tzinfo else pd.Timestamp(end, tz="UTC")
        frames = []
        for day in pd.date_range(start.floor("D"), end.floor("D"), freq="D"):
            ds = day.date().isoformat()
            key = (s, ds)
            if key not in self._ticks:
                p = self._symbol_dir(s) / "ticks" / f"date={ds}" / "ticks.parquet"
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


def _median_spread_r(frame: pd.DataFrame, risk: float) -> float:
    if frame.empty:
        return np.nan
    return float(((pd.to_numeric(frame.ask, errors="coerce") - pd.to_numeric(frame.bid, errors="coerce")) / risk).median())


def relabel_ticks(t: Trade, ticks: pd.DataFrame, max_hold_hours: float = 12.0) -> dict:
    if ticks.empty or not {"bid", "ask", "time"}.issubset(ticks.columns):
        return {"label_source": "no_ticks", "execution_outcome": "no_data", "filled": 0}
    w = ticks[(ticks.time >= t.entry_time) & (ticks.time <= t.entry_time + pd.Timedelta(hours=max_hold_hours))].copy()
    w["bid"] = pd.to_numeric(w.bid, errors="coerce")
    w["ask"] = pd.to_numeric(w.ask, errors="coerce")
    w = w[(w.bid > 0) & (w.ask > 0) & (w.ask >= w.bid)].sort_values("time").reset_index(drop=True)
    if w.empty:
        return {"label_source": "no_ticks", "execution_outcome": "no_data", "filled": 0}

    risk = t.risk
    fill_pos = None
    for j, r in w.iterrows():
        if (t.direction == "long" and r.ask <= t.entry) or (t.direction == "short" and r.bid >= t.entry):
            fill_pos = j
            break
    if fill_pos is None:
        return {"label_source": "tick_direct", "execution_outcome": "no_fill", "filled": 0,
                "spread_median_r": _median_spread_r(w, risk)}

    fill = w.iloc[fill_pos]
    fill_price = min(float(fill.ask), t.entry) if t.direction == "long" else max(float(fill.bid), t.entry)
    fill_spread_r = float((fill.ask - fill.bid) / risk)
    after = w.iloc[fill_pos:]
    med_spread = _median_spread_r(after, risk)

    for _, r in after.iterrows():
        bid, ask = float(r.bid), float(r.ask)
        if t.direction == "long":
            if bid <= t.stop:
                return {"label_source": "tick_direct", "execution_outcome": "loss", "filled": 1,
                        "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": bid,
                        "execution_r": (bid-fill_price)/risk, "fill_spread_r": fill_spread_r,
                        "stop_slippage_r": max(0.0, t.stop-bid)/risk, "spread_median_r": med_spread}
            if bid >= t.target:
                return {"label_source": "tick_direct", "execution_outcome": "win", "filled": 1,
                        "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": t.target,
                        "execution_r": (t.target-fill_price)/risk, "fill_spread_r": fill_spread_r,
                        "stop_slippage_r": 0.0, "spread_median_r": med_spread}
        else:
            if ask >= t.stop:
                return {"label_source": "tick_direct", "execution_outcome": "loss", "filled": 1,
                        "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": ask,
                        "execution_r": (fill_price-ask)/risk, "fill_spread_r": fill_spread_r,
                        "stop_slippage_r": max(0.0, ask-t.stop)/risk, "spread_median_r": med_spread}
            if ask <= t.target:
                return {"label_source": "tick_direct", "execution_outcome": "win", "filled": 1,
                        "fill_time": fill.time, "exit_time": r.time, "fill_price": fill_price, "exit_price": t.target,
                        "execution_r": (fill_price-t.target)/risk, "fill_spread_r": fill_spread_r,
                        "stop_slippage_r": 0.0, "spread_median_r": med_spread}

    last = after.iloc[-1]
    mark = float(last.bid) if t.direction == "long" else float(last.ask)
    rr = (mark-fill_price)/risk if t.direction == "long" else (fill_price-mark)/risk
    return {"label_source": "tick_direct", "execution_outcome": "timeout", "filled": 1,
            "fill_time": fill.time, "exit_time": last.time, "fill_price": fill_price, "exit_price": mark,
            "execution_r": float(np.clip(rr, -2.0, 3.0)), "fill_spread_r": fill_spread_r,
            "stop_slippage_r": 0.0, "spread_median_r": med_spread}


def relabel_m1(t: Trade, m1: pd.DataFrame, point: float, max_hold_hours: float = 12.0) -> dict:
    w = m1[(m1.time >= t.entry_time.floor("min")) & (m1.time <= t.entry_time + pd.Timedelta(hours=max_hold_hours))].copy()
    if w.empty:
        return {"label_source": "m1_spread_approx", "execution_outcome": "no_data", "filled": 0}
    if not np.isfinite(point) or point <= 0:
        point = max(abs(t.entry) * 1e-6, 1e-9)
    spread_points = pd.to_numeric(w["spread"], errors="coerce").fillna(0) if "spread" in w else pd.Series(0.0, index=w.index)
    spread_px = spread_points * point
    w["ask_low"] = pd.to_numeric(w.low, errors="coerce") + spread_px
    w["ask_high"] = pd.to_numeric(w.high, errors="coerce") + spread_px
    w = w.reset_index(drop=True)
    spread_px = spread_px.reset_index(drop=True)
    risk = t.risk

    fill_pos = None
    for j, r in w.iterrows():
        if (t.direction == "long" and float(r.ask_low) <= t.entry) or (t.direction == "short" and float(r.high) >= t.entry):
            fill_pos = j
            break
    if fill_pos is None:
        return {"label_source": "m1_spread_approx", "execution_outcome": "no_fill", "filled": 0}

    for j in range(fill_pos, len(w)):
        r = w.iloc[j]
        if t.direction == "long":
            stop_hit, tp_hit = float(r.low) <= t.stop, float(r.high) >= t.target
        else:
            stop_hit, tp_hit = float(r.ask_high) >= t.stop, float(r.ask_low) <= t.target
        if stop_hit and tp_hit:
            return {"label_source": "m1_spread_approx", "execution_outcome": "ambiguous_m1", "filled": 1}
        if j == fill_pos and (stop_hit or tp_hit):
            return {"label_source": "m1_spread_approx", "execution_outcome": "ambiguous_entry_minute", "filled": 1}
        if stop_hit:
            return {"label_source": "m1_spread_approx", "execution_outcome": "loss", "filled": 1,
                    "execution_r": -1.0, "fill_spread_r": float(spread_px.iloc[j]/risk)}
        if tp_hit:
            return {"label_source": "m1_spread_approx", "execution_outcome": "win", "filled": 1,
                    "execution_r": abs(t.target-t.entry)/risk, "fill_spread_r": float(spread_px.iloc[j]/risk)}
    return {"label_source": "m1_spread_approx", "execution_outcome": "timeout", "filled": 1}


def quality(rec: dict) -> str:
    outcome = rec.get("execution_outcome")
    if rec.get("label_source") == "tick_direct" and outcome in {"win", "loss"}:
        spread = pd.to_numeric(pd.Series([rec.get("fill_spread_r")]), errors="coerce").iloc[0]
        slip = pd.to_numeric(pd.Series([rec.get("stop_slippage_r", 0)]), errors="coerce").fillna(0).iloc[0]
        return "trusted_tick" if np.isfinite(spread) and spread <= 0.20 and slip <= 0.10 else "tick_high_friction"
    if rec.get("label_source") == "m1_spread_approx" and outcome in {"win", "loss"}:
        return "m1_unambiguous"
    if str(outcome).startswith("ambiguous"):
        return "ambiguous"
    return "unresolved"
