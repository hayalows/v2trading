from __future__ import annotations

"""Score eligible age-zero Shadow Arena records with two frozen observers.

Observers:
- Granite TTM R2 v1.7
- StateTwin compact logistic student v1.8

The workflow authenticates with a short-lived GitHub Actions OIDC JWT. No Supabase
service key is available to this process. Scores are submitted only through the
restricted gateway and remain hidden from the product UI.
"""

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import torch
from tsfm_public.toolkit.get_model import get_model

TTM_MODEL_PATH = "ibm-granite/granite-timeseries-ttm-r2"
TTM_VERSION = "granite-ttm-r2-v17"
STUDENT_VERSION = "state-twin-student-v18"
TICKERS = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X"}
USER_AGENT = "V2-Shadow-Observers/1.0"
CONTEXT = 512
HORIZON = 16


def get_json(url: str, token: str) -> dict[str, Any]:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}, timeout=45)
    r.raise_for_status()
    return r.json()


def yahoo_ohlc(symbol: str, observed_bar_at: str, days: int = 30) -> pd.DataFrame:
    cutoff = pd.Timestamp(observed_bar_at)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    end_ts = int(cutoff.timestamp())
    start_ts = end_ts - days * 24 * 3600
    ticker = TICKERS[symbol]
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={start_ts}&period2={end_ts + 900}&interval=15m&includePrePost=false&events=div%2Csplits"
    )
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    r.raise_for_status()
    result = (r.json().get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError(f"Yahoo returned no chart for {symbol}")
    payload = result[0]
    ts = payload.get("timestamp") or []
    quote = ((payload.get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for i, t in enumerate(ts):
        dt = pd.Timestamp(int(t), unit="s", tz="UTC")
        if dt > cutoff:
            continue
        vals = []
        for key in ("open", "high", "low", "close"):
            arr = quote.get(key) or []
            v = arr[i] if i < len(arr) else None
            vals.append(v)
        if any(v is None or not np.isfinite(float(v)) for v in vals):
            continue
        rows.append((dt, *map(float, vals)))
    out = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])
    out = out.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    if out.empty or out.iloc[-1].date != cutoff:
        raise RuntimeError(f"No exact completed Yahoo M15 bar at cutoff for {symbol}")
    return out


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs(),
    ], axis=1).max(axis=1)


def efficiency(close: pd.Series, bars: int) -> pd.Series:
    displacement = (close - close.shift(bars)).abs()
    path = close.diff().abs().rolling(bars, min_periods=bars).sum()
    return displacement / path.replace(0, np.nan)


def market_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy().reset_index(drop=True)
    logc = np.log(x["close"].clip(lower=1e-12))
    r1 = logc.diff()
    atr = true_range(x).rolling(14, min_periods=14).mean()
    ema20 = x["close"].ewm(span=20, adjust=False).mean()
    ema50 = x["close"].ewm(span=50, adjust=False).mean()
    hi20 = x["high"].rolling(20, min_periods=20).max()
    lo20 = x["low"].rolling(20, min_periods=20).min()
    hi32 = x["high"].rolling(32, min_periods=32).max()
    lo32 = x["low"].rolling(32, min_periods=32).min()
    body = (x["close"] - x["open"]).abs()
    upper = x["high"] - x[["open", "close"]].max(axis=1)
    lower = x[["open", "close"]].min(axis=1) - x["low"]
    hour = x["date"].dt.hour.astype(float)
    dow = x["date"].dt.dayofweek.astype(float)
    out = pd.DataFrame({
        "date": x["date"],
        "ret1": r1,
        "ret1_bps": r1 * 10000,
        "ret4_bps": (logc - logc.shift(4)) * 10000,
        "ret8_bps": (logc - logc.shift(8)) * 10000,
        "ret16_bps": (logc - logc.shift(16)) * 10000,
        "atr_pct": atr / x["close"].replace(0, np.nan),
        "ema_gap_atr": (ema20 - ema50) / atr.replace(0, np.nan),
        "eff8": efficiency(x["close"], 8),
        "eff32": efficiency(x["close"], 32),
        "vol_fast": r1.rolling(8, min_periods=6).std(),
        "vol_slow": r1.rolling(32, min_periods=20).std(),
        "range_pos32": (x["close"] - lo32) / (hi32 - lo32).replace(0, np.nan),
        "dist_high20_atr": (hi20 - x["close"]) / atr.replace(0, np.nan),
        "dist_low20_atr": (x["close"] - lo20) / atr.replace(0, np.nan),
        "body_atr": body / atr.replace(0, np.nan),
        "upper_wick_atr": upper.clip(lower=0) / atr.replace(0, np.nan),
        "lower_wick_atr": lower.clip(lower=0) / atr.replace(0, np.nan),
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "dow_sin": np.sin(2 * np.pi * dow / 5),
        "dow_cos": np.cos(2 * np.pi * dow / 5),
    })
    out["vol_ratio"] = out["vol_fast"] / out["vol_slow"].replace(0, np.nan)
    return out


