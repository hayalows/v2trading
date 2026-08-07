from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load(path: Path) -> pd.DataFrame:
    df = pd.read_feather(path)
    cols = {str(c).lower(): c for c in df.columns}
    time_col = next(cols[k] for k in ("date", "datetime", "time", "timestamp") if k in cols)
    out = pd.DataFrame({
        "time": pd.to_datetime(df[time_col], utc=True, errors="coerce"),
        "open": pd.to_numeric(df[cols["open"]], errors="coerce"),
        "high": pd.to_numeric(df[cols["high"]], errors="coerce"),
        "low": pd.to_numeric(df[cols["low"]], errors="coerce"),
        "close": pd.to_numeric(df[cols["close"]], errors="coerce"),
    }).dropna().sort_values("time").drop_duplicates("time")
    return out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)].reset_index(drop=True)


def efficiency(close: pd.Series, n: int = 20) -> pd.Series:
    change = (close - close.shift(n)).abs()
    path = close.diff().abs().rolling(n).sum()
    return (change / path.replace(0, np.nan)).clip(0, 1)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    prev = x.close.shift(1)
    tr = pd.concat([(x.high-x.low), (x.high-prev).abs(), (x.low-prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    x["natr"] = atr / x.close
    x["eff20"] = efficiency(x.close, 20)
    x["vol_pct"] = x.natr.rolling(120, min_periods=60).apply(lambda a: 100.0 * np.mean(a <= a[-1]), raw=True)
    ret = np.log(x.close).diff()
    recent = ret.rolling(8).std(ddof=0)
    base = ret.rolling(50).std(ddof=0)
    x["vol_ratio"] = recent / base
    move = np.log(x.close / x.close.shift(8)).abs()
    x["return_shock"] = move / (base * np.sqrt(8))
    raw = (x.vol_ratio.sub(1).clip(lower=0) / 0.8 * 0.55 + x.return_shock.sub(1).clip(lower=0) / 2.0 * 0.45)
    x["shift_score"] = (raw * 100).clip(0, 100)
    x["shift_risk"] = np.select([x.shift_score >= 70, x.shift_score >= 40], ["high", "elevated"], default="stable")
    x["future_abs_1h_bps"] = (np.log(x.close.shift(-4) / x.close).abs() * 10000)
    x["future_abs_4h_bps"] = (np.log(x.close.shift(-16) / x.close).abs() * 10000)
    return x


def summarize(symbol: str, x: pd.DataFrame) -> dict:
    y = x.dropna(subset=["eff20", "vol_pct", "shift_score", "future_abs_1h_bps"]).copy()
    by_shift = {}
    for risk in ["stable", "elevated", "high"]:
        g = y[y.shift_risk == risk]
        by_shift[risk] = {
            "n": int(len(g)),
            "share": float(len(g) / len(y)) if len(y) else 0.0,
            "median_next_1h_abs_bps": float(g.future_abs_1h_bps.median()) if len(g) else None,
            "median_next_4h_abs_bps": float(g.future_abs_4h_bps.median()) if len(g) else None,
        }
    return {
        "symbol": symbol,
        "rows": int(len(y)),
        "efficiency_min": float(y.eff20.min()),
        "efficiency_max": float(y.eff20.max()),
        "vol_percentile_min": float(y.vol_pct.min()),
        "vol_percentile_max": float(y.vol_pct.max()),
        "shift_score_min": float(y.shift_score.min()),
        "shift_score_max": float(y.shift_score.max()),
        "median_efficiency": float(y.eff20.median()),
        "by_shift": by_shift,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = {"version": "v0.7 quant context audit", "start": args.start, "symbols": {}}
    for symbol in ["EURUSD", "GBPUSD"]:
        df = load(args.data_dir / f"{symbol}-15m.feather")
        df = df[df.time >= pd.Timestamp(args.start, tz="UTC")].reset_index(drop=True)
        result["symbols"][symbol] = summarize(symbol, add_features(df))
    # Descriptive gate: diagnostics must be bounded and each shift state must occur.
    checks = []
    for s in result["symbols"].values():
        checks += [
            0 <= s["efficiency_min"] <= s["efficiency_max"] <= 1,
            0 <= s["vol_percentile_min"] <= s["vol_percentile_max"] <= 100,
            0 <= s["shift_score_min"] <= s["shift_score_max"] <= 100,
            all(s["by_shift"][r]["n"] > 0 for r in ["stable", "elevated", "high"]),
        ]
    result["sanity_pass"] = bool(all(checks))
    (args.out / "context_audit.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["sanity_pass"]:
        raise SystemExit("v0.7 context diagnostic sanity gate failed")


if __name__ == "__main__":
    main()
