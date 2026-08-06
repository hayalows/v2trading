from __future__ import annotations

import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2trading.backtest import performance, stressed_net_r
from v2trading.features import BASE_FEATURES, HTF_FEATURES, assert_no_leakage, prepare_ledger
from v2trading.model import build_pipeline

TEST_YEARS = [2023, 2024, 2025, 2026]


def run(ledger_path: Path, out_dir: Path) -> None:
    raw = pd.read_csv(ledger_path)
    df = prepare_ledger(raw)
    out_dir.mkdir(parents=True, exist_ok=True)
    feature_sets = {"base": BASE_FEATURES, "base_htf": BASE_FEATURES + HTF_FEATURES}
    for features in feature_sets.values():
        assert_no_leakage(features)

    yearly, predictions = [], []
    for feature_set, features in feature_sets.items():
        for model_name in ["logit", "lgbm"]:
            for year in TEST_YEARS:
                train = df[df["year"] < year].copy()
                test = df[df["year"] == year].copy()
                pipe = build_pipeline(train, features, model_name)
                pipe.fit(train[features], train["win"])
                p_test = pipe.predict_proba(test[features])[:, 1]
                p_train = pipe.predict_proba(train[features])[:, 1]
                th50, th70 = float(np.quantile(p_train, .50)), float(np.quantile(p_train, .70))
                row = {"feature_set": feature_set, "model": model_name, "test_year": int(year),
                       "auc": float(roc_auc_score(test["win"], p_test)),
                       "brier": float(brier_score_loss(test["win"], p_test)),
                       **{f"all_{k}": v for k, v in performance(test["net_r"]).items()}}
                for tag, threshold in [("q50", th50), ("q70", th70)]:
                    selected = test[p_test >= threshold]
                    row[f"{tag}_threshold"] = threshold
                    row[f"{tag}_coverage"] = len(selected) / len(test)
                    row.update({f"{tag}_{k}": v for k, v in performance(selected["net_r"]).items()})
                yearly.append(row)

                pred = test[["setup_id", "symbol", "direction", "entry_time", "year", "gross_r", "spread_as_r", "net_r", "win"]].copy()
                pred["feature_set"], pred["model"], pred["p_win"] = feature_set, model_name, p_test
                pred["q50_threshold"], pred["q70_threshold"] = th50, th70
                pred["select_q50"], pred["select_q70"] = p_test >= th50, p_test >= th70
                predictions.append(pred)

    yearly_df = pd.DataFrame(yearly)
    yearly_df.to_csv(out_dir / "walk_forward_yearly.csv", index=False)
    pred_df = pd.concat(predictions, ignore_index=True)
    pred_df.to_csv(out_dir / "walk_forward_predictions.csv", index=False)

    chosen = pred_df[(pred_df["feature_set"] == "base") & (pred_df["model"] == "lgbm")].copy()
    stress_rows = []
    for multiple in [1.0, 1.25, 1.5, 2.0]:
        chosen["stressed_net_r"] = stressed_net_r(chosen, multiple)
        for selection, mask in [("all_v2", np.ones(len(chosen), dtype=bool)),
                                ("meta_q50", chosen["select_q50"].to_numpy()),
                                ("meta_q70", chosen["select_q70"].to_numpy())]:
            stress_rows.append({"spread_cost_multiple": multiple, "selection": selection,
                                **performance(chosen.loc[mask, "stressed_net_r"])})
    pd.DataFrame(stress_rows).to_csv(out_dir / "cost_stress.csv", index=False)

    summary = {
        "recovered_ledger": {"rows": int(len(df)), "columns": int(len(raw.columns)),
                             "baseline_full_expectancy_r": float(df["net_r"].mean()),
                             "baseline_full_win_rate": float(df["win"].mean())},
        "leakage_audit": {"m15_v2_setup_score_equals_net_r": bool(np.allclose(df["m15_v2_setup_score"], df["net_r"], equal_nan=True)),
                          "excluded_from_training": True},
        "chosen_candidate": {"features": "base entry-time features only", "model": "LightGBM classifier",
                             "oos_years": TEST_YEARS, "oos_rows": int(len(chosen)),
                             "pooled_auc": float(roc_auc_score(chosen["win"], chosen["p_win"])),
                             "pooled_brier": float(brier_score_loss(chosen["win"], chosen["p_win"])),
                             "baseline_oos": performance(chosen["net_r"]),
                             "q50_oos": performance(chosen.loc[chosen["select_q50"], "net_r"]),
                             "q70_oos": performance(chosen.loc[chosen["select_q70"], "net_r"])},
        "interpretation": "Research ranking signal only. Not approved for live execution."
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: run_recovered_ledger_experiment.py LEDGER.csv OUT_DIR")
    run(Path(sys.argv[1]), Path(sys.argv[2]))
