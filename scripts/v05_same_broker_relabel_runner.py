from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v05_same_broker_relabel import SameBrokerStore, Trade, load_ledger, quality, relabel_m1, relabel_ticks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--export-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reward-r", type=float, default=2.5)
    ap.add_argument("--max-hold-hours", type=float, default=12.0)
    ap.add_argument("--tick-only", action="store_true")
    args = ap.parse_args()

    trades = load_ledger(args.ledger, args.reward_r)
    store = SameBrokerStore(args.export_root)
    rows = []
    for rec in trades.to_dict("records"):
        if not store.has_symbol(rec["symbol"]):
            continue
        t = Trade(
            setup_id=rec["setup_id"], symbol=rec["symbol"], direction=rec["direction"],
            entry_time=rec["entry_time"], entry=float(rec["entry"]), stop=float(rec["stop"]),
            target=float(rec["target"]), source_outcome=rec["source_outcome"],
            source_net_r=rec.get("source_net_r"),
        )
        end = t.entry_time + pd.Timedelta(hours=args.max_hold_hours)
        ticks = store.ticks_for_window(t.symbol, t.entry_time - pd.Timedelta(minutes=5), end)
        result = relabel_ticks(t, ticks, args.max_hold_hours)
        if result.get("execution_outcome") == "no_data" and not args.tick_only:
            result = relabel_m1(t, store.m1(t.symbol), store.point.get(t.symbol, np.nan), args.max_hold_hours)
        result["label_quality"] = quality(result)
        rows.append({**rec, **result})

    out = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    clear = out[out.execution_outcome.isin(["win", "loss"])] if len(out) else out
    direct = clear[clear.label_source == "tick_direct"] if len(clear) else clear
    summary = {
        "trades_loaded": int(len(trades)),
        "trades_replayed": int(len(out)),
        "direct_tick_clear": int(len(direct)),
        "m1_fallback_clear": int((clear.label_source == "m1_spread_approx").sum()) if len(clear) else 0,
        "ambiguous": int(out.execution_outcome.astype(str).str.startswith("ambiguous").sum()) if len(out) else 0,
        "no_fill": int((out.execution_outcome == "no_fill").sum()) if len(out) else 0,
        "no_data": int((out.execution_outcome == "no_data").sum()) if len(out) else 0,
        "direct_tick_agreement": float((direct.execution_outcome == direct.source_outcome).mean()) if len(direct) else np.nan,
        "direct_tick_execution_expectancy_r": float(pd.to_numeric(direct.execution_r, errors="coerce").mean()) if len(direct) else np.nan,
        "source_expectancy_same_rows_r": float(pd.to_numeric(direct.source_net_r, errors="coerce").mean()) if len(direct) else np.nan,
        "trusted_tick_count": int((out.label_quality == "trusted_tick").sum()) if len(out) else 0,
    }
    args.out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
