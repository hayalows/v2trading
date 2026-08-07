from __future__ import annotations

"""V2 Quant v0.4 execution-first analysis.

This script does not retrain the v0.3 model after seeing tick outcomes. It asks whether
its already-frozen OOS probability ranking survives when the labels are replaced by
independent M1 or executable Dukascopy bid/ask outcomes.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

KEYS = ["setup_id", "entry_time"]


def auc_or_nan(y: pd.Series, p: pd.Series) -> float:
    z = pd.DataFrame({"y": pd.to_numeric(y, errors="coerce"), "p": pd.to_numeric(p, errors="coerce")}).dropna()
    return float(roc_auc_score(z.y, z.p)) if len(z) >= 5 and z.y.nunique() == 2 else np.nan


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return np.nan, np.nan
    ph = k / n
    den = 1 + z*z/n
    mid = (ph + z*z/(2*n)) / den
    half = z * np.sqrt(ph*(1-ph)/n + z*z/(4*n*n)) / den
    return float(max(0, mid-half)), float(min(1, mid+half))


def bootstrap_auc(y: np.ndarray, p: np.ndarray, seed: int = 404, n_boot: int = 2000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    vals = []
    n = len(y)
    if n < 8 or len(np.unique(y)) < 2:
        return np.nan, np.nan
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yy = y[idx]
        if len(np.unique(yy)) < 2:
            continue
        vals.append(roc_auc_score(yy, p[idx]))
    return (float(np.quantile(vals, .025)), float(np.quantile(vals, .975))) if vals else (np.nan, np.nan)


def safe_merge_predictions(pred: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    a, b = pred.copy(), audit.copy()
    for d in (a, b):
        d["entry_time"] = pd.to_datetime(d.entry_time, utc=True, errors="coerce")
        d["_occ"] = d.groupby(KEYS, dropna=False).cumcount()
    keep = ["setup_id", "entry_time", "_occ", "p_price", "net_r", "symbol"]
    keep = [c for c in keep if c in a.columns]
    return b.merge(a[keep], on=["setup_id", "entry_time", "_occ"], how="inner", validate="one_to_one").drop(columns="_occ")


def tick_metrics(tick: pd.DataFrame) -> dict:
    clear = tick[(pd.to_numeric(tick.adjusted_tick_filled, errors="coerce") == 1) & tick.adjusted_tick_outcome.isin(["win", "loss"])].copy()
    clear["tick_win"] = (clear.adjusted_tick_outcome == "win").astype(int)
    clear["p_price"] = pd.to_numeric(clear.p_price, errors="coerce")
    clear["fill_spread_r"] = pd.to_numeric(clear.fill_spread_r, errors="coerce")
    clear["stop_slippage_r"] = pd.to_numeric(clear.stop_slippage_r, errors="coerce").fillna(0)
    clear["adjusted_exec_r"] = pd.to_numeric(clear.adjusted_exec_r, errors="coerce")
    clear["source_cost_as_r"] = pd.to_numeric(clear.source_cost_as_r, errors="coerce")
    clear = clear.dropna(subset=["p_price"])
    n = len(clear)
    agree = int((clear.adjusted_tick_outcome == clear.m15_outcome).sum()) if n else 0
    lo, hi = wilson(agree, n)
    auc = auc_or_nan(clear.tick_win, clear.p_price)
    alo, ahi = bootstrap_auc(clear.tick_win.to_numpy(), clear.p_price.to_numpy()) if n else (np.nan, np.nan)

    threshold_rows = []
    for spread_cap in [0.10, 0.20, 0.30, 0.50]:
        z = clear[(clear.fill_spread_r <= spread_cap) & (clear.stop_slippage_r <= 0.10)].copy()
        za = auc_or_nan(z.tick_win, z.p_price) if len(z) else np.nan
        threshold_rows.append({
            "spread_cap_r": spread_cap,
            "n": int(len(z)),
            "coverage": float(len(z) / n) if n else np.nan,
            "m15_tick_agreement": float((z.adjusted_tick_outcome == z.m15_outcome).mean()) if len(z) else np.nan,
            "price_auc_on_tick_labels": za,
            "execution_expectancy_r": float(z.adjusted_exec_r.mean()) if len(z) else np.nan,
            "source_expectancy_same_trades_r": float(pd.to_numeric(z.m15_net_r, errors="coerce").mean()) if len(z) else np.nan,
        })

    corr = np.nan
    corr_p = np.nan
    cc = clear.dropna(subset=["source_cost_as_r", "fill_spread_r"])
    if len(cc) >= 8 and cc.source_cost_as_r.nunique() > 1 and cc.fill_spread_r.nunique() > 1:
        c = spearmanr(cc.source_cost_as_r, cc.fill_spread_r)
        corr, corr_p = float(c.statistic), float(c.pvalue)

    by_symbol = []
    for symbol, g in clear.groupby("symbol"):
        by_symbol.append({
            "symbol": symbol,
            "n": int(len(g)),
            "agreement": float((g.adjusted_tick_outcome == g.m15_outcome).mean()),
            "tick_auc": auc_or_nan(g.tick_win, g.p_price),
            "median_fill_spread_r": float(g.fill_spread_r.median()),
            "exec_expectancy_r": float(g.adjusted_exec_r.mean()),
        })

    trusted = clear[(clear.fill_spread_r <= 0.20) & (clear.stop_slippage_r <= 0.10)]
    median_spread = float(clear.fill_spread_r.median()) if n else np.nan
    gate = {
        "minimum_clear_labels_40": bool(n >= 40),
        "minimum_trusted_labels_20": bool(len(trusted) >= 20),
        "agreement_at_least_0_80": bool(n and agree/n >= 0.80),
        "tick_auc_at_least_0_55": bool(np.isfinite(auc) and auc >= 0.55),
        "median_fill_spread_at_most_0_20R": bool(np.isfinite(median_spread) and median_spread <= 0.20),
    }
    gate["pass"] = bool(all(gate.values()))
    return {
        "clear_labels": n,
        "trusted_labels": int(len(trusted)),
        "m15_tick_agreement": float(agree/n) if n else np.nan,
        "agreement_95ci": [lo, hi],
        "price_auc_on_tick_labels": auc,
        "tick_auc_bootstrap_95ci": [alo, ahi],
        "median_fill_spread_r": median_spread,
        "p90_fill_spread_r": float(clear.fill_spread_r.quantile(.90)) if n else np.nan,
        "execution_expectancy_r": float(clear.adjusted_exec_r.mean()) if n else np.nan,
        "source_expectancy_same_trades_r": float(pd.to_numeric(clear.m15_net_r, errors="coerce").mean()) if n else np.nan,
        "source_cost_vs_observed_spread_spearman": corr,
        "source_cost_vs_observed_spread_p": corr_p,
        "thresholds": threshold_rows,
        "by_symbol": by_symbol,
        "gate": gate,
    }


def m1_metrics(pred: pd.DataFrame, m1: pd.DataFrame) -> dict:
    z = safe_merge_predictions(pred, m1)
    z = z[z.m1_outcome.isin(["win", "loss"]) & z.m15_outcome.isin(["win", "loss"])].copy()
    if z.empty:
        return {"n": 0}
    z["m1_win"] = (z.m1_outcome == "win").astype(int)
    auc = auc_or_nan(z.m1_win, z.p_price)
    agree = int((z.m1_outcome == z.m15_outcome).sum())
    lo, hi = wilson(agree, len(z))
    return {
        "n": int(len(z)),
        "m15_m1_agreement": float(agree / len(z)),
        "agreement_95ci": [lo, hi],
        "price_auc_on_m1_labels": auc,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--m1-audit", type=Path, required=True)
    ap.add_argument("--tick-audit", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    pred = pd.read_csv(args.predictions)
    m1 = pd.read_csv(args.m1_audit)
    tick = pd.read_csv(args.tick_audit)
    tm = tick_metrics(tick)
    mm = m1_metrics(pred, m1)

    # M1 is a cross-source path check, so require a high agreement bar before it can
    # support a live gate. It is not allowed to override a failed true tick gate.
    m1_pass = bool(mm.get("n", 0) >= 40 and mm.get("m15_m1_agreement", 0) >= 0.75 and np.isfinite(mm.get("price_auc_on_m1_labels", np.nan)) and mm["price_auc_on_m1_labels"] >= 0.55)
    live_gate = bool(tm["gate"]["pass"] and m1_pass)

    summary = {
        "version": "V2 Quant v0.4 Execution First",
        "frozen_model_rule": "v0.3 p_price is evaluated unchanged; no retraining or sign flip after execution labels are observed",
        "tick_execution": tm,
        "xau_independent_m1": {**mm, "gate_pass": m1_pass},
        "overall_live_gate": "PASS" if live_gate else "FAIL",
        "decision": "Eligible for shadow trading only" if live_gate else "Keep live money and live buy/sell signals disabled",
        "pre_registered_tick_gate": {
            "clear_labels": 40,
            "trusted_labels": 20,
            "source_tick_agreement": 0.80,
            "price_auc_on_tick_labels": 0.55,
            "median_fill_spread_r": 0.20,
        },
    }
    (args.out / "v04_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(tm["thresholds"]).to_csv(args.out / "v04_execution_thresholds.csv", index=False)
    pd.DataFrame(tm["by_symbol"]).to_csv(args.out / "v04_execution_by_symbol.csv", index=False)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
