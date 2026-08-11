from __future__ import annotations

"""Score eligible V2 Shadow Arena records with frozen Granite TTM R2.

Authentication uses a short-lived GitHub Actions OIDC JWT. The scorer never receives
Supabase database credentials and can only submit a model score through the Edge
Function's restricted OIDC endpoint.

The v1.7 historical TTM gate was validated on the earliest independent Stage-3/4
observation only. v1.8 therefore restricts this scorer to landmark age 0 until a
separate dynamic-age validation exists.
"""

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import requests
import torch
from tsfm_public.toolkit.get_model import get_model

MODEL_PATH = "ibm-granite/granite-timeseries-ttm-r2"
TICKERS = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X"}
USER_AGENT = "V2-Shadow-TTM/1.1"


def get_json(url: str, token: str) -> dict[str, Any]:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}, timeout=45)
    r.raise_for_status()
    return r.json()


def yahoo_context(symbol: str, observed_bar_at: str, n: int = 512) -> np.ndarray | None:
    end_ts = int(np.datetime64(observed_bar_at).astype("datetime64[s]").astype(int))
    start_ts = end_ts - 21 * 24 * 3600
    ticker = TICKERS[symbol]
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={start_ts}&period2={end_ts + 900}&interval=15m&includePrePost=false&events=div%2Csplits"
    )
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    r.raise_for_status()
    payload = r.json()["chart"]["result"][0]
    ts = payload.get("timestamp") or []
    close = ((payload.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    vals = [(int(t), float(c)) for t, c in zip(ts, close) if c is not None and int(t) <= end_ts]
    if len(vals) < n:
        return None
    return np.asarray([v for _, v in vals[-n:]], dtype=np.float32)


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def calibrate(features: dict[str, float], cfg: dict[str, Any]) -> float:
    score = float(cfg["logistic_intercept"])
    for name in cfg["features"]:
        v = float(features.get(name, cfg["imputer_median"][name]))
        if not math.isfinite(v):
            v = float(cfg["imputer_median"][name])
        z = (v - float(cfg["scaler_mean"][name])) / max(float(cfg["scaler_scale"][name]), 1e-12)
        score += float(cfg["logistic_coef"][name]) * z
    return float(min(1 - 1e-6, max(1e-6, sigmoid(score))))


def score_item(model: Any, item: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any] | None:
    if int(item.get("landmark_age_bars", -1)) != 0:
        return None
    snapshot = item.get("feature_snapshot") or {}
    market = snapshot.get("market") or {}
    direction = item.get("direction")
    atr = float(market.get("atr15") or 0)
    bos = market.get("bosReference")
    if direction not in ("long", "short") or not atr or bos is None:
        return None
    ctx = yahoo_context(item["symbol"], item["observed_bar_at"], int(cfg["context_bars"]))
    if ctx is None:
        return None
    mu = float(np.mean(ctx))
    sd = max(float(np.std(ctx)), abs(mu) * 1e-7, 1e-9)
    zctx = ((ctx - mu) / sd).reshape(1, len(ctx), 1).astype(np.float32)
    with torch.no_grad():
        out = model(past_values=torch.from_numpy(zctx), return_loss=False)
    pred_z = out.prediction_outputs[0, : int(cfg["forecast_bars"]), 0].detach().cpu().numpy()
    pred = pred_z * sd + mu
    close = float(ctx[-1])
    sign = 1.0 if direction == "long" else -1.0
    extreme = float(np.max(pred) if sign > 0 else np.min(pred))
    bosf = float(bos)
    features = {
        "bos_margin_atr": sign * (extreme - bosf) / atr,
        "endpoint_move_atr": sign * (float(pred[-1]) - close) / atr,
        "forecast_crosses_bos": float(np.any(pred >= bosf) if sign > 0 else np.any(pred <= bosf)),
        "forecast_dispersion_atr": float(np.std(pred) / atr),
    }
    p = calibrate(features, cfg)
    return {
        "forecast_key": item["forecast_key"],
        "model_version": "granite-ttm-r2-v17",
        "p": p,
        "features": features,
        "context_last_close": close,
        "context_source": "Yahoo Finance public 15m chart filtered to observed_bar_at",
        "eligible_landmark_age_bars": [0],
        "scored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "calibrator_version": cfg["version"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--calibrator", type=Path, required=True)
    args = ap.parse_args()
    token = os.environ.get("V2_OIDC")
    if not token:
        raise RuntimeError("V2_OIDC is required")
    cfg = json.loads(args.calibrator.read_text(encoding="utf-8"))
    queue = get_json(f"{args.endpoint}?score_queue=1", token).get("queue") or []
    if not queue:
        print(json.dumps({"queue": 0, "scored": 0, "submitted": 0}))
        return

    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    model = get_model(
        model_path=MODEL_PATH,
        context_length=int(cfg["context_bars"]),
        prediction_length=96,
        prefer_longer_context=False,
    )
    model.eval()
    scores = []
    skipped = []
    for item in queue:
        try:
            s = score_item(model, item, cfg)
            if s is None:
                skipped.append({"forecast_key": item.get("forecast_key"), "reason": "ineligible_age_or_invalid_context"})
            else:
                scores.append(s)
        except Exception as exc:
            skipped.append({"forecast_key": item.get("forecast_key"), "reason": type(exc).__name__})

    submitted = 0
    if scores:
        r = requests.post(
            args.endpoint,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": USER_AGENT},
            json={"action": "submit_scores", "scores": scores},
            timeout=60,
        )
        r.raise_for_status()
        submitted = int(r.json().get("accepted") or 0)
    print(json.dumps({"queue": len(queue), "scored": len(scores), "submitted": submitted, "skipped": skipped[:10]}))


if __name__ == "__main__":
    main()
