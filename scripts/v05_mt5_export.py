from __future__ import annotations

"""V2 Quant v0.5 same-broker MT5 exporter.

Run this script on the Windows machine that has the ORIGINAL research broker's
MetaTrader 5 terminal installed and logged in. It exports immutable M1/M5/M15 bars,
partitioned bid/ask ticks, symbol execution metadata and a SHA256 manifest.

The exporter deliberately does not backtest or modify V2. Its job is to create an
auditable same-broker dataset from which labels can later be reconstructed.
"""

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

UTC = timezone.utc
TIMEFRAMES = ("M1", "M5", "M15")


@dataclass
class FileRecord:
    relative_path: str
    rows: int
    start_utc: str | None
    end_utc: str | None
    sha256: str
    bytes: int
    kind: str
    symbol: str
    timeframe: str | None = None
    date: str | None = None


def parse_utc_day(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def normalize_symbol(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def parse_aliases(values: Iterable[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise SystemExit(f"Invalid --alias {item!r}; expected RESEARCH=MT5_SYMBOL")
        research, broker = item.split("=", 1)
        out[research.strip().upper()] = broker.strip()
    return out


def resolve_symbol(mt5, requested: str, aliases: dict[str, str]) -> str:
    research = requested.upper()
    if research in aliases:
        broker = aliases[research]
        if mt5.symbol_info(broker) is None:
            raise SystemExit(f"Alias {research}={broker} is not visible in MT5")
        mt5.symbol_select(broker, True)
        return broker

    if mt5.symbol_info(requested) is not None:
        mt5.symbol_select(requested, True)
        return requested

    symbols = list(mt5.symbols_get() or [])
    exact_ci = [s.name for s in symbols if s.name.upper() == research]
    if len(exact_ci) == 1:
        mt5.symbol_select(exact_ci[0], True)
        return exact_ci[0]

    target = normalize_symbol(research)
    candidates = [s.name for s in symbols if normalize_symbol(s.name).startswith(target)]
    if len(candidates) == 1:
        mt5.symbol_select(candidates[0], True)
        return candidates[0]
    if not candidates:
        raise SystemExit(f"Could not resolve MT5 symbol for {requested!r}. Pass --alias {research}=BROKER_SYMBOL")
    raise SystemExit(
        f"Ambiguous MT5 symbol for {requested!r}: {candidates[:12]}. "
        f"Pass --alias {research}=BROKER_SYMBOL explicitly."
    )


def symbol_metadata(info) -> dict:
    names = [
        "name", "path", "description", "currency_base", "currency_profit", "currency_margin",
        "digits", "point", "trade_tick_size", "trade_tick_value", "trade_tick_value_profit",
        "trade_tick_value_loss", "trade_contract_size", "volume_min", "volume_max", "volume_step",
        "trade_stops_level", "trade_freeze_level", "spread", "spread_float", "trade_mode",
        "trade_calc_mode", "filling_mode", "expiration_mode", "order_mode", "swap_mode",
        "swap_long", "swap_short",
    ]
    return {k: getattr(info, k, None) for k in names}


def bar_frame(rates) -> pd.DataFrame:
    f = pd.DataFrame(rates)
    if f.empty:
        return f
    f["time"] = pd.to_datetime(f["time"], unit="s", utc=True)
    numeric = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    for c in numeric:
        if c in f:
            f[c] = pd.to_numeric(f[c], errors="coerce")
    return f.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)


def tick_frame(ticks) -> pd.DataFrame:
    f = pd.DataFrame(ticks)
    if f.empty:
        return f
    if "time_msc" in f:
        f["time"] = pd.to_datetime(f["time_msc"], unit="ms", utc=True)
    else:
        f["time"] = pd.to_datetime(f["time"], unit="s", utc=True)
    for c in ["bid", "ask", "last", "volume", "volume_real", "flags"]:
        if c in f:
            f[c] = pd.to_numeric(f[c], errors="coerce")
    if "bid" in f and "ask" in f:
        f["spread"] = f["ask"] - f["bid"]
        f["mid"] = (f["ask"] + f["bid"]) / 2.0
    return f.sort_values("time").drop_duplicates([c for c in ["time_msc", "bid", "ask", "last"] if c in f], keep="last").reset_index(drop=True)


def write_parquet(frame: pd.DataFrame, path: Path, *, kind: str, research_symbol: str,
                  timeframe: str | None = None, date: str | None = None, root: Path) -> FileRecord:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd")
    start = str(frame.time.min()) if len(frame) and "time" in frame else None
    end = str(frame.time.max()) if len(frame) and "time" in frame else None
    return FileRecord(
        relative_path=path.relative_to(root).as_posix(), rows=int(len(frame)), start_utc=start, end_utc=end,
        sha256=sha256_file(path), bytes=path.stat().st_size, kind=kind, symbol=research_symbol,
        timeframe=timeframe, date=date,
    )


def export_bars(mt5, research_symbol: str, broker_symbol: str, start: datetime, end: datetime,
                root: Path) -> list[FileRecord]:
    tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
    records: list[FileRecord] = []
    for name in TIMEFRAMES:
        rates = mt5.copy_rates_range(broker_symbol, tf_map[name], start, end)
        if rates is None:
            raise RuntimeError(f"copy_rates_range({broker_symbol}, {name}) failed: {mt5.last_error()}")
        frame = bar_frame(rates)
        if frame.empty:
            raise RuntimeError(f"No {name} bars returned for {broker_symbol} {start}..{end}")
        path = root / safe_name(research_symbol) / "bars" / f"{name}.parquet"
        records.append(write_parquet(frame, path, kind="bars", research_symbol=research_symbol,
                                     timeframe=name, root=root))
    return records


def export_ticks(mt5, research_symbol: str, broker_symbol: str, start: datetime, end: datetime,
                 root: Path) -> tuple[list[FileRecord], list[dict]]:
    records: list[FileRecord] = []
    diagnostics: list[dict] = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    final = end
    while day < final:
        nxt = min(day + timedelta(days=1), final)
        ticks = mt5.copy_ticks_range(broker_symbol, day, nxt, mt5.COPY_TICKS_ALL)
        if ticks is None:
            diagnostics.append({"date": day.date().isoformat(), "status": "error", "error": str(mt5.last_error())})
            day = nxt
            continue
        frame = tick_frame(ticks)
        if not frame.empty:
            # copy_ticks_range can be inclusive at the upper boundary; keep this partition half-open.
            frame = frame[(frame.time >= day) & (frame.time < nxt)].copy()
        date_s = day.date().isoformat()
        if frame.empty:
            diagnostics.append({"date": date_s, "status": "empty", "rows": 0})
            day = nxt
            continue
        invalid_cross = int(((frame.ask < frame.bid) & frame.ask.notna() & frame.bid.notna()).sum()) if {"ask", "bid"}.issubset(frame.columns) else -1
        usable_quotes = int((frame.bid.gt(0) & frame.ask.gt(0)).sum()) if {"ask", "bid"}.issubset(frame.columns) else 0
        path = root / safe_name(research_symbol) / "ticks" / f"date={date_s}" / "ticks.parquet"
        records.append(write_parquet(frame, path, kind="ticks", research_symbol=research_symbol,
                                     date=date_s, root=root))
        diagnostics.append({
            "date": date_s, "status": "ok", "rows": int(len(frame)), "usable_bid_ask": usable_quotes,
            "invalid_ask_below_bid": invalid_cross,
            "median_spread": float(frame.loc[(frame.bid > 0) & (frame.ask > 0), "spread"].median()) if usable_quotes else None,
        })
        day = nxt
    return records, diagnostics


def validate_bar_relationship(root: Path, research_symbol: str) -> dict:
    frames = {tf: pd.read_parquet(root / safe_name(research_symbol) / "bars" / f"{tf}.parquet") for tf in TIMEFRAMES}
    result: dict[str, object] = {}
    for tf, f in frames.items():
        f["time"] = pd.to_datetime(f.time, utc=True)
        result[f"{tf}_rows"] = int(len(f))
        result[f"{tf}_duplicate_times"] = int(f.time.duplicated().sum())
        result[f"{tf}_monotonic"] = bool(f.time.is_monotonic_increasing)
        result[f"{tf}_ohlc_invalid"] = int(((f.high < f[["open", "close", "low"]].max(axis=1)) | (f.low > f[["open", "close", "high"]].min(axis=1))).sum())
    # Same-broker cross-timeframe sanity check: resampled M1 close should usually match M5/M15 close.
    m1 = frames["M1"].copy()
    m1["time"] = pd.to_datetime(m1.time, utc=True)
    m1 = m1.set_index("time")
    for tf, rule in [("M5", "5min"), ("M15", "15min")]:
        derived = m1.resample(rule, label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
        actual = frames[tf].copy()
        actual["time"] = pd.to_datetime(actual.time, utc=True)
        z = actual.merge(derived, on="time", suffixes=("_actual", "_m1"))
        if z.empty:
            result[f"{tf}_m1_overlap"] = 0
            result[f"{tf}_m1_close_exact_rate"] = None
        else:
            tol = max(1e-12, float(np.nanmedian(np.abs(z.close_actual))) * 1e-10)
            result[f"{tf}_m1_overlap"] = int(len(z))
            result[f"{tf}_m1_close_exact_rate"] = float((np.abs(z.close_actual - z.close_m1) <= tol).mean())
    return result


def main() -> None:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("Install MetaTrader5 on the Windows/MT5 machine: pip install MetaTrader5 pandas pyarrow") from exc

    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD", "XAUUSD", "US30"])
    ap.add_argument("--alias", action="append", default=[], help="Research symbol to broker symbol, e.g. US30=US30.cash")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2026-08-01")
    ap.add_argument("--out", type=Path, default=Path("same-broker-export"))
    ap.add_argument("--skip-ticks", action="store_true", help="Export bars only; tick labels will remain unavailable")
    args = ap.parse_args()

    start, end = parse_utc_day(args.start), parse_utc_day(args.end)
    if end <= start:
        raise SystemExit("--end must be after --start")
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
        file_records: list[FileRecord] = []
        for research_symbol in [s.upper() for s in args.symbols]:
            broker_symbol = resolve_symbol(mt5, research_symbol, aliases)
            info = mt5.symbol_info(broker_symbol)
            if info is None:
                raise RuntimeError(f"symbol_info failed for {broker_symbol}")
            print(f"[{research_symbol}] broker symbol: {broker_symbol}")
            bars = export_bars(mt5, research_symbol, broker_symbol, start, end, root)
            file_records.extend(bars)
            tick_records: list[FileRecord] = []
            tick_diag: list[dict] = []
            if not args.skip_ticks:
                tick_records, tick_diag = export_ticks(mt5, research_symbol, broker_symbol, start, end, root)
                file_records.extend(tick_records)
            manifest["symbols"][research_symbol] = {
                "broker_symbol": broker_symbol,
                "metadata": symbol_metadata(info),
                "bar_integrity": validate_bar_relationship(root, research_symbol),
                "tick_days_ok": int(sum(d.get("status") == "ok" for d in tick_diag)),
                "tick_days_empty": int(sum(d.get("status") == "empty" for d in tick_diag)),
                "tick_days_error": int(sum(d.get("status") == "error" for d in tick_diag)),
                "tick_diagnostics": tick_diag,
            }
        manifest["files"] = [asdict(r) for r in file_records]
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        print(f"\nExport complete: {root}")
        print(f"Manifest: {manifest_path}")
        print(f"Files: {len(file_records):,}")
        print("Do not edit exported parquet files. Their SHA256 hashes are recorded in manifest.json.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