def add_cross_pair_features(features: dict[str, pd.DataFrame]) -> None:
    panel = pd.DataFrame()
    symbols = ("EURUSD", "GBPUSD")
    for sym in symbols:
        f = features[sym].set_index("date")
        panel[f"{sym}_ret1"] = f["ret1"]
        panel[f"{sym}_ret8_bps"] = f["ret8_bps"]
    panel = panel.sort_index()
    panel["corr32"] = panel["EURUSD_ret1"].rolling(32, min_periods=24).corr(panel["GBPUSD_ret1"])
    panel["corr96"] = panel["EURUSD_ret1"].rolling(96, min_periods=64).corr(panel["GBPUSD_ret1"])
    for sym in symbols:
        other = "GBPUSD" if sym == "EURUSD" else "EURUSD"
        f = features[sym].set_index("date")
        f["cross_corr32"] = panel["corr32"].reindex(f.index)
        f["cross_corr96"] = panel["corr96"].reindex(f.index)
        f["other_ret8_bps"] = panel[f"{other}_ret8_bps"].reindex(f.index)
        f["relative_ret8_bps"] = f["ret8_bps"] - f["other_ret8_bps"]
        features[sym] = f.reset_index()


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def calibrate_ttm(features: dict[str, float], cfg: dict[str, Any]) -> float:
    score = float(cfg["logistic_intercept"])
    for name in cfg["features"]:
        v = float(features.get(name, cfg["imputer_median"][name]))
        if not math.isfinite(v):
            v = float(cfg["imputer_median"][name])
        z = (v - float(cfg["scaler_mean"][name])) / max(float(cfg["scaler_scale"][name]), 1e-12)
        score += float(cfg["logistic_coef"][name]) * z
    return float(min(1 - 1e-6, max(1e-6, sigmoid(score))))


