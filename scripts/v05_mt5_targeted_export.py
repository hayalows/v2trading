from __future__ import annotations

"""Targeted v0.5 MT5 exporter.

Exports full M1/M5/M15 bars for the requested research period, but downloads bid/ask
ticks only for UTC dates needed to replay trades in the recovered ledger. The day
before and day after each entry are included so midnight boundaries and the default
12-hour holding horizon cannot silently remove execution data.
"""

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v05_mt5_export import (
    FileRecord,
    export_bars,
    parse_aliases,
    parse_utc_day,
    resolve_symbol,
    safe_name,
    symbol_metadata,
    tick_frame,
    validate_bar_relationship,
    write_parquet,
)
from v05_same_broker_relabel import load_ledger

UTC = timezone.utc


def required_days(ledger: pd.DataFrame, symbol: str, pad_before: int = 1, pad_after: int = 1) -> list[pd.Timestamp]:
    g = ledger[ledger.symbol == symbol.upper()]
    days: set[pd.Timestamp] = set()
    for ts in pd.to_datetime(g.entry_time, utc=True):
        base = ts.floor("D")
        for offset in range(-pad_before, pad_after + 1):
            days.add(base + pd.Timedelta(days=offset))
    return sorted(days)


def export_tick_days(mt5, research_symbol: str, broker_symbol: str, days: list[pd.Timestamp], root: Path) -> tuple[list[FileRecord], list[dict]]:
    records: list[FileRecord] = []
    diagnostics: list[dict] = []
    for day in days:
        start = day.to_pydatetime()
        end = (day + pd.Timedelta(days=1)).to_pydatetime()
        ticks = mt5.copy_ticks_range(broker_symbol, start, end, mt5.COPY_TICKS_ALL)
        ds = day.date().isoformat()
        if ticks is None:
            diagnostics.append({"date": ds, "status": "error", "error": str(mt5.last_error())})
            continue
        frame = tick_frame(ticks)
        if not frame.empty:
            frame = frame[(frame.time >= day) & (frame.time < day + pd.Timedelta(days=1))].copy()
        if frame.empty:
            diagnostics.append({"date": ds, "status": "empty", "rows": 0})
            continue
        valid_quotes = (frame.bid > 0) & (frame.ask > 0) & (frame.ask >= frame.bid)
        path = root / safe_name(research_symbol) / "ticks" / f"date={ds}" / "ticks.parquet"
        records.append(write_parquet(frame, path, kind="ticks", research_symbol=research_symbol, date=ds, root=root))
        diagnostics.append({
            "date": ds,
            "status": "ok",
            "rows": int(len(frame)),
            "usable_bid_ask": int(valid_quotes.sum()),
            "invalid_ask_below_bid": int(((frame.ask < frame.bid) & frame.ask.notna() & frame.bid.notna()).sum()),
            "median_spread": float((frame.loc[valid_quotes, "ask"] - frame.loc[valid_quotes, "bid"]).median()) if valid_quotes.any() else None,
        })
    return records, diagnostics


def main() -> None:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("Install MetaTrader5 on the Windows/MT5 machine: pip install -r requirements-mt5.txt") from exc

    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD", "XAUUSD", "US30"])
    ap.add_argument("--alias", action="append", default=[])
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2026-08-01")
    ap.add_argument("--out", type=Path, default=Path("same-broker-export"))
    ap.add_argument("--pad-before-days", type=int, default=1)
    ap.add_argument("--pad-after-days", type=int, default=1)
    args = ap.parse_args()

    ledger = load_ledger(args.ledger)
    start, end = parse_utc_day(args.start), parse_utc_day(args.end)
    aliases = parse_aliases(args.alias)
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        terminal = mt5.terminal_info()
        version = mt5.version()
        manifest: dict[str, object] = {
            "format": "v2trading-same-broker-v1",
            "created_utc": datetime.now(UTC).isoformat(),
            "requested_start_utc": start.isoformat(),
            "requested_end_utc": end.isoformat(),
            "tick_export_mode": "recovered_trade_window_days",
            "tick_day_padding": {"before": args.pad_before_days, "after": args.pad_after_days},
            "ledger_trades": int(len(ledger)),
            "terminal": {
                "company": getattr(terminal, "company", None),
                "name": getattr(terminal, "name", None),
                "build": version[1] if version else None,
                "version": list(version) if version else None,
            },
            "privacy_note": "Account login/name are intentionally not exported.",
            "symbols": {},
            "files": [],
        }
        all_files: list[FileRecord] = []
        for research_symbol in [s.upper() for s in args.symbols]:
            if not (ledger.symbol == research_symbol).any():
                print(f"[{research_symbol}] no ledger trades; skipping")
                continue
            broker_symbol = resolve_symbol(mt5, research_symbol, aliases)
            info = mt5.symbol_info(broker_symbol)
            print(f"[{research_symbol}] broker symbol: {broker_symbol}")
            all_files.extend(export_bars(mt5, research_symbol, broker_symbol, start, end, root))
            days = required_days(ledger, research_symbol, args.pad_before_days, args.pad_after_days)
            tick_files, tick_diag = export_tick_days(mt5, research_symbol, broker_symbol, days, root)
            all_files.extend(tick_files)
            manifest["symbols"][research_symbol] = {
                "broker_symbol": broker_symbol,
                "ledger_trades": int((ledger.symbol == research_symbol).sum()),
                "requested_tick_days": int(len(days)),
                "metadata": symbol_metadata(info),
                "bar_integrity": validate_bar_relationship(root, research_symbol),
                "tick_days_ok": int(sum(d.get("status") == "ok" for d in tick_diag)),
                "tick_days_empty": int(sum(d.get("status") == "empty" for d in tick_diag)),
                "tick_days_error": int(sum(d.get("status") == "error" for d in tick_diag)),
                "tick_diagnostics": tick_diag,
            }
        manifest["files"] = [asdict(r) for r in all_files]
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        print(f"\nTargeted same-broker export complete: {root}")
        print(f"Ledger trades: {len(ledger):,}")
        print(f"Exported files: {len(all_files):,}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
