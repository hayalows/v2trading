from __future__ import annotations

"""Pre-registered label-integrity gate for V2 Quant v0.5.

Passing this gate does NOT approve live trading. It only says that same-broker
execution labels are sufficiently coherent to justify rebuilding/retraining a model.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return np.nan, np.nan
    p = k / n
    den = 1 + z*z/n
    mid = (p + z*z/(2*n)) / den
    half = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return float(max(0, mid-half)), float(min(1, mid+half))


def metrics(g: pd.DataFrame) -> dict:
    clear = g[(g.label_source == "tick_direct") & g.execution_outcome.isin(["win", "loss"])].copy()
    trusted = clear[clear.label_quality == "trusted_tick"].copy()
    agree = int((clear.execution_outcome == clear.source_outcome).sum())
    tagree = int((trusted.execution_outcome == trusted.source_outcome).sum())
    lo, hi = wilson(agree, len(clear))
    tlo, thi = wilson(tagree, len(trusted))
    return {
        "rows": int(len(g)),
        "direct_tick_clear": int(len(clear)),
        "trusted_tick_clear": int(len(trusted)),
        "direct_agreement": float(agree/len(clear)) if len(clear) else np.nan,
        "direct_agreement_95ci": [lo, hi],
        "trusted_agreement": float(tagree/len(trusted)) if len(trusted) else np.nan,
        "trusted_agreement_95ci": [tlo, thi],
        "execution_expectancy_r": float(pd.to_numeric(clear.execution_r, errors="coerce").mean()) if len(clear) else np.nan,
        "source_expectancy_same_trades_r": float(pd.to_numeric(clear.source_net_r, errors="coerce").mean()) if len(clear) else np.nan,
        "median_fill_spread_r": float(pd.to_numeric(clear.fill_spread_r, errors="coerce").median()) if len(clear) else np.nan,
        "p90_fill_spread_r": float(pd.to_numeric(clear.fill_spread_r, errors="coerce").quantile(.90)) if len(clear) else np.nan,
        "median_stop_slippage_r": float(pd.to_numeric(clear.stop_slippage_r, errors="coerce").median()) if len(clear) else np.nan,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relabels", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected-symbols", nargs="+", default=["EURUSD", "GBPUSD", "XAUUSD", "US30"])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.relabels, low_memory=False)
    df["symbol"] = df.symbol.astype(str).str.upper()
    expected = [s.upper() for s in args.expected_symbols]
    overall = metrics(df)

    by_symbol = []
    for symbol in expected:
        by_symbol.append({"symbol": symbol, **metrics(df[df.symbol == symbol])})
    # Preserve any unexpected symbols for diagnosis without allowing them to replace
    # a required market in the gate.
    for symbol in sorted(set(df.symbol) - set(expected)):
        by_symbol.append({"symbol": symbol, **metrics(df[df.symbol == symbol])})
    by_symbol_df = pd.DataFrame(by_symbol)

    unresolved = ~df.execution_outcome.isin(["win", "loss"])
    unresolved_rate = float(unresolved.mean()) if len(df) else 1.0
    expected_rows = by_symbol_df[by_symbol_df.symbol.isin(expected)]
    min_per_symbol = int(expected_rows.direct_tick_clear.min()) if len(expected_rows) else 0
    present = sorted(set(df.symbol) & set(expected))
    missing = sorted(set(expected) - set(df.symbol))

    gate = {
        "all_expected_symbols_present": bool(not missing),
        "minimum_direct_tick_clear_200": bool(overall["direct_tick_clear"] >= 200),
        "minimum_trusted_tick_clear_100": bool(overall["trusted_tick_clear"] >= 100),
        "minimum_30_direct_tick_labels_per_symbol": bool(min_per_symbol >= 30),
        "overall_source_tick_agreement_at_least_0_90": bool(np.isfinite(overall["direct_agreement"]) and overall["direct_agreement"] >= .90),
        "trusted_source_tick_agreement_at_least_0_93": bool(np.isfinite(overall["trusted_agreement"]) and overall["trusted_agreement"] >= .93),
        "unresolved_rate_at_most_0_10": bool(unresolved_rate <= .10),
    }
    gate["pass"] = bool(all(gate.values()))

    summary = {
        "version": "V2 Quant v0.5 Same-Broker Reconstruction",
        "purpose": "Validate label integrity before any executable-label model retraining",
        "expected_symbols": expected,
        "present_expected_symbols": present,
        "missing_expected_symbols": missing,
        "overall": overall,
        "unresolved_rate": unresolved_rate,
        "minimum_direct_tick_labels_in_any_expected_symbol": min_per_symbol,
        "by_symbol": by_symbol,
        "pre_registered_gate": {
            "all_expected_symbols_required": True,
            "direct_tick_clear": 200,
            "trusted_tick_clear": 100,
            "direct_tick_per_symbol": 30,
            "overall_source_tick_agreement": .90,
            "trusted_source_tick_agreement": .93,
            "maximum_unresolved_rate": .10,
        },
        "gate": gate,
        "training_eligible": bool(gate["pass"]),
        "decision": "Proceed to executable-label model rebuild" if gate["pass"] else "Do not retrain; diagnose same-broker label disagreement first",
        "live_trading": "NOT APPROVED — passing this gate would only approve the next research stage",
    }
    (args.out / "v05_label_gate_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    by_symbol_df.to_csv(args.out / "v05_label_gate_by_symbol.csv", index=False)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
