"""Export broker M1/M15 bars from a local MetaTrader 5 terminal.

Run this on the Windows machine that has MT5 installed and logged in. The output
becomes immutable research input for V2 reproduction and tick/M1 validation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def main() -> None:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("Install MetaTrader5 on the Windows/MT5 research machine") from exc

    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", choices=["M1", "M15"], default="M15")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    tf = mt5.TIMEFRAME_M1 if args.timeframe == "M1" else mt5.TIMEFRAME_M15
    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        rates = mt5.copy_rates_range(args.symbol, tf, start, end)
        if rates is None:
            raise SystemExit(f"copy_rates_range failed: {mt5.last_error()}")
        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(out, index=False)
        print(f"wrote {len(frame):,} rows to {out}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
