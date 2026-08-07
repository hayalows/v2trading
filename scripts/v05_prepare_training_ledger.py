from __future__ import annotations

"""Create an executable-label training ledger only after the v0.5 label gate passes.

The original feature columns are retained. Historical candle ``net_r`` is preserved as
``source_net_r_original`` and replaced by same-broker direct-tick ``execution_r`` so
existing leakage-safe research tooling can be reused in the NEXT stage.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from v05_same_broker_relabel import find_col


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--relabels", type=Path, required=True)
    ap.add_argument("--gate-summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    gate = json.loads(args.gate_summary.read_text(encoding="utf-8"))
    if not gate.get("training_eligible", False):
        raise SystemExit("v0.5 label gate did not pass; executable-label training ledger will not be created")

    raw = pd.read_parquet(args.ledger) if args.ledger.suffix.lower() in {".parquet", ".pq"} else pd.read_csv(args.ledger, low_memory=False)
    rel = pd.read_csv(args.relabels, low_memory=False)
    sid_col = find_col(raw, "setup_id", required=False)
    et_col = find_col(raw, "entry_time", required=True)
    nr_col = find_col(raw, "net_r", required=True)

    work = raw.copy()
    work["_setup_key"] = work[sid_col].astype(str) if sid_col is not None else [f"LEDGER_{i:06d}" for i in range(len(work))]
    work["_entry_key"] = pd.to_datetime(work[et_col], utc=True, errors="coerce")
    work["_occ"] = work.groupby(["_setup_key", "_entry_key"], dropna=False).cumcount()

    rel = rel[(rel.label_source == "tick_direct") & rel.execution_outcome.isin(["win", "loss"])].copy()
    rel["_setup_key"] = rel.setup_id.astype(str)
    rel["_entry_key"] = pd.to_datetime(rel.entry_time, utc=True, errors="coerce")
    rel["_occ"] = rel.groupby(["_setup_key", "_entry_key"], dropna=False).cumcount()
    keep = ["_setup_key", "_entry_key", "_occ", "execution_r", "execution_outcome", "label_quality",
            "fill_spread_r", "spread_median_r", "stop_slippage_r", "fill_time", "exit_time"]
    merged = work.merge(rel[keep], on=["_setup_key", "_entry_key", "_occ"], how="inner", validate="one_to_one")
    if merged.empty:
        raise SystemExit("No direct-tick relabel rows matched the original ledger")

    merged["source_net_r_original"] = pd.to_numeric(merged[nr_col], errors="coerce")
    merged[nr_col] = pd.to_numeric(merged.execution_r, errors="coerce")
    merged["same_broker_execution_win"] = (merged.execution_outcome == "win").astype(int)
    merged["same_broker_fill_spread_as_r"] = pd.to_numeric(merged.fill_spread_r, errors="coerce")
    merged["same_broker_stop_slippage_r"] = pd.to_numeric(merged.stop_slippage_r, errors="coerce")
    merged["same_broker_label_quality"] = merged.label_quality
    merged = merged.drop(columns=["_setup_key", "_entry_key", "_occ"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.suffix.lower() in {".parquet", ".pq"}:
        merged.to_parquet(args.out, index=False, compression="zstd")
    else:
        merged.to_csv(args.out, index=False)

    summary = {
        "rows": int(len(merged)),
        "trusted_tick_rows": int((merged.same_broker_label_quality == "trusted_tick").sum()),
        "execution_win_rate": float(merged.same_broker_execution_win.mean()),
        "execution_expectancy_r": float(pd.to_numeric(merged[nr_col], errors="coerce").mean()),
        "source_expectancy_same_rows_r": float(merged.source_net_r_original.mean()),
        "note": "This file is research-eligible because the v0.5 label-integrity gate passed. It is not a live-trading approval.",
    }
    args.out.with_suffix(args.out.suffix + ".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
