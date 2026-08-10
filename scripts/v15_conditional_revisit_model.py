from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

HORIZONS = (24, 48, 96)
CAT = ["symbol", "direction"]
NUM = ["risk_atr", "poi_width_atr", "sweep_to_bos_bars", "bos_hour", "bos_dow"]


def prepare(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    x = df.copy()
    x["sweep_time"] = pd.to_datetime(x["sweep_time"], utc=True, errors="coerce")
    x["bos_time"] = pd.to_datetime(x["bos_time"], utc=True, errors="coerce")
    x["atr"] = pd.to_numeric(x["atr"], errors="coerce")
    x["risk_atr"] = pd.to_numeric(x["risk_atr"], errors="coerce")
    x["poi_low"] = pd.to_numeric(x["poi_low"], errors="coerce")
    x["poi_high"] = pd.to_numeric(x["poi_high"], errors="coerce")
    x["available_follow_bars"] = pd.to_numeric(x["available_follow_bars"], errors="coerce")
    x["midpoint_fill_bars"] = pd.to_numeric(x["midpoint_fill_bars"], errors="coerce")
    x = x[x["available_follow_bars"] >= horizon].copy()
    x["event"] = (x["midpoint_fill_bars"].notna() & (x["midpoint_fill_bars"] <= horizon)).astype(int)
    x["poi_width_atr"] = (x["poi_high"] - x["poi_low"]) / x["atr"].replace(0, np.nan)
    x["sweep_to_bos_bars"] = ((x["bos_time"] - x["sweep_time"]).dt.total_seconds() / 900).round()
    x["bos_hour"] = x["bos_time"].dt.hour
    x["bos_dow"] = x["bos_time"].dt.dayofweek
    x["year"] = x["bos_time"].dt.year
    return x.dropna(subset=["year", "event", "symbol", "direction"]).copy()


def model() -> Pipeline:
    pre = ColumnTransformer([
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CAT),
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUM),
    ])
    return Pipeline([("pre", pre), ("clf", LogisticRegression(C=0.5, max_iter=2000, class_weight=None))])


def evaluate(df: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, dict]:
    rows = []
    pooled_y, pooled_p, pooled_base = [], [], []
    years = sorted(int(y) for y in df.year.dropna().unique())
    for year in years:
        train = df[df.year < year]
        test = df[df.year == year]
        if len(train) < 250 or len(test) < 50 or train.event.nunique() < 2 or test.event.nunique() < 2:
            continue
        m = model()
        m.fit(train[CAT + NUM], train.event)
        p = m.predict_proba(test[CAT + NUM])[:, 1]
        base = float(train.event.mean())
        brier = brier_score_loss(test.event, p)
        base_brier = brier_score_loss(test.event, np.full(len(test), base))
        auc = roc_auc_score(test.event, p)
        rows.append({"horizon_bars": horizon, "test_year": year, "n": len(test), "event_rate": float(test.event.mean()), "auc": float(auc), "brier": float(brier), "base_rate": base, "base_brier": float(base_brier), "brier_improvement": float(base_brier - brier)})
        pooled_y.extend(test.event.tolist()); pooled_p.extend(p.tolist()); pooled_base.extend([base] * len(test))
    if not pooled_y:
        return pd.DataFrame(rows), {"horizon_bars": horizon, "n": 0}
    y = np.asarray(pooled_y); p = np.asarray(pooled_p); b = np.asarray(pooled_base)
    pooled = {
        "horizon_bars": horizon,
        "n": int(len(y)),
        "event_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "base_brier": float(brier_score_loss(y, b)),
        "brier_improvement": float(brier_score_loss(y, b) - brier_score_loss(y, p)),
        "positive_brier_years": int(sum(r["brier_improvement"] > 0 for r in rows)),
        "years": [int(r["test_year"]) for r in rows],
    }
    return pd.DataFrame(rows), pooled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(args.candidates)
    all_years = []
    pooled = []
    for h in HORIZONS:
        d = prepare(raw, h)
        yrs, summary = evaluate(d, h)
        all_years.append(yrs)
        pooled.append(summary)
    year_df = pd.concat(all_years, ignore_index=True) if all_years else pd.DataFrame()
    pooled_df = pd.DataFrame(pooled)
    year_df.to_csv(args.out / "v15_revisit_walkforward.csv", index=False)
    pooled_df.to_csv(args.out / "v15_revisit_pooled.csv", index=False)
    primary = next((x for x in pooled if x.get("horizon_bars") == 48), {"n": 0})
    accepted = bool(primary.get("n", 0) >= 500 and primary.get("auc", 0) >= 0.55 and primary.get("brier_improvement", -1) > 0 and primary.get("positive_brier_years", 0) >= 3)
    report = {
        "study": "V2 v1.5 conditional POI revisit baseline",
        "features": CAT + NUM,
        "primary_horizon_bars": 48,
        "pooled": pooled,
        "decision": "ACCEPT_RESEARCH_CANDIDATE" if accepted else "REJECT_PREDICTIVE_UI",
        "product_rule": "Never label this as win probability, execution probability, or a trade signal.",
    }
    (args.out / "v15_revisit_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
