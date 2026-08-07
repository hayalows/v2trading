from __future__ import annotations

"""Duplicate-safe v0.3 model combination and acceptance summary.

The proxy's human-readable `setup_id` is not guaranteed globally unique. Joining
model outputs on it alone can create a Cartesian product. This postprocessor pairs
identical keys by deterministic occurrence number, preserving exactly one row for
every price-model OOS observation.

No model is inverted or retuned after seeing OOS results. The fixed blend weights
remain 80/20 for event context and 70/30 for XAU macro context. If a context layer
fails to improve ranking, the acceptance decision records that negative result.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score


def score_summary(df: pd.DataFrame, score: str) -> dict:
    z = df.dropna(subset=[score, "win", "net_r"]).copy()
    if z.empty or z.win.nunique() < 2:
        return {}
    q50, q70 = z[score].quantile([0.50, 0.70]).tolist()
    return {
        "n": int(len(z)),
        "auc": float(roc_auc_score(z.win, z[score])),
        "brier": float(brier_score_loss(z.win, z[score].clip(0, 1))),
        "all_expectancy_r": float(z.net_r.mean()),
        "q50_n": int((z[score] >= q50).sum()),
        "q50_expectancy_r": float(z.loc[z[score] >= q50, "net_r"].mean()),
        "q70_n": int((z[score] >= q70).sum()),
        "q70_expectancy_r": float(z.loc[z[score] >= q70, "net_r"].mean()),
    }


def occurrence_safe_merge(left: pd.DataFrame, right: pd.DataFrame, right_cols: list[str]) -> pd.DataFrame:
    keys = [c for c in ["setup_id", "entry_time", "net_r", "win"] if c in left.columns and c in right.columns]
    if not keys:
        raise ValueError("No stable pairing keys available")
    l = left.copy()
    r = right.copy()
    for d in (l, r):
        if "entry_time" in keys:
            d["entry_time"] = pd.to_datetime(d.entry_time, utc=True, errors="coerce").astype(str)
        d["_occurrence"] = d.groupby(keys, dropna=False).cumcount()
    merged = l.merge(r[keys + ["_occurrence"] + right_cols], on=keys + ["_occurrence"], how="left", validate="one_to_one")
    return merged.drop(columns=["_occurrence"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out

    price = pd.read_csv(out / "v03_price_oos_predictions.csv")
    event = pd.read_csv(out / "v03_event_oos_predictions.csv") if (out / "v03_event_oos_predictions.csv").exists() else pd.DataFrame()
    gold = pd.read_csv(out / "v03_gold_macro_oos_predictions.csv") if (out / "v03_gold_macro_oos_predictions.csv").exists() else pd.DataFrame()

    combined = occurrence_safe_merge(price, event, ["p_event"]) if not event.empty else price.assign(p_event=np.nan)
    combined["p_combined"] = np.where(combined.p_event.notna(), 0.80 * combined.p_price + 0.20 * combined.p_event, combined.p_price)
    if len(combined) != len(price):
        raise AssertionError(f"Price/event merge changed row count: {len(price)} -> {len(combined)}")
    combined.to_csv(out / "v03_price_event_combined_oos.csv", index=False)

    gold_price = price[price.symbol == "XAUUSD"].copy()
    gold_blend = occurrence_safe_merge(gold_price, gold, ["p_gold_macro"]) if not gold.empty else gold_price.assign(p_gold_macro=np.nan)
    gold_blend["p_gold_blend"] = np.where(gold_blend.p_gold_macro.notna(), 0.70 * gold_blend.p_price + 0.30 * gold_blend.p_gold_macro, gold_blend.p_price)
    if len(gold_blend) != len(gold_price):
        raise AssertionError(f"Gold merge changed row count: {len(gold_price)} -> {len(gold_blend)}")
    gold_blend.to_csv(out / "v03_gold_blended_oos.csv", index=False)

    base = json.loads((out / "v03_summary.json").read_text(encoding="utf-8"))
    strict = score_summary(price, "p_price")
    event_blend = score_summary(combined, "p_combined")
    gold_price_s = score_summary(gold_price, "p_price")
    gold_blend_s = score_summary(gold_blend, "p_gold_blend")

    base["strict_price"] = strict
    base["price_plus_event"] = event_blend
    base["gold_price_only"] = gold_price_s
    base["gold_price_plus_macro"] = gold_blend_s
    base["acceptance"] = {
        "price_model": "ACCEPT_RESEARCH_BASELINE" if strict.get("auc", 0) > 0.55 else "REJECT",
        "event_model": "ACCEPT_INCREMENTAL" if event_blend.get("auc", 0) > strict.get("auc", 0) + 0.005 else "REJECT_AS_INCREMENTAL_FILTER",
        "gold_macro_model": "ACCEPT_INCREMENTAL" if gold_blend_s.get("auc", 0) > gold_price_s.get("auc", 0) + 0.005 else "REJECT_AS_INCREMENTAL_FILTER",
        "rule": "Context models are not inverted, reweighted, or tuned after OOS results. A rejected layer remains documented as a negative result."
    }
    base["merge_integrity"] = {
        "price_oos_rows": int(len(price)),
        "price_event_rows": int(len(combined)),
        "gold_price_rows": int(len(gold_price)),
        "gold_blend_rows": int(len(gold_blend)),
        "method": "occurrence-safe one-to-one pairing on setup/time/outcome keys"
    }
    (out / "v03_summary.json").write_text(json.dumps(base, indent=2), encoding="utf-8")
    print(json.dumps(base, indent=2))


if __name__ == "__main__":
    main()
