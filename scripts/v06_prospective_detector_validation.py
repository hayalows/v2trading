from __future__ import annotations

"""Prospective validation for the live V2 formation detector.

This does NOT test profitability. It answers a narrower question:
Would the live detector have identified a developing V2-like sequence before its
research entry zone was reached, if we replayed history one completed M15 bar at a
time with no access to future bars?

The state rules mirror the Supabase market-lab detector:
0 no setup, 1 liquidity nearby, 2 used POI, 3 sweep confirmed,
4 waiting for BOS, 5 BOS confirmed, 6 fresh POI, 7 approaching POI,
8 research entry zone reached.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from public_data_v2_proxy import load_market


STAGE_NAME = {
    0: "NO_SETUP",
    1: "LIQUIDITY_NEARBY",
    2: "POI_USED",
    3: "SWEEP_CONFIRMED",
    4: "WAITING_FOR_BOS",
    5: "BOS_CONFIRMED",
    6: "FRESH_POI_IDENTIFIED",
    7: "APPROACHING_POI",
    8: "ENTRY_ZONE_REACHED",
}


def true_ranges(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs(),
    ], axis=1).max(axis=1)


def swings(df: pd.DataFrame) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs, lows = [], []
    for i in range(2, len(df) - 2):
        r = df.iloc[i]
        if r.high > df.iloc[i-1].high and r.high >= df.iloc[i-2].high and r.high > df.iloc[i+1].high and r.high >= df.iloc[i+2].high:
            highs.append((i, float(r.high)))
        if r.low < df.iloc[i-1].low and r.low <= df.iloc[i-2].low and r.low < df.iloc[i+1].low and r.low <= df.iloc[i+2].low:
            lows.append((i, float(r.low)))
    return highs, lows


def formation(prefix: pd.DataFrame) -> dict:
    """Calculate state from completed bars in prefix only."""
    if len(prefix) < 45:
        return {"stage": 0, "direction": None, "code": STAGE_NAME[0]}

    df = prefix.reset_index(drop=True)
    atr = true_ranges(df).rolling(14, min_periods=1).mean()
    n = len(df)
    last = df.iloc[-1]
    a = max(float(atr.iloc[-1]), abs(float(last.close)) * 1e-5)
    reference = float(last.close)  # structure price stays on the same candle feed

    sweep = None
    for i in range(max(22, n - 12), n):
        prior = df.iloc[i-20:i]
        ph = float(prior.high.max())
        pl = float(prior.low.min())
        ai = max(float(atr.iloc[i]), a)
        bear = float(df.iloc[i].high) > ph + 0.03 * ai and float(df.iloc[i].close) < ph
        bull = float(df.iloc[i].low) < pl - 0.03 * ai and float(df.iloc[i].close) > pl
        if bear or bull:
            sweep = {"i": i, "direction": "short" if bear else "long", "ts": df.iloc[i].date}

    h, l = swings(df.iloc[-60:].reset_index(drop=True))
    if sweep is None:
        recent = df.iloc[-20:]
        hi = h[-1][1] if h else float(recent.high.max())
        lo = l[-1][1] if l else float(recent.low.min())
        dh, dl = abs(reference-hi)/a, abs(reference-lo)/a
        if min(dh, dl) <= 0.35:
            return {"stage": 1, "direction": "long" if dl < dh else "short", "code": STAGE_NAME[1]}
        return {"stage": 0, "direction": None, "code": STAGE_NAME[0]}

    pre = df.iloc[max(0, sweep["i"]-8):sweep["i"]]
    if pre.empty:
        return {"stage": 3, "direction": sweep["direction"], "code": STAGE_NAME[3]}
    bos_high, bos_low = float(pre.high.max()), float(pre.low.min())
    bos = -1
    for i in range(sweep["i"]+1, n):
        if sweep["direction"] == "long" and float(df.iloc[i].close) > bos_high:
            bos = i; break
        if sweep["direction"] == "short" and float(df.iloc[i].close) < bos_low:
            bos = i; break
    if bos < 0:
        age = n - 1 - sweep["i"]
        st = 4 if age >= 1 else 3
        return {"stage": st, "direction": sweep["direction"], "code": STAGE_NAME[st]}

    poi = -1
    for i in range(bos, sweep["i"]-1, -1):
        r = df.iloc[i]
        opp = float(r.close) < float(r.open) if sweep["direction"] == "long" else float(r.close) > float(r.open)
        if opp:
            poi = i; break
    if poi < 0:
        return {"stage": 5, "direction": sweep["direction"], "code": STAGE_NAME[5]}

    p_high, p_low = float(df.iloc[poi].high), float(df.iloc[poi].low)
    mid = (p_high + p_low) / 2
    dist = abs(reference-mid) / a
    inside = p_low <= reference <= p_high
    touched = False
    for i in range(bos+1, n-1):
        r = df.iloc[i]
        if float(r.low) <= p_high and float(r.high) >= p_low:
            touched = True; break
    if touched and not inside:
        return {"stage": 2, "direction": sweep["direction"], "code": STAGE_NAME[2]}
    if inside:
        return {"stage": 8, "direction": sweep["direction"], "code": STAGE_NAME[8]}
    if dist <= 0.5:
        return {"stage": 7, "direction": sweep["direction"], "code": STAGE_NAME[7]}
    return {"stage": 6, "direction": sweep["direction"], "code": STAGE_NAME[6]}


def replay(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    rows = []
    # 80 bars gives trend/liquidity warmup while preserving strict prefix replay.
    for i in range(80, len(df)):
        st = formation(df.iloc[:i+1])
        rows.append({
            "symbol": symbol,
            "bar_i": i,
            "time": pd.Timestamp(df.iloc[i].date),
            "close": float(df.iloc[i].close),
            **st,
        })
    return pd.DataFrame(rows)


def episodes(states: pd.DataFrame, horizon_bars: int = 32) -> pd.DataFrame:
    """Create non-overlapping developing-setup episodes beginning at stage >= 3.

    Success means the same-direction sequence reaches stage 8 within horizon_bars.
    This is a formation-conversion test, not a P/L label.
    """
    out = []
    i = 0
    s = states.reset_index(drop=True)
    while i < len(s):
        r = s.iloc[i]
        if int(r.stage) < 3 or int(r.stage) == 8 or r.direction not in {"long", "short"}:
            i += 1; continue
        direction = r.direction
        start_i = i
        end_i = min(len(s)-1, i+horizon_bars)
        hit = None
        max_stage = int(r.stage)
        for j in range(i+1, end_i+1):
            rr = s.iloc[j]
            if rr.direction == direction:
                max_stage = max(max_stage, int(rr.stage))
                if int(rr.stage) == 8:
                    hit = j; break
        out.append({
            "symbol": r.symbol,
            "start_time": r.time,
            "start_stage": int(r.stage),
            "direction": direction,
            "converted_to_stage8": hit is not None,
            "entry_time": s.iloc[hit].time if hit is not None else pd.NaT,
            "lead_bars": (hit-start_i) if hit is not None else np.nan,
            "lead_minutes": (hit-start_i)*15 if hit is not None else np.nan,
            "max_stage": max_stage,
        })
        # Don't count the same sequence on every bar. On success jump to the entry;
        # on failure jump past the observation window.
        i = (hit + 1) if hit is not None else (end_i + 1)
    return pd.DataFrame(out)


def entry_recall(states: pd.DataFrame, lookback_bars: int = 32) -> dict:
    s = states.reset_index(drop=True)
    entry_idx = [i for i, x in enumerate(s.stage.astype(int)) if x == 8]
    # Collapse consecutive stage-8 bars to unique entry-zone episodes.
    unique = []
    for i in entry_idx:
        if not unique or i - unique[-1] > 1:
            unique.append(i)
    caught, leads = 0, []
    for i in unique:
        direction = s.iloc[i].direction
        prior = s.iloc[max(0, i-lookback_bars):i]
        matches = prior[(prior.direction == direction) & (prior.stage.astype(int) >= 3) & (prior.stage.astype(int) < 8)]
        if not matches.empty:
            caught += 1
            first_idx = int(matches.index[0])
            leads.append((i-first_idx)*15)
    return {
        "unique_stage8_entries": len(unique),
        "entries_with_prior_stage3plus": caught,
        "entry_recall": caught/len(unique) if unique else None,
        "median_warning_minutes": float(np.median(leads)) if leads else None,
    }


def summarize(states: pd.DataFrame, eps: pd.DataFrame) -> dict:
    by_stage = {}
    for threshold in [3, 4, 5, 6, 7]:
        e = eps[eps.start_stage >= threshold]
        by_stage[str(threshold)] = {
            "episodes": int(len(e)),
            "converted": int(e.converted_to_stage8.sum()) if len(e) else 0,
            "conversion_rate": float(e.converted_to_stage8.mean()) if len(e) else None,
            "median_lead_minutes": float(e.loc[e.converted_to_stage8, "lead_minutes"].median()) if e.converted_to_stage8.any() else None,
        }
    return {
        "bars_replayed": int(len(states)),
        "from": states.time.min().isoformat() if len(states) else None,
        "to": states.time.max().isoformat() if len(states) else None,
        "stage_counts": {str(int(k)): int(v) for k, v in states.stage.value_counts().sort_index().items()},
        "candidate_thresholds": by_stage,
        **entry_recall(states),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("research-output/v06"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    all_states, all_eps, summary = [], [], {}
    for symbol in args.symbols:
        df = load_market(args.data_dir / f"{symbol}-15m.feather", symbol)
        df = df[df.date >= pd.Timestamp(args.start, tz="UTC")].reset_index(drop=True)
        st = replay(df, symbol)
        ep = episodes(st)
        summary[symbol] = summarize(st, ep)
        all_states.append(st); all_eps.append(ep)

    states = pd.concat(all_states, ignore_index=True)
    eps = pd.concat(all_eps, ignore_index=True)
    states.to_csv(args.out / "prospective_states.csv", index=False)
    eps.to_csv(args.out / "formation_episodes.csv", index=False)

    pooled = summarize(states.sort_values(["symbol", "time"]), eps)
    pooled["note"] = "Stage conversion validates prospective setup detection only. It is not a profitability or execution test."
    result = {"version": "v0.6 prospective detector validation", "symbols": summary, "pooled": pooled}
    (args.out / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
