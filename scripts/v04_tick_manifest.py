from __future__ import annotations

"""Build a deterministic, score-stratified tick audit sample for V2 Quant v0.4.

The sample is deliberately NOT chosen by historical win/loss. For each symbol we split
out-of-sample v0.3 predictions into score octiles and draw a fixed number from every
part of the score distribution. This lets the tick audit test whether v0.3 ranking
survives when labels come from executable bid/ask ticks rather than M15/M5 OHLC.
"""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

INSTRUMENTS = {
    "EURUSD": "eurusd",
    "GBPUSD": "gbpusd",
    "XAUUSD": "xauusd",
    "NAS100": "usatechidxusd",
}

KEYS = ["setup_id", "symbol", "direction", "entry_time"]


def occurrence_safe_merge(left: pd.DataFrame, right: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    a, b = left.copy(), right.copy()
    for df in (a, b):
        df["entry_time"] = pd.to_datetime(df.entry_time, utc=True, errors="coerce")
        df["_occ"] = df.groupby(KEYS, dropna=False).cumcount()
    keep = KEYS + ["_occ"] + [c for c in cols if c in b.columns]
    return a.merge(b[keep], on=KEYS + ["_occ"], how="inner", validate="one_to_one").drop(columns="_occ")


def stable_hash(row: pd.Series) -> str:
    raw = f"{row.setup_id}|{row.symbol}|{row.direction}|{pd.Timestamp(row.entry_time).isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-symbol", type=int, default=16)
    ap.add_argument("--bins", type=int, default=8)
    args = ap.parse_args()

    ledger = pd.read_csv(args.ledger)
    pred = pd.read_csv(args.predictions)
    x = occurrence_safe_merge(ledger, pred, ["p_price", "q50_threshold", "q70_threshold"])
    x = x[x.symbol.isin(INSTRUMENTS) & x.p_price.notna() & x.net_r.notna()].copy()
    x["entry_time"] = pd.to_datetime(x.entry_time, utc=True)
    x = x[x.entry_time.dt.year.between(2023, 2025)].copy()
    x["stable_hash"] = x.apply(stable_hash, axis=1)

    picks = []
    for symbol, g in x.groupby("symbol", sort=True):
        g = g.sort_values(["p_price", "stable_hash"]).copy()
        # Rank-based bins are robust to duplicate probability values.
        ranks = g.p_price.rank(method="first", pct=True).clip(upper=1 - 1e-12)
        g["score_bin"] = np.floor(ranks * args.bins).astype(int).clip(0, args.bins - 1)
        base = args.per_symbol // args.bins
        rem = args.per_symbol % args.bins
        chosen_idx: list[int] = []
        for b in range(args.bins):
            need = base + int(b < rem)
            pool = g[g.score_bin == b].sort_values("stable_hash")
            chosen_idx.extend(pool.head(need).index.tolist())
        if len(chosen_idx) < args.per_symbol:
            unused = g[~g.index.isin(chosen_idx)].sort_values("stable_hash")
            chosen_idx.extend(unused.head(args.per_symbol - len(chosen_idx)).index.tolist())
        chosen = g.loc[chosen_idx].sort_values(["score_bin", "p_price", "stable_hash"]).head(args.per_symbol)
        for _, r in chosen.iterrows():
            start = r.entry_time.floor("D")
            end = start + pd.Timedelta(days=2 if r.entry_time.hour >= 12 else 1)
            picks.append({
                "setup_id": r.setup_id,
                "symbol": symbol,
                "dukascopy_instrument": INSTRUMENTS[symbol],
                "entry_time": r.entry_time.isoformat(),
                "entry": float(r.entry),
                "stop": float(r.stop),
                "target": float(r.target),
                "risk_distance": float(r.risk_distance),
                "risk_atr": float(r.risk_atr),
                "cost_as_r": float(r.cost_as_r),
                "direction": r.direction,
                "m15_outcome": r.outcome,
                "m15_net_r": float(r.net_r),
                "p_price": float(r.p_price),
                "score_bin": int(r.score_bin),
                "from": start.date().isoformat(),
                "to": end.date().isoformat(),
            })

    out = pd.DataFrame(picks)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    counts = out.groupby(["symbol", "score_bin"]).size().unstack(fill_value=0) if not out.empty else pd.DataFrame()
    print(f"v0.4 tick manifest: {len(out)} trades")
    print(counts.to_string())


if __name__ == "__main__":
    main()