def student_features(item: dict[str, Any], market: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> dict[str, Any]:
    feats = {sym: market_features(df) for sym, df in market.items()}
    add_cross_pair_features(feats)
    symbol = str(item["symbol"])
    direction = str(item["direction"])
    cutoff = pd.Timestamp(item["observed_bar_at"])
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    q = feats[symbol]
    r = q[q.date == cutoff]
    if len(r) != 1:
        raise RuntimeError("StateTwin feature timestamp alignment failure")
    f = r.iloc[0]
    sign = 1.0 if direction == "long" else -1.0
    raw: dict[str, Any] = {
        "symbol": symbol,
        "direction": direction,
        "stage": f"S{int(item['formation_stage'])}",
        "age_bars": 0.0,
        "log_age": 0.0,
    }
    direct = [
        "ret1_bps", "ret4_bps", "ret8_bps", "ret16_bps", "atr_pct",
        "ema_gap_atr", "eff8", "eff32", "vol_ratio", "range_pos32",
        "dist_high20_atr", "dist_low20_atr", "body_atr", "upper_wick_atr",
        "lower_wick_atr", "hour_sin", "hour_cos", "dow_sin", "dow_cos",
        "cross_corr32", "cross_corr96", "other_ret8_bps", "relative_ret8_bps",
    ]
    for name in direct:
        v = f.get(name)
        raw[name] = float(v) if pd.notna(v) else float("nan")
    raw["dir_ret4_bps"] = sign * raw["ret4_bps"]
    raw["dir_ret8_bps"] = sign * raw["ret8_bps"]
    raw["dir_ret16_bps"] = sign * raw["ret16_bps"]
    raw["dir_ema_gap_atr"] = sign * raw["ema_gap_atr"]
    for name in cfg["numeric_features"]:
        if name not in raw:
            raise RuntimeError(f"Missing StateTwin feature {name}")
    return raw


def score_student(raw: dict[str, Any], cfg: dict[str, Any]) -> float:
    vector: list[float] = []
    for name in cfg["categorical_features"]:
        value = raw.get(name)
        if value is None:
            value = cfg["categorical_fill"][name]
        value = str(value)
        vector.extend(1.0 if value == str(cat) else 0.0 for cat in cfg["categories"][name])
    for name in cfg["numeric_features"]:
        v = raw.get(name)
        try:
            x = float(v)
        except (TypeError, ValueError):
            x = float("nan")
        if not math.isfinite(x):
            x = float(cfg["numeric_imputer_median"][name])
        mean = float(cfg["numeric_scaler_mean"][name])
        scale = max(float(cfg["numeric_scaler_scale"][name]), 1e-12)
        vector.append((x - mean) / scale)
    coef = [float(x) for x in cfg["logistic_coef"]]
    if len(vector) != len(coef):
        raise RuntimeError(f"StateTwin student vector mismatch {len(vector)} != {len(coef)}")
    logit = float(cfg["logistic_intercept"]) + float(np.dot(np.asarray(vector, float), np.asarray(coef, float)))
    return float(min(1 - 1e-6, max(1e-6, sigmoid(logit))))


def score_ttm(model: Any, item: dict[str, Any], market: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> dict[str, Any]:
    snapshot = item.get("feature_snapshot") or {}
    snap_market = snapshot.get("market") or {}
    direction = str(item["direction"])
    atr = float(snap_market.get("atr15") or 0)
    bos = snap_market.get("bosReference")
    if direction not in ("long", "short") or not atr or bos is None:
        raise RuntimeError("TTM requires direction, ATR and frozen BOS reference")
    closes = market[item["symbol"]].close.to_numpy(np.float32)
    if len(closes) < int(cfg["context_bars"]):
        raise RuntimeError("Insufficient TTM context")
    ctx = closes[-int(cfg["context_bars"]):]
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
    return {
        "forecast_key": item["forecast_key"],
        "model_version": TTM_VERSION,
        "p": calibrate_ttm(features, cfg),
        "features": features,
        "context_last_close": close,
        "context_source": "Yahoo Finance public M15 OHLC filtered exactly to observed_bar_at",
        "calibrator_version": cfg["version"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--ttm-calibrator", type=Path, required=True)
    ap.add_argument("--student", type=Path, required=True)
    args = ap.parse_args()
    token = os.environ.get("V2_OIDC")
    if not token:
        raise RuntimeError("V2_OIDC is required")
    ttm_cfg = json.loads(args.ttm_calibrator.read_text(encoding="utf-8"))
    student_cfg = json.loads(args.student.read_text(encoding="utf-8"))
    if student_cfg.get("historical_gate") != "PASS":
        raise RuntimeError("StateTwin student historical gate is not PASS")

    queue_payload = get_json(f"{args.endpoint}?score_queue=1", token)
    queue = queue_payload.get("queue") or []
    if not queue:
        print(json.dumps({"queue": 0, "scores": 0, "submitted": 0}))
        return

    needs_ttm = any((x.get("missing_models") or {}).get(TTM_VERSION) for x in queue)
    model = None
    if needs_ttm:
        torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
        model = get_model(
            model_path=TTM_MODEL_PATH,
            context_length=int(ttm_cfg["context_bars"]),
            prediction_length=96,
            prefer_longer_context=False,
        )
        model.eval()

    scores: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in queue:
        key = item.get("forecast_key")
        try:
            if int(item.get("landmark_age_bars", -1)) != 0:
                raise RuntimeError("ineligible_landmark_age")
            market = {
                "EURUSD": yahoo_ohlc("EURUSD", item["observed_bar_at"]),
                "GBPUSD": yahoo_ohlc("GBPUSD", item["observed_bar_at"]),
            }
            missing = item.get("missing_models") or {}
            if missing.get(STUDENT_VERSION):
                raw = student_features(item, market, student_cfg)
                scores.append({
                    "forecast_key": key,
                    "model_version": STUDENT_VERSION,
                    "p": score_student(raw, student_cfg),
                    "features": {name: raw.get(name) for name in student_cfg["numeric_features"]},
                    "context_source": "Yahoo Finance public M15 OHLC; frozen v1.6 causal StateTwin feature family",
                    "calibrator_version": student_cfg["version"],
                })
            if missing.get(TTM_VERSION):
                if model is None:
                    raise RuntimeError("TTM model not loaded")
                scores.append(score_ttm(model, item, market, ttm_cfg))
        except Exception as exc:
            skipped.append({"forecast_key": key, "reason": f"{type(exc).__name__}:{exc}"[:240]})

    submitted = 0
    response: dict[str, Any] = {}
    if scores:
        r = requests.post(
            args.endpoint,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": USER_AGENT},
            json={"action": "submit_scores", "scores": scores},
            timeout=60,
        )
        r.raise_for_status()
        response = r.json()
        submitted = int(response.get("accepted") or 0)
    print(json.dumps({"queue": len(queue), "scores": len(scores), "submitted": submitted, "gateway": response, "skipped": skipped[:10]}))


if __name__ == "__main__":
    main()
