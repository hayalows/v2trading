from __future__ import annotations

"""V2 v1.8 Model Council research.

Preregistered questions:
A) Does Granite TTM R2 add incremental information beyond the StateTwin v1.6 teacher?
B) Can the StateTwin teacher be distilled into a compact logistic shadow scorer?

Research only. No execution or product probability claims.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from public_data_v2_proxy import load_market
from v06_prospective_detector_validation_np import replay
from v16_state_twin_research import (
    SYMBOLS,
    CAT,
    NUM,
    add_cross_pair_features,
    choose_weights,
    component_predictions,
    landmark_dataset,
    market_features,
    preprocessor,
)
from v17_ttm_challenger import (
    FEATURES as TTM_FEATURES,
    HORIZON,
    build_samples,
    run_ttm,
)

COMPLETED_YEARS = (2022, 2023, 2024, 2025)
BLEND_GRID = tuple(round(x * 0.05, 2) for x in range(21))
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 1808
DISAGREEMENT_THRESHOLD = 0.15


def safe_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    p = np.asarray(p, float)
    y = np.asarray(y, int)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = 0.0
    n = len(y)
    if not n:
        return float("nan")
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.any():
            out += float(m.sum()) / n * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(out)


def metrics(y: np.ndarray, p: np.ndarray, base: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y, int)
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
        "ece10": ece(y, p, 10),
    }


def combine(parts: dict[str, np.ndarray], w: tuple[float, float, float]) -> np.ndarray:
    return np.clip(w[0] * parts["linear"] + w[1] * parts["nonlinear"] + w[2] * parts["twin"], 1e-6, 1 - 1e-6)


def fit_ttm_calibrator(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=0.5, max_iter=2000, random_state=42)),
    ])
    pipe.fit(train[TTM_FEATURES], train.event)
    return np.clip(pipe.predict_proba(test[TTM_FEATURES])[:, 1], 1e-6, 1 - 1e-6)


def choose_council_weight(y: np.ndarray, state_p: np.ndarray, ttm_p: np.ndarray) -> float:
    """Return StateTwin weight. Ties prefer StateTwin, per frozen protocol."""
    best_w = 1.0
    best = float("inf")
    for w in sorted(BLEND_GRID, reverse=True):
        p = np.clip(w * state_p + (1.0 - w) * ttm_p, 1e-6, 1 - 1e-6)
        b = float(brier_score_loss(y, p))
        if b < best - 1e-12:
            best = b
            best_w = float(w)
    return best_w


def aligned_dataset(data_dir: Path, start: pd.Timestamp, batch_size: int) -> pd.DataFrame:
    markets: dict[str, pd.DataFrame] = {}
    feats: dict[str, pd.DataFrame] = {}
    states: dict[str, pd.DataFrame] = {}
    state_rows: list[pd.DataFrame] = []
    ttm_meta: list[pd.DataFrame] = []
    ttm_ctx: list[np.ndarray] = []

    for sym in SYMBOLS:
        market = load_market(data_dir / f"{sym}-15m.feather", sym)
        market = market[market.date >= start].reset_index(drop=True)
        markets[sym] = market
        feats[sym] = market_features(market)
        states[sym] = replay(market, sym).reset_index(drop=True)

    add_cross_pair_features(feats)

    for sym in SYMBOLS:
        s = landmark_dataset(states[sym], feats[sym], HORIZON)
        s = s[s.age_bars == 0].copy()
        state_rows.append(s)
        m, c = build_samples(markets[sym], sym)
        ttm_meta.append(m)
        ttm_ctx.append(c)

    state = pd.concat(state_rows, ignore_index=True)
    meta = pd.concat(ttm_meta, ignore_index=True)
    ctx = np.concatenate(ttm_ctx, axis=0)
    if len(meta) != len(ctx):
        raise RuntimeError("TTM metadata/context alignment failure")

    ttm = run_ttm(ctx, meta, batch_size)
    ttm.replace([np.inf, -np.inf], np.nan, inplace=True)
    keys = ["symbol", "campaign_id", "time", "direction", "event"]
    keep_ttm = keys + TTM_FEATURES + ["bos_reference", "atr", "close"]
    merged = state.merge(ttm[keep_ttm], on=keys, how="inner", validate="one_to_one")
    merged = merged.sort_values("time").reset_index(drop=True)
    if merged.empty:
        raise RuntimeError("No intersected StateTwin/TTM campaigns")
    return merged


def yearly_predictions(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    pred_tables: list[pd.DataFrame] = []

    for test_year in sorted(int(x) for x in data.year.unique() if int(x) >= 2022):
        train = data[data.year < test_year].copy()
        test = data[data.year == test_year].copy()
        train_years = sorted(int(x) for x in train.year.unique())
        if len(train_years) < 2 or len(train) < 500 or len(test) < 50:
            continue

        val_year = train_years[-1]
        fit = train[train.year < val_year].copy()
        val = train[train.year == val_year].copy()
        if len(fit) < 300 or len(val) < 50 or fit.event.nunique() < 2 or val.event.nunique() < 2:
            continue

        state_inner_parts = component_predictions(fit, val)
        state_weights = choose_weights(val.event.to_numpy(int), state_inner_parts)
        state_val = combine(state_inner_parts, state_weights)
        ttm_val = fit_ttm_calibrator(fit, val)
        council_w = choose_council_weight(val.event.to_numpy(int), state_val, ttm_val)

        state_outer_parts = component_predictions(train, test)
        state_p = combine(state_outer_parts, state_weights)
        student_p = np.clip(state_outer_parts["linear"], 1e-6, 1 - 1e-6)
        ttm_p = fit_ttm_calibrator(train, test)
        council_p = np.clip(council_w * state_p + (1.0 - council_w) * ttm_p, 1e-6, 1 - 1e-6)

        base_p = float(train.event.mean())
        base = np.full(len(test), base_p)
        y = test.event.to_numpy(int)
        ms = metrics(y, state_p, base)
        mt = metrics(y, ttm_p, base)
        mc = metrics(y, council_p, base)
        mstu = metrics(y, student_p, base)

        rows.append({
            "year": int(test_year), "train_n": int(len(train)), "test_n": int(len(test)),
            "base_probability": base_p,
            "state_w_linear": float(state_weights[0]), "state_w_nonlinear": float(state_weights[1]), "state_w_twin": float(state_weights[2]),
            "council_state_weight": float(council_w),
            "state_auc": ms["auc"], "state_brier": ms["brier"], "state_log_loss": ms["log_loss"], "state_ece10": ms["ece10"],
            "ttm_auc": mt["auc"], "ttm_brier": mt["brier"], "ttm_log_loss": mt["log_loss"], "ttm_ece10": mt["ece10"],
            "council_auc": mc["auc"], "council_brier": mc["brier"], "council_log_loss": mc["log_loss"], "council_ece10": mc["ece10"],
            "student_auc": mstu["auc"], "student_brier": mstu["brier"], "student_log_loss": mstu["log_loss"], "student_ece10": mstu["ece10"],
            "state_minus_council_brier": ms["brier"] - mc["brier"],
            "base_minus_student_brier": mstu["base_brier"] - mstu["brier"],
        })

        z = test[["symbol", "campaign_id", "time", "year", "direction", "stage", "event"]].copy()
        z["base_probability"] = base_p
        z["state_probability"] = state_p
        z["ttm_probability"] = ttm_p
        z["student_probability"] = student_p
        z["council_probability"] = council_p
        z["council_state_weight"] = council_w
        z["model_disagreement"] = np.abs(state_p - ttm_p)
        pred_tables.append(z)

    return pd.DataFrame(rows), pd.concat(pred_tables, ignore_index=True) if pred_tables else pd.DataFrame()


def paired_bootstrap_ci(y: np.ndarray, state_p: np.ndarray, council_p: np.ndarray) -> dict[str, float]:
    y = np.asarray(y, int)
    delta = (state_p - y) ** 2 - (council_p - y) ** 2
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(delta)
    vals = np.empty(BOOTSTRAP_REPS, float)
    for i in range(BOOTSTRAP_REPS):
        idx = rng.integers(0, n, n)
        vals[i] = float(np.mean(delta[idx]))
    return {"point": float(np.mean(delta)), "low95": float(np.quantile(vals, 0.025)), "high95": float(np.quantile(vals, 0.975)), "reps": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED}


def model_metrics_by_pair(pred: pd.DataFrame, column: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sym in SYMBOLS:
        q = pred[pred.symbol == sym]
        out[sym] = metrics(q.event.to_numpy(int), q[column].to_numpy(float), q.base_probability.to_numpy(float)) if len(q) else {"n": 0}
    return out


def disagreement_diagnostics(pred: pd.DataFrame) -> dict[str, Any]:
    state = pred.state_probability.to_numpy(float)
    ttm = pred.ttm_probability.to_numpy(float)
    y = pred.event.to_numpy(int)
    d = np.abs(state - ttm)
    out: dict[str, Any] = {
        "pearson_probability_correlation": float(np.corrcoef(state, ttm)[0, 1]),
        "spearman_probability_correlation": float(pd.Series(state).corr(pd.Series(ttm), method="spearman")),
        "mean_absolute_disagreement": float(np.mean(d)),
        "median_absolute_disagreement": float(np.median(d)),
        "strong_disagreement_threshold": DISAGREEMENT_THRESHOLD,
        "strong_disagreement_n": int(np.sum(d >= DISAGREEMENT_THRESHOLD)),
        "strong_disagreement_event_rate": float(np.mean(y[d >= DISAGREEMENT_THRESHOLD])) if np.any(d >= DISAGREEMENT_THRESHOLD) else None,
    }
    q = pred.copy()
    q["disagreement_quartile"] = pd.qcut(q.model_disagreement, 4, labels=False, duplicates="drop")
    quartiles = []
    for k, g in q.groupby("disagreement_quartile", dropna=True):
        quartiles.append({
            "quartile": int(k) + 1, "n": int(len(g)), "mean_disagreement": float(g.model_disagreement.mean()),
            "event_rate": float(g.event.mean()),
            "state_brier": float(brier_score_loss(g.event, g.state_probability)),
            "ttm_brier": float(brier_score_loss(g.event, g.ttm_probability)),
            "council_brier": float(brier_score_loss(g.event, g.council_probability)),
        })
    out["quartiles"] = quartiles
    return out


def export_student_config(train: pd.DataFrame) -> dict[str, Any]:
    pp = preprocessor()
    x = pp.fit_transform(train[CAT + NUM])
    model = LogisticRegression(C=0.5, max_iter=2500, random_state=42)
    model.fit(x, train.event.to_numpy(int))

    cat_pipe = pp.named_transformers_["cat"]
    num_pipe = pp.named_transformers_["num"]
    cat_imputer = cat_pipe.named_steps["impute"]
    onehot = cat_pipe.named_steps["onehot"]
    num_imputer = num_pipe.named_steps["impute"]
    scaler = num_pipe.named_steps["scale"]

    return {
        "version": "state-twin-student-v18-through-2025",
        "training_cutoff": "2025-12-31T23:59:59Z",
        "target": "age-0 Stage 3/4 -> same-direction Stage 5 within 16 M15 bars",
        "eligible_landmark_age_bars": [0],
        "categorical_features": list(CAT),
        "numeric_features": list(NUM),
        "categorical_fill": {name: (None if pd.isna(v) else str(v)) for name, v in zip(CAT, cat_imputer.statistics_)},
        "categories": {name: [str(v) for v in vals.tolist()] for name, vals in zip(CAT, onehot.categories_)},
        "numeric_imputer_median": {name: float(v) for name, v in zip(NUM, num_imputer.statistics_)},
        "numeric_scaler_mean": {name: float(v) for name, v in zip(NUM, scaler.mean_)},
        "numeric_scaler_scale": {name: float(v) for name, v in zip(NUM, scaler.scale_)},
        "logistic_intercept": float(model.intercept_[0]),
        "logistic_coef": [float(v) for v in model.coef_[0]],
        "transformed_feature_names": [str(v) for v in pp.get_feature_names_out().tolist()],
        "training_n": int(len(train)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=128)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    data = aligned_dataset(args.data_dir, pd.Timestamp(args.start, tz="UTC"), args.batch_size)
    data.to_csv(args.out / "v18_model_council_aligned.csv", index=False)
    yearly, pred = yearly_predictions(data)
    if pred.empty:
        raise RuntimeError("No chronological v1.8 predictions were generated")
    yearly.to_csv(args.out / "v18_model_council_yearly.csv", index=False)
    pred.to_csv(args.out / "v18_model_council_predictions.csv", index=False)

    completed = pred[pred.year.isin(COMPLETED_YEARS)].copy()
    if completed.empty:
        raise RuntimeError("No completed-year predictions")
    y = completed.event.to_numpy(int)
    base = completed.base_probability.to_numpy(float)
    state_p = completed.state_probability.to_numpy(float)
    ttm_p = completed.ttm_probability.to_numpy(float)
    council_p = completed.council_probability.to_numpy(float)
    student_p = completed.student_probability.to_numpy(float)

    state_m = metrics(y, state_p, base)
    ttm_m = metrics(y, ttm_p, base)
    council_m = metrics(y, council_p, base)
    student_m = metrics(y, student_p, base)
    bootstrap = paired_bootstrap_ci(y, state_p, council_p)
    state_pairs = model_metrics_by_pair(completed, "state_probability")
    ttm_pairs = model_metrics_by_pair(completed, "ttm_probability")
    council_pairs = model_metrics_by_pair(completed, "council_probability")
    student_pairs = model_metrics_by_pair(completed, "student_probability")

    years_done = yearly[yearly.year.isin(COMPLETED_YEARS)].copy()
    council_positive_years = int((years_done.state_minus_council_brier >= 0).sum())
    student_positive_base_years = int((years_done.base_minus_student_brier > 0).sum())

    council_pass = bool(
        len(completed) >= 5000
        and council_m["brier"] < state_m["brier"]
        and council_m["brier"] < ttm_m["brier"]
        and council_m["log_loss"] <= state_m["log_loss"] + 1e-12
        and (council_m["auc"] or 0) >= (state_m["auc"] or 0) - 0.005
        and council_positive_years >= 3
        and all(state_pairs[s]["brier"] - council_pairs[s]["brier"] >= -1e-12 for s in SYMBOLS)
        and bootstrap["low95"] > 0
    )
    student_pass = bool(
        len(completed) >= 5000
        and student_m["brier"] <= state_m["brier"] + 0.0025
        and (student_m["auc"] or 0) >= (state_m["auc"] or 0) - 0.015
        and student_positive_base_years >= 3
        and all(student_pairs[s]["brier_improvement"] >= -1e-12 for s in SYMBOLS)
        and student_m["ece10"] <= 0.06
    )

    diag = disagreement_diagnostics(completed)
    teacher_student_corr = float(np.corrcoef(state_p, student_p)[0, 1])
    live_train = data[data.year <= 2025].copy()
    student_cfg = export_student_config(live_train)
    student_cfg["historical_gate"] = "PASS" if student_pass else "FAIL"
    student_cfg["historical_metrics_2022_2025"] = student_m
    student_cfg["teacher_metrics_2022_2025"] = state_m
    (args.out / "V18_STATE_TWIN_STUDENT.json").write_text(json.dumps(student_cfg, indent=2), encoding="utf-8")

    report = {
        "study": "V2 v1.8 Model Council",
        "protocol": "reports/v18/V18_MODEL_COUNCIL_PROTOCOL.md",
        "target": "earliest independent Stage-3/4 -> same-direction Stage 5 within 16 M15 bars",
        "eligible_landmark_age_bars": [0],
        "intersected_campaigns_total": int(data.campaign_id.nunique()),
        "completed_2022_2025_n": int(len(completed)),
        "state_twin_teacher": state_m,
        "granite_ttm_r2": ttm_m,
        "model_council": council_m,
        "state_twin_student": student_m,
        "paired_bootstrap_state_minus_council_brier": bootstrap,
        "council_positive_or_equal_brier_years": council_positive_years,
        "student_positive_base_brier_years": student_positive_base_years,
        "teacher_student_probability_correlation": teacher_student_corr,
        "pair_results": {
            "state_twin_teacher": state_pairs, "granite_ttm_r2": ttm_pairs,
            "model_council": council_pairs, "state_twin_student": student_pairs,
        },
        "complementarity": diag,
        "yearly": yearly.to_dict(orient="records"),
        "decision_council": "ACCEPT_HISTORICAL_COUNCIL" if council_pass else "REJECT_COUNCIL_INCREMENTAL",
        "decision_student": "PROMOTE_STATE_TWIN_STUDENT_TO_SHADOW" if student_pass else "REJECT_STATE_TWIN_STUDENT",
        "product_rule": "No visible probability and no Focus or paper-trade influence. A pass only permits eligible age-0 hidden prospective shadow scoring.",
    }
    (args.out / "v18_model_council_summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
