from __future__ import annotations

"""Ablation tests for the public-data V2 proxy trade ledger.

Compares price/setup features with the same model plus raw economic-calendar context.
It also writes simple event-proximity diagnostics. These tests are deliberately
separate from the event generator so a negative macro result is preserved rather
than tuned away.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PRICE_FEATURES = [
    "symbol", "direction", "entry_hour", "entry_dow", "is_london", "is_new_york", "is_overlap",
    "atr", "risk_distance", "risk_atr", "sweep_depth_atr", "sweep_wick_ratio",
    "bos_displacement_atr", "zone_width_atr", "sweep_to_bos_bars", "bos_to_entry_bars",
    "volume_z", "trend20_atr", "range_position_20", "cost_as_r",
]
CALENDAR_FEATURES = [
    "high_event_30m", "high_event_120m", "minutes_to_nearest_high_event",
    "nearby_event_count_120m", "nearest_event_surprise", "nearest_event_currency",
]


def performance(x: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(x, errors="coerce").dropna()
    gains = s[s > 0].sum()
    losses = -s[s < 0].sum()
    return {
        "n": int(len(s)),
        "win_rate": float((s > 0).mean()) if len(s) else np.nan,
        "expectancy_r": float(s.mean()) if len(s) else np.nan,
        "profit_factor": float(gains / losses) if losses > 0 else np.inf,
    }


def build_model(frame: pd.DataFrame, features: list[str]) -> Pipeline:
    cats = [c for c in features if not pd.api.types.is_numeric_dtype(frame[c])]
    nums = [c for c in features if c not in cats]
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), nums),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cats),
    ])
    model = LGBMClassifier(
        n_estimators=240, learning_rate=0.025, num_leaves=15, max_depth=4,
        min_child_samples=45, colsample_bytree=0.85, subsample=0.9,
        reg_alpha=0.6, reg_lambda=1.2, random_state=42, verbose=-1,
    )
    return Pipeline([("pre", pre), ("model", model)])


def walk_forward(df: pd.DataFrame, features: list[str]) -> dict[str, float]:
    pred_rows = []
    for year in [2023, 2024, 2025]:
        train = df[df.year < year]
        test = df[df.year == year]
        model = build_model(train, features)
        model.fit(train[features], train.win)
        p_train = model.predict_proba(train[features])[:, 1]
        p_test = model.predict_proba(test[features])[:, 1]
        q50, q70 = np.quantile(p_train, [0.50, 0.70])
        z = test[["net_r", "win"]].copy()
        z["p_win"] = p_test
        z["q50"] = p_test >= q50
        z["q70"] = p_test >= q70
        pred_rows.append(z)
    pred = pd.concat(pred_rows, ignore_index=True)
    return {
        "pooled_auc": float(roc_auc_score(pred.win, pred.p_win)),
        "pooled_brier": float(brier_score_loss(pred.win, pred.p_win)),
        "all_expectancy_r": float(pred.net_r.mean()),
        "q50_n": int(pred.q50.sum()),
        "q50_expectancy_r": float(pred.loc[pred.q50, "net_r"].mean()),
        "q70_n": int(pred.q70.sum()),
        "q70_expectancy_r": float(pred.loc[pred.q70, "net_r"].mean()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trades", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.trades)
    df = df[df.net_r.notna()].copy()
    df["entry_time"] = pd.to_datetime(df.entry_time, utc=True)
    df["year"] = df.entry_time.dt.year
    df["win"] = (df.net_r > 0).astype(int)

    rows = []
    for name, features in [
        ("price_structure_only", PRICE_FEATURES),
        ("price_structure_plus_calendar", PRICE_FEATURES + CALENDAR_FEATURES),
    ]:
        rows.append({"feature_set": name, **walk_forward(df, features)})
    pd.DataFrame(rows).to_csv(args.out / "public_model_ablation.csv", index=False)

    event_rows = []
    for field in ["high_event_30m", "high_event_120m"]:
        for value, g in df.groupby(field):
            event_rows.append({"field": field, "value": int(value), **performance(g.net_r)})
    pd.DataFrame(event_rows).to_csv(args.out / "public_event_proximity.csv", index=False)

    symbol_event = df.groupby(["symbol", "high_event_30m"]).agg(
        n=("net_r", "size"), win_rate=("win", "mean"), expectancy_r=("net_r", "mean")
    ).reset_index()
    symbol_event.to_csv(args.out / "public_symbol_event30.csv", index=False)


if __name__ == "__main__":
    main()
