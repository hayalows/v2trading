from __future__ import annotations

"""V2 v1.7 Granite TTM R2 standalone structural challenger.

Frozen target: earliest independent Stage-3/4 campaign observation -> same-direction
BOS / Stage 5 within 16 completed M15 bars. Research only; no execution claims.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from tsfm_public.toolkit.get_model import get_model

from public_data_v2_proxy import load_market
from v06_prospective_detector_validation_np import replay
from v16_state_twin_research import find_campaigns

SYMBOLS = ("EURUSD", "GBPUSD")
CONTEXT = 512
MODEL_FORECAST = 96
HORIZON = 16
FEATURES = ["bos_margin_atr", "endpoint_move_atr", "forecast_crosses_bos", "forecast_dispersion_atr"]
MODEL_PATH = "ibm-granite/granite-timeseries-ttm-r2"


def true_range_np(x: np.ndarray) -> np.ndarray:
    o, h, l, c = x[:, 0], x[:, 1], x[:, 2], x[:, 3]
    prev = np.r_[c[0], c[:-1]]
    return np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))


def point_atr(x: np.ndarray, i: int, n: int = 14) -> float:
    tr = true_range_np(x[max(0, i - n - 2) : i + 1])
    return max(float(np.mean(tr[-n:])), abs(float(x[i, 3])) * 1e-6)


def bos_reference(df: pd.DataFrame, raw_i: int, expected_direction: str) -> float | None:
    start = max(0, raw_i - 119)
    w = df.loc[start:raw_i, ["open", "high", "low", "close"]].to_numpy(float)
    n = len(w)
    if n < 45:
        return None
    o, h, l, c = w[:, 0], w[:, 1], w[:, 2], w[:, 3]
    tr = true_range_np(w)

    def atr(j: int) -> float:
        return float(np.mean(tr[max(0, j - 13) : j + 1]))

    a = max(atr(n - 1), abs(float(c[-1])) * 1e-6)
    sweep_i = -1
    direction = None
    for j in range(max(22, n - 12), n):
        ph = float(np.max(h[j - 20 : j]))
        pl = float(np.min(l[j - 20 : j]))
        aj = max(atr(j), a)
        bear = h[j] > ph + 0.03 * aj and c[j] < ph
        bull = l[j] < pl - 0.03 * aj and c[j] > pl
        if bear or bull:
            sweep_i = j
            direction = "short" if bear else "long"
    if sweep_i < 0 or direction != expected_direction:
        return None
    pre0 = max(0, sweep_i - 8)
    if pre0 == sweep_i:
        return None
    if direction == "long":
        return float(np.max(h[pre0:sweep_i]))
    return float(np.min(l[pre0:sweep_i]))


def build_samples(df: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, np.ndarray]:
    states = replay(df, symbol).reset_index(drop=True)
    campaigns = find_campaigns(states)
    x = df[["open", "high", "low", "close"]].to_numpy(float)
    closes = x[:, 3]
    rows: list[dict] = []
    contexts: list[np.ndarray] = []

    for c in campaigns:
        idx = int(c["start_i"])
        cur = states.iloc[idx]
        raw_i = int(cur.bar_i)
        if raw_i < CONTEXT - 1:
            continue
        if idx + HORIZON >= len(states):
            continue
        event_i = c.get("event_i")
        reset_i = c.get("reset_i")
        if event_i is not None and int(event_i) > idx and int(event_i) - idx <= HORIZON:
            y = 1
        elif reset_i is not None and int(reset_i) > idx and int(reset_i) - idx <= HORIZON:
            y = 0
        else:
            y = 0

        direction = str(c["direction"])
        ref = bos_reference(df, raw_i, direction)
        if ref is None:
            continue
        atr = point_atr(x, raw_i)
        ctx = closes[raw_i - CONTEXT + 1 : raw_i + 1].astype(np.float32)
        if len(ctx) != CONTEXT or not np.all(np.isfinite(ctx)):
            continue
        mu = float(np.mean(ctx))
        sd = max(float(np.std(ctx)), abs(mu) * 1e-7, 1e-9)
        z = ((ctx - mu) / sd).reshape(CONTEXT, 1).astype(np.float32)
        contexts.append(z)
        rows.append(
            {
                "symbol": symbol,
                "campaign_id": c["campaign_id"],
                "time": pd.Timestamp(cur.time),
                "year": int(pd.Timestamp(cur.time).year),
                "direction": direction,
                "stage": int(cur.stage),
                "raw_i": raw_i,
                "close": float(closes[raw_i]),
                "bos_reference": ref,
                "atr": atr,
                "context_mu": mu,
                "context_sd": sd,
                "event": int(y),
            }
        )
    return pd.DataFrame(rows), np.stack(contexts) if contexts else np.empty((0, CONTEXT, 1), np.float32)


def run_ttm(contexts: np.ndarray, rows: pd.DataFrame, batch_size: int) -> pd.DataFrame:
    if len(rows) == 0:
        return rows
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    model = get_model(
        model_path=MODEL_PATH,
        context_length=CONTEXT,
        prediction_length=MODEL_FORECAST,
        prefer_longer_context=False,
    )
    model.eval()
    feats: list[dict] = []
    for start in range(0, len(rows), batch_size):
        end = min(len(rows), start + batch_size)
        past = torch.from_numpy(contexts[start:end])
        with torch.no_grad():
            out = model(past_values=past, return_loss=False)
        pred_z = out.prediction_outputs[:, :HORIZON, 0].detach().cpu().numpy()
        for k in range(end - start):
            r = rows.iloc[start + k]
            pred = pred_z[k] * float(r.context_sd) + float(r.context_mu)
            atr = max(float(r.atr), 1e-12)
            close = float(r.close)
            ref = float(r.bos_reference)
            sign = 1.0 if r.direction == "long" else -1.0
            directional_extreme = float(np.max(pred) if sign > 0 else np.min(pred))
            bos_margin = sign * (directional_extreme - ref) / atr
            endpoint = sign * (float(pred[-1]) - close) / atr
            crosses = float(np.any(pred >= ref) if sign > 0 else np.any(pred <= ref))
            dispersion = float(np.std(pred) / atr)
            feats.append(
                {
                    "bos_margin_atr": bos_margin,
                    "endpoint_move_atr": endpoint,
                    "forecast_crosses_bos": crosses,
                    "forecast_dispersion_atr": dispersion,
                }
            )
    return pd.concat([rows.reset_index(drop=True), pd.DataFrame(feats)], axis=1)


def safe_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    out = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.any():
            out += float(m.mean()) * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(out)


def metric_row(y: np.ndarray, p: np.ndarray, base: np.ndarray) -> dict:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    base = np.clip(np.asarray(base, float), 1e-6, 1 - 1e-6)
    b = float(brier_score_loss(y, p))
    bb = float(brier_score_loss(y, base))
    return {
        "n": int(len(y)),
        "event_rate": float(np.mean(y)),
        "auc": safe_auc(y, p),
        "brier": b,
        "base_brier": bb,
        "brier_improvement": bb - b,
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "ece10": ece(y, p),
    }


def walk_forward(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    yearly: list[dict] = []
    preds: list[pd.DataFrame] = []
    years = sorted(y for y in data.year.unique() if y >= 2022)
    for year in years:
        train = data[data.year < year].copy()
        test = data[data.year == year].copy()
        if len(train) < 500 or len(test) < 50 or train.event.nunique() < 2:
            continue
        pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(C=0.5, max_iter=2000, random_state=42)),
            ]
        )
        pipe.fit(train[FEATURES], train.event)
        p = pipe.predict_proba(test[FEATURES])[:, 1]
        base_p = float(train.event.mean())
        base = np.full(len(test), base_p)
        m = metric_row(test.event.to_numpy(int), p, base)
        yearly.append({"year": int(year), "train_n": int(len(train)), "base_probability": base_p, **m})
        z = test[["symbol", "campaign_id", "time", "year", "direction", "stage", "event"] + FEATURES].copy()
        z["ttm_probability"] = p
        z["base_probability"] = base_p
        preds.append(z)
    pred = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame()
    yr = pd.DataFrame(yearly)
    completed = pred[pred.year.between(2022, 2025)].copy()
    if len(completed):
        pooled = metric_row(completed.event.to_numpy(int), completed.ttm_probability.to_numpy(float), completed.base_probability.to_numpy(float))
        pairs = {}
        for sym in SYMBOLS:
            q = completed[completed.symbol == sym]
            pairs[sym] = metric_row(q.event.to_numpy(int), q.ttm_probability.to_numpy(float), q.base_probability.to_numpy(float)) if len(q) else {"n": 0}
        positive_years = int((yr[yr.year.between(2022, 2025)].brier_improvement > 0).sum()) if len(yr) else 0
        pooled["positive_brier_years_2022_2025"] = positive_years
        pooled["pair_results"] = pairs
    else:
        pooled = {"n": 0, "positive_brier_years_2022_2025": 0, "pair_results": {s: {"n": 0} for s in SYMBOLS}}
    return yr, pred, pooled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=128)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    tables: list[pd.DataFrame] = []
    contexts: list[np.ndarray] = []
    for sym in SYMBOLS:
        df = load_market(args.data_dir / f"{sym}-15m.feather", sym)
        df = df[df.date >= pd.Timestamp(args.start, tz="UTC")].reset_index(drop=True)
        t, c = build_samples(df, sym)
        tables.append(t)
        contexts.append(c)
    meta = pd.concat(tables, ignore_index=True)
    ctx = np.concatenate(contexts, axis=0)
    if len(meta) != len(ctx):
        raise RuntimeError("metadata/context alignment failure")

    data = run_ttm(ctx, meta, args.batch_size)
    data.replace([np.inf, -np.inf], np.nan, inplace=True)
    yearly, pred, pooled = walk_forward(data)
    pairs = pooled.get("pair_results", {})
    accepted = bool(
        pooled.get("n", 0) >= 5000
        and (pooled.get("auc") or 0) >= 0.58
        and pooled.get("brier_improvement", -1) > 0
        and pooled.get("positive_brier_years_2022_2025", 0) >= 3
        and all(pairs.get(s, {}).get("brier_improvement", -1) >= 0 for s in SYMBOLS)
    )
    decision = "PROMOTE_TTM_TO_SHADOW" if accepted else "REJECT_TTM_STANDALONE"
    report = {
        "study": "V2 v1.7 Granite TTM R2 structural challenger",
        "target": "earliest independent Stage-3/4 -> same-direction Stage 5 within 16 M15 bars",
        "model": MODEL_PATH,
        "context_bars": CONTEXT,
        "forecast_bars_used": HORIZON,
        "features": FEATURES,
        "samples_total": int(len(data)),
        "campaigns_total": int(data.campaign_id.nunique()) if len(data) else 0,
        "yearly": yearly.to_dict(orient="records"),
        "completed_2022_2025": pooled,
        "decision": decision,
        "product_rule": "A pass only permits TTM to enter prospective Shadow Arena and an incremental-to-StateTwin test. It never enables a buy/sell or execution claim.",
    }
    data.to_csv(args.out / "v17_ttm_features.csv", index=False)
    yearly.to_csv(args.out / "v17_ttm_yearly.csv", index=False)
    pred.to_csv(args.out / "v17_ttm_oos_predictions.csv", index=False)
    (args.out / "v17_ttm_summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
