from __future__ import annotations

"""Attach causal source-price anchors to the targeted Dukascopy tick manifest.

Cross-broker spot-FX/CFD quotes can differ by a persistent local basis. Replaying a
source-broker entry/stop/target as absolute Dukascopy prices can therefore create a
false execution mismatch even when both feeds describe the same path.

For each selected setup this script stores the close of the last COMPLETED source
M15 bar before entry. The tick audit can then compare that known source close with
the contemporaneous Dukascopy midpoint and translate all three price levels by one
constant pre-entry offset. No future source or tick price is used to compute it.
"""

import argparse
from pathlib import Path

import pandas as pd

import public_data_v2_proxy as proxy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    m = pd.read_csv(args.manifest)
    m["entry_time"] = pd.to_datetime(m.entry_time, utc=True, errors="coerce")
    rows = []
    cache: dict[str, pd.DataFrame] = {}
    for rec in m.to_dict("records"):
        symbol = str(rec["symbol"])
        market = cache.get(symbol)
        if market is None:
            market = proxy.load_market(args.data_dir / f"{symbol}-15m.feather", symbol)
            market["completed_time"] = pd.to_datetime(market.date, utc=True) + pd.Timedelta(minutes=15)
            cache[symbol] = market
        ts = pd.Timestamp(rec["entry_time"])
        known = market[market.completed_time <= ts]
        if known.empty:
            rec["source_anchor_time"] = ""
            rec["source_anchor_close"] = ""
        else:
            r = known.iloc[-1]
            rec["source_anchor_time"] = pd.Timestamp(r.completed_time).isoformat()
            rec["source_anchor_close"] = float(r.close)
            # Give the tick downloader enough room to include the anchor even for
            # entries shortly after midnight.
            from_day = min(pd.Timestamp(rec["from"], tz="UTC"), pd.Timestamp(r.completed_time).floor("D") - pd.Timedelta(days=1))
            rec["from"] = from_day.date().isoformat()
        rows.append(rec)

    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False)
    print(f"basis anchors attached: {out.source_anchor_close.notna().sum()}/{len(out)}")


if __name__ == "__main__":
    main()
