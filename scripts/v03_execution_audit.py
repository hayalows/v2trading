from __future__ import annotations

"""Independent XAUUSD 1-minute execution audit for V2 Quant v0.3.

The main public proxy uses one vendor/source at M15/M5. This audit uses a separate
minute-level XAUUSD dataset to ask four narrower questions:

- was the midpoint entry actually touched after the setup became eligible?
- does M1 sequencing agree with the M15/M5 result?
- how many cases remain ambiguous even at M1?
- how sensitive is fill availability to a one-minute execution delay?

Because spot-gold brokers can have a persistent quote basis difference, each trade is
also checked after a local pre-entry close offset between the two data sources. The
offset uses only the last completed 15-minute bar before entry.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import public_data_v2_proxy as proxy


def load_xau_m1(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    rename = {}
    for c in df.columns:
        k = c.strip().lower().strip("<>")
        if k in {"datetime", "date", "time"}:
            rename[c] = "date"
        elif k in {"open", "high", "low", "close", "tickvol", "volume"}:
            rename[c] = "volume" if k in {"tickvol", "volume"} else k
    df = df.rename(columns=rename)
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"M1 file missing columns {sorted(missing)}; columns={list(df.columns)}")
    if "volume" not in df:
        df["volume"] = np.nan
    df["date"] = pd.to_datetime(df.date, utc=True, errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)


def resample_15m(m1: pd.DataFrame) -> pd.DataFrame:
    x = m1.set_index("date")
    r = x.resample("15min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return r.reset_index()


def level_offset(entry_time: pd.Timestamp, source15: pd.DataFrame, independent15: pd.DataFrame) -> float | None:
    s = source15[source15.date < entry_time]
    q = independent15[independent15.date < entry_time]
    if s.empty or q.empty:
        return None
    srow = s.iloc[-1]
    # Use nearest independent bar no more than 30 minutes away.
    j = (q.date - pd.Timestamp(srow.date)).abs().idxmin()
    qrow = q.loc[j]
    if abs((pd.Timestamp(qrow.date) - pd.Timestamp(srow.date)).total_seconds()) > 1800:
        return None
    return float(qrow.close - srow.close)


def first_entry_index(window: pd.DataFrame, direction: str, entry: float) -> int | None:
    mask = (window.low <= entry) & (window.high >= entry)
    ids = np.flatnonzero(mask.to_numpy())
    return int(ids[0]) if len(ids) else None


def simulate(window: pd.DataFrame, direction: str, entry: float, stop: float, target: float, delay_minutes: int = 0) -> dict:
    w = window.copy().reset_index(drop=True)
    if delay_minutes:
        start_time = w.date.iloc[0] + pd.Timedelta(minutes=delay_minutes)
        w = w[w.date >= start_time].reset_index(drop=True)
    if w.empty:
        return {"fill": False, "outcome": "no_data", "fill_time": None, "exit_time": None}
    ei = first_entry_index(w, direction, entry)
    if ei is None:
        return {"fill": False, "outcome": "no_fill", "fill_time": None, "exit_time": None}
    for j in range(ei, len(w)):
        r = w.iloc[j]
        if direction == "long":
            hs, ht = float(r.low) <= stop, float(r.high) >= target
        else:
            hs, ht = float(r.high) >= stop, float(r.low) <= target
        if hs and ht:
            return {"fill": True, "outcome": "ambiguous_1m", "fill_time": str(w.iloc[ei].date), "exit_time": str(r.date)}
        if hs:
            return {"fill": True, "outcome": "loss", "fill_time": str(w.iloc[ei].date), "exit_time": str(r.date)}
        if ht:
            return {"fill": True, "outcome": "win", "fill_time": str(w.iloc[ei].date), "exit_time": str(r.date)}
    return {"fill": True, "outcome": "timeout", "fill_time": str(w.iloc[ei].date), "exit_time": str(w.iloc[-1].date)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", type=Path, required=True)
    ap.add_argument("--m1", type=Path, required=True)
    ap.add_argument("--source15", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(args.trades)
    trades = trades[(trades.symbol == "XAUUSD") & trades.net_r.notna()].copy()
    trades["entry_time"] = pd.to_datetime(trades.entry_time, utc=True)
    m1 = load_xau_m1(args.m1)
    independent15 = resample_15m(m1)
    source15 = proxy.load_market(args.source15, "XAUUSD")

    min_t, max_t = m1.date.min(), m1.date.max()
    trades = trades[(trades.entry_time >= min_t) & (trades.entry_time <= max_t)].copy()
    dates = m1.date.to_numpy()
    rows = []
    for _, r in trades.iterrows():
        ts = pd.Timestamp(r.entry_time)
        end = ts + pd.Timedelta(hours=12)
        lo = int(np.searchsorted(dates, np.datetime64(ts.to_datetime64()), side="left"))
        hi = int(np.searchsorted(dates, np.datetime64(end.to_datetime64()), side="right"))
        w = m1.iloc[lo:hi].copy()
        if w.empty:
            continue
        off = level_offset(ts, source15, independent15)
        if off is None:
            continue
        entry, stop, target = float(r.entry + off), float(r.stop + off), float(r.target + off)
        raw_touch = bool(((w.low <= float(r.entry)) & (w.high >= float(r.entry))).any())
        base = simulate(w, str(r.direction), entry, stop, target, delay_minutes=0)
        delayed = simulate(w, str(r.direction), entry, stop, target, delay_minutes=1)
        rows.append({
            "setup_id": r.setup_id,
            "entry_time": ts,
            "m15_outcome": r.outcome,
            "quote_offset": off,
            "quote_offset_bps": 1e4 * off / max(abs(float(r.entry)), 1e-9),
            "raw_entry_touch": int(raw_touch),
            "adjusted_fill": int(base["fill"]),
            "m1_outcome": base["outcome"],
            "m1_fill_time": base["fill_time"],
            "m1_exit_time": base["exit_time"],
            "delay1m_fill": int(delayed["fill"]),
            "delay1m_outcome": delayed["outcome"],
        })

    audit = pd.DataFrame(rows)
    audit.to_csv(args.out / "v03_xau_m1_execution_audit.csv", index=False)
    comparable = audit[audit.m1_outcome.isin(["win", "loss"]) & audit.m15_outcome.isin(["win", "loss"])].copy() if not audit.empty else pd.DataFrame()
    summary = {
        "source": "independent XAUUSD one-minute history",
        "m1_data_start": str(min_t),
        "m1_data_end": str(max_t),
        "audited_trades": int(len(audit)),
        "adjusted_fill_rate": float(audit.adjusted_fill.mean()) if len(audit) else np.nan,
        "one_minute_delayed_fill_rate": float(audit.delay1m_fill.mean()) if len(audit) else np.nan,
        "remaining_m1_ambiguous": int((audit.m1_outcome == "ambiguous_1m").sum()) if len(audit) else 0,
        "m15_m1_directional_agreement": float((comparable.m15_outcome == comparable.m1_outcome).mean()) if len(comparable) else np.nan,
        "comparable_win_loss_trades": int(len(comparable)),
        "median_quote_offset": float(audit.quote_offset.median()) if len(audit) else np.nan,
        "median_abs_quote_offset_bps": float(audit.quote_offset_bps.abs().median()) if len(audit) else np.nan,
        "warning": "This is cross-source OHLC validation, not a substitute for bid/ask ticks. The local pre-entry offset reduces persistent broker-basis differences without using future prices.",
    }
    (args.out / "v03_xau_m1_execution_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
