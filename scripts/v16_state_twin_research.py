from __future__ import annotations

"""V2 v1.6 StateTwin dynamic structural-transition research.

Primary question: while a EURUSD/GBPUSD formation is still at Stage 3/4, can a
causal market-state vector improve the probability estimate that same-direction
BOS (Stage 5+) arrives within the next fixed horizon?

This is research-only. It does not model trade P/L or broker execution.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from public_data_v2_proxy import load_market
from v06_prospective_detector_validation_np import replay

SYMBOLS = ("EURUSD", "GBPUSD")
HORIZONS = (8, 16, 32)
PRIMARY_HORIZON = 16
LANDMARKS = (0, 2, 4, 8, 12, 16, 24)
CAT = ["symbol", "direction", "stage"]
NUM = [
    "age_bars", "log_age", "ret1_bps", "ret4_bps", "ret8_bps", "ret16_bps",
    "dir_ret4_bps", "dir_ret8_bps", "dir_ret16_bps", "atr_pct",
    "ema_gap_atr", "dir_ema_gap_atr", "eff8", "eff32", "vol_ratio",
    "range_pos32", "dist_high20_atr", "dist_low20_atr", "body_atr",
    "upper_wick_atr", "lower_wick_atr", "hour_sin", "hour_cos",
    "dow_sin", "dow_cos", "cross_corr32", "cross_corr96",
    "other_ret8_bps", "relative_ret8_bps",
]


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
    for sym in SYMBOLS:
        f = features[sym].set_index("date")
        panel[f"{sym}_ret1"] = f["ret1"]
        panel[f"{sym}_ret8_bps"] = f["ret8_bps"]
    panel = panel.sort_index()
    panel["corr32"] = panel[f"{SYMBOLS[0]}_ret1"].rolling(32, min_periods=24).corr(panel[f"{SYMBOLS[1]}_ret1"])
    panel["corr96"] = panel[f"{SYMBOLS[0]}_ret1"].rolling(96, min_periods=64).corr(panel[f"{SYMBOLS[1]}_ret1"])
    for sym in SYMBOLS:
        other = SYMBOLS[1] if sym == SYMBOLS[0] else SYMBOLS[0]
        f = features[sym].set_index("date")
        f["cross_corr32"] = panel["corr32"].reindex(f.index)
        f["cross_corr96"] = panel["corr96"].reindex(f.index)
        f["other_ret8_bps"] = panel[f"{other}_ret8_bps"].reindex(f.index)
        f["relative_ret8_bps"] = f["ret8_bps"] - f["other_ret8_bps"]
        features[sym] = f.reset_index()


def find_campaigns(states: pd.DataFrame) -> list[dict]:
    s = states.reset_index(drop=True)
    rows: list[dict] = []
    i = 0
    campaign_no = 0
    while i < len(s):
        r = s.iloc[i]
        stage = int(r.stage)
        direction = r.direction
        if stage not in (3, 4) or direction not in {"long", "short"}:
            i += 1
            continue
        campaign_no += 1
        start = i
        event_i = None
        reset_i = None
        j = i + 1
        while j < len(s):
            rr = s.iloc[j]
            st = int(rr.stage)
            rd = rr.direction
            if rd == direction and st >= 5:
                event_i = j
                break
            if st <= 2 or (rd in {"long", "short"} and rd != direction):
                reset_i = j
                break
            j += 1
        end = event_i if event_i is not None else reset_i if reset_i is not None else len(s)
        rows.append({
            "campaign_id": f"{r.symbol}:{campaign_no}:{pd.Timestamp(r.time).isoformat()}",
            "start_i": start,
            "end_i": end,
            "event_i": event_i,
            "reset_i": reset_i,
            "direction": direction,
        })
        i = max(i + 1, end + 1 if end < len(s) else len(s))
    return rows


def landmark_dataset(
    states: pd.DataFrame,
    feat: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    s = states.reset_index(drop=True)
    rows: list[dict] = []
    campaigns = find_campaigns(s)
    for c in campaigns:
        for age in LANDMARKS:
            idx = c["start_i"] + age
            if idx >= c["end_i"] or idx >= len(s):
                continue
            cur = s.iloc[idx]
            if int(cur.stage) not in (3, 4) or cur.direction != c["direction"]:
                continue
            event_i, reset_i = c["event_i"], c["reset_i"]
            if event_i is not None and event_i > idx and event_i - idx <= horizon:
                y = 1
            elif reset_i is not None and reset_i > idx and reset_i - idx <= horizon:
                y = 0
            elif idx + horizon < len(s):
                y = 0
            else:
                continue  # right-censored by dataset boundary

            raw_i = int(cur.bar_i)
            if raw_i < 0 or raw_i >= len(feat):
                continue
            f = feat.iloc[raw_i]
            sign = 1.0 if cur.direction == "long" else -1.0
            rec = {
                "campaign_id": c["campaign_id"],
                "symbol": cur.symbol,
                "time": pd.Timestamp(cur.time),
                "year": int(pd.Timestamp(cur.time).year),
                "direction": cur.direction,
                "stage": f"S{int(cur.stage)}",
                "age_bars": float(age),
                "log_age": math.log1p(age),
                "event": int(y),
                "horizon_bars": int(horizon),
            }
            for name in [
                "ret1_bps", "ret4_bps", "ret8_bps", "ret16_bps", "atr_pct",
                "ema_gap_atr", "eff8", "eff32", "vol_ratio", "range_pos32",
                "dist_high20_atr", "dist_low20_atr", "body_atr",
                "upper_wick_atr", "lower_wick_atr", "hour_sin", "hour_cos",
                "dow_sin", "dow_cos", "cross_corr32", "cross_corr96",
                "other_ret8_bps", "relative_ret8_bps",
            ]:
                rec[name] = float(f[name]) if pd.notna(f[name]) else np.nan
            rec["dir_ret4_bps"] = sign * rec["ret4_bps"]
            rec["dir_ret8_bps"] = sign * rec["ret8_bps"]
            rec["dir_ret16_bps"] = sign * rec["ret16_bps"]
            rec["dir_ema_gap_atr"] = sign * rec["ema_gap_atr"]
            rows.append(rec)
    return pd.DataFrame(rows)


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), CAT),
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), NUM),
    ], remainder="drop")


def component_predictions(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    pp = preprocessor()
    x_train = pp.fit_transform(train[CAT + NUM])
    x_test = pp.transform(test[CAT + NUM])
    y = train.event.to_numpy(int)

    linear = LogisticRegression(C=0.5, max_iter=2500, random_state=42)
    linear.fit(x_train, y)

    nonlinear = LGBMClassifier(
        n_estimators=240,
        learning_rate=0.035,
        num_leaves=15,
        max_depth=4,
        min_child_samples=50,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        reg_alpha=0.2,
        random_state=42,
        verbosity=-1,
    )
    nonlinear.fit(x_train, y)

    k = min(45, max(12, int(round(math.sqrt(len(train))))))
    twin = KNeighborsClassifier(n_neighbors=k, weights="distance", p=2)
    twin.fit(x_train, y)

    return {
        "linear": linear.predict_proba(x_test)[:, 1],
        "nonlinear": nonlinear.predict_proba(x_test)[:, 1],
        "twin": twin.predict_proba(x_test)[:, 1],
    }


def weight_grid() -> list[tuple[float, float, float]]:
    vals = [0.0, 0.25, 0.5, 0.75, 1.0]
    out = []
    for a in vals:
        for b in vals:
            c = round(1.0 - a - b, 10)
            if c >= 0 and c in vals:
                out.append((a, b, c))
    return out


def choose_weights(y: np.ndarray, p: dict[str, np.ndarray]) -> tuple[float, float, float]:
    best = (1.0, 0.0, 0.0)
    score = float("inf")
    for w in weight_grid():
        q = np.clip(w[0] * p["linear"] + w[1] * p["nonlinear"] + w[2] * p["twin"], 1e-6, 1 - 1e-6)
        b = brier_score_loss(y, q)
        if b < score - 1e-12:
            score, best = b, w
    return best


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = len(y)
    out = 0.0
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        n = int(mask.sum())
        if n:
            out += n / total * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(out)


def safe_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None


def metrics(y: np.ndarray, p: np.ndarray, base: np.ndarray) -> dict:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    base = np.clip(np.asarray(base, float), 1e-6, 1 - 1e-6)
    brier = float(brier_score_loss(y, p))
    bb = float(brier_score_loss(y, base))
    return {
        "n": int(len(y)),
        "event_rate": float(np.mean(y)),
        "auc": safe_auc(y, p),
        "brier": brier,
        "base_brier": bb,
        "brier_improvement": bb - brier,
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "ece10": ece(y, p, 10),
    }


def evaluate_walkforward(df: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows = df[df.horizon_bars == horizon].sort_values("time").reset_index(drop=True)
    years = sorted(int(x) for x in rows.year.unique())
    yearly = []
    predictions = []

    for test_year in years:
        train = rows[rows.year < test_year].copy()
        test = rows[rows.year == test_year].copy()
        train_years = sorted(int(x) for x in train.year.unique())
        if len(train_years) < 2 or len(train) < 500 or len(test) < 100:
            continue
        val_year = train_years[-1]
        fit = train[train.year < val_year].copy()
        val = train[train.year == val_year].copy()
        if len(fit) < 300 or len(val) < 100 or fit.event.nunique() < 2 or val.event.nunique() < 2 or test.event.nunique() < 2:
            continue

        inner = component_predictions(fit, val)
        weights = choose_weights(val.event.to_numpy(int), inner)
        outer = component_predictions(train, test)
        p = np.clip(weights[0] * outer["linear"] + weights[1] * outer["nonlinear"] + weights[2] * outer["twin"], 1e-6, 1 - 1e-6)
        base_rate = float(train.event.mean())
        base = np.full(len(test), base_rate)
        m = metrics(test.event.to_numpy(int), p, base)
        yearly.append({
            "horizon_bars": horizon,
            "test_year": test_year,
            **m,
            "base_rate": base_rate,
            "w_linear": weights[0],
            "w_nonlinear": weights[1],
            "w_twin": weights[2],
            "fit_through_year": val_year,
        })
        z = test[["campaign_id", "symbol", "time", "year", "event", "stage", "direction", "age_bars"]].copy()
        z["horizon_bars"] = horizon
        z["probability"] = p
        z["base_probability"] = base
        z["w_linear"] = weights[0]
        z["w_nonlinear"] = weights[1]
        z["w_twin"] = weights[2]
        predictions.append(z)

    pred = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    yr = pd.DataFrame(yearly)
    if pred.empty:
        return yr, pred, {"horizon_bars": horizon, "n": 0}
    y = pred.event.to_numpy(int)
    p = pred.probability.to_numpy(float)
    b = pred.base_probability.to_numpy(float)
    pooled = {"horizon_bars": horizon, **metrics(y, p, b)}
    pooled["positive_brier_years"] = int((yr.brier_improvement > 0).sum()) if len(yr) else 0
    pooled["test_years"] = yr.test_year.astype(int).tolist() if len(yr) else []
    pooled["pair_results"] = {}
    for sym in SYMBOLS:
        q = pred[pred.symbol == sym]
        if q.empty:
            continue
        pooled["pair_results"][sym] = metrics(
            q.event.to_numpy(int), q.probability.to_numpy(float), q.base_probability.to_numpy(float)
        )
    return yr, pred, pooled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", default="2020-01-01")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(args.start, tz="UTC")

    markets: dict[str, pd.DataFrame] = {}
    feats: dict[str, pd.DataFrame] = {}
    states: dict[str, pd.DataFrame] = {}
    for sym in SYMBOLS:
        market = load_market(args.data_dir / f"{sym}-15m.feather", sym)
        market = market[market.date >= start].reset_index(drop=True)
        markets[sym] = market
        feats[sym] = market_features(market)
    add_cross_pair_features(feats)

    for sym in SYMBOLS:
        states[sym] = replay(markets[sym], sym)

    samples = []
    for horizon in HORIZONS:
        for sym in SYMBOLS:
            d = landmark_dataset(states[sym], feats[sym], horizon)
            if len(d):
                samples.append(d)
    data = pd.concat(samples, ignore_index=True) if samples else pd.DataFrame()
    if data.empty:
        raise RuntimeError("No StateTwin landmark samples were generated")
    data.to_csv(args.out / "v16_state_twin_landmarks.csv", index=False)

    yearly_all = []
    pred_all = []
    pooled_all = []
    for horizon in HORIZONS:
        yr, pred, pooled = evaluate_walkforward(data, horizon)
        yearly_all.append(yr)
        if len(pred):
            pred_all.append(pred)
        pooled_all.append(pooled)

    yearly = pd.concat(yearly_all, ignore_index=True) if yearly_all else pd.DataFrame()
    predictions = pd.concat(pred_all, ignore_index=True) if pred_all else pd.DataFrame()
    pooled_df = pd.json_normalize(pooled_all, sep=".")
    yearly.to_csv(args.out / "v16_state_twin_walkforward.csv", index=False)
    predictions.to_csv(args.out / "v16_state_twin_oos_predictions.csv", index=False)
    pooled_df.to_csv(args.out / "v16_state_twin_pooled.csv", index=False)

    primary = next((x for x in pooled_all if x.get("horizon_bars") == PRIMARY_HORIZON), {"n": 0})
    pairs = primary.get("pair_results", {})
    accepted = bool(
        primary.get("n", 0) >= 1000
        and (primary.get("auc") or 0) >= 0.58
        and primary.get("brier_improvement", -1) > 0
        and primary.get("positive_brier_years", 0) >= 3
        and primary.get("ece10", 1) <= 0.08
        and all(pairs.get(s, {}).get("brier_improvement", -1) >= 0 for s in SYMBOLS)
    )
    report = {
        "study": "V2 v1.6 StateTwin dynamic structural-transition model",
        "scope": list(SYMBOLS),
        "primary_horizon_bars": PRIMARY_HORIZON,
        "landmark_ages": list(LANDMARKS),
        "features": CAT + NUM,
        "samples": int(len(data)),
        "campaigns": int(data.campaign_id.nunique()),
        "pooled": pooled_all,
        "decision": "ACCEPT_RESEARCH_CANDIDATE" if accepted else "KEEP_PROBABILITY_WITHHELD",
        "product_rule": "Even a pass requires prospective live calibration before Focus may show a current structural-transition probability. This is never a buy/sell or broker-execution probability.",
    }
    (args.out / "v16_state_twin_summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
