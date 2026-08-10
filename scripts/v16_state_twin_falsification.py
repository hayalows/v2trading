from __future__ import annotations

"""Post-gate falsification audit for V2 StateTwin v1.6.

This audit is deliberately stricter than the preregistered landmark gate. It keeps
only the earliest eligible landmark from each formation campaign, checks year-boundary
contamination, and bootstraps whole independent campaigns. It does not alter the
frozen acceptance criteria or retune the model.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y)
    score = 0.0
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        n = int(mask.sum())
        if n:
            score += n / total * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(score)


def score_frame(df: pd.DataFrame) -> dict:
    y = df.event.to_numpy(int)
    p = df.probability.to_numpy(float)
    b = df.base_probability.to_numpy(float)
    model_brier = float(brier_score_loss(y, p))
    base_brier = float(brier_score_loss(y, b))
    return {
        "n": int(len(df)),
        "event_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)),
        "brier": model_brier,
        "base_brier": base_brier,
        "brier_improvement": base_brier - model_brier,
        "ece10": ece(y, p),
    }


def bootstrap_campaigns(df: pd.DataFrame, repeats: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n = len(df)
    improvements = np.empty(repeats, dtype=float)
    aucs = np.empty(repeats, dtype=float)
    for i in range(repeats):
        idx = rng.integers(0, n, n)
        q = df.iloc[idx]
        y = q.event.to_numpy(int)
        p = q.probability.to_numpy(float)
        b = q.base_probability.to_numpy(float)
        improvements[i] = brier_score_loss(y, b) - brier_score_loss(y, p)
        aucs[i] = roc_auc_score(y, p)
    return {
        "repeats": repeats,
        "seed": seed,
        "brier_improvement_ci95": [float(x) for x in np.quantile(improvements, [0.025, 0.975])],
        "brier_improvement_median": float(np.median(improvements)),
        "auc_ci95": [float(x) for x in np.quantile(aucs, [0.025, 0.975])],
        "auc_median": float(np.median(aucs)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--primary-horizon", type=int, default=16)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    pred = pd.read_csv(args.predictions, parse_dates=["time"])
    start_text = pred["campaign_id"].str.split(":", n=2).str[2]
    pred["campaign_start"] = pd.to_datetime(start_text, utc=True)
    pred["campaign_start_year"] = pred.campaign_start.dt.year
    boundary = pred[pred.campaign_start_year != pred.year]

    primary = pred[pred.horizon_bars == args.primary_horizon].copy()
    one = (
        primary.sort_values(["campaign_id", "age_bars", "time"])
        .groupby("campaign_id", as_index=False)
        .first()
    )
    completed_years = one[one.year <= 2025].copy()

    yearly = {}
    for year, q in completed_years.groupby("year"):
        yearly[str(int(year))] = score_frame(q)

    report = {
        "audit": "V2 v1.6 StateTwin independent-campaign falsification",
        "policy": "Post-gate audit only. It does not change the preregistered acceptance criteria or tune the model.",
        "primary_horizon_bars": int(args.primary_horizon),
        "year_boundary_landmark_rows": int(len(boundary)),
        "year_boundary_campaigns": int(boundary.campaign_id.nunique()),
        "one_landmark_per_campaign_all_oos": score_frame(one),
        "one_landmark_per_campaign_2022_2025": score_frame(completed_years),
        "yearly_2022_2025": yearly,
        "campaign_bootstrap_2022_2025": bootstrap_campaigns(completed_years, args.bootstrap, args.seed),
        "interpretation": "If Brier improvement remains positive and the campaign-bootstrap interval stays above zero, the landmark result is not explained by repeated observations from the same formation campaign.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
