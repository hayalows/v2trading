from __future__ import annotations

"""Public-data reconstruction experiment for the V2 research idea.

This is intentionally called a *proxy* engine. The exact historical V2 source code
is not available, so this module translates the recovered research description into
fully explicit, reproducible rules:

    liquidity sweep -> BOS -> fresh POI -> 50% POI entry -> fixed 2.5R target

All signal features are computed from information available no later than entry.
Outcome resolution uses 15-minute bars and, when necessary, 5-minute bars to reduce
same-bar stop/target ambiguity.
"""

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass(frozen=True)
class ProxyConfig:
    swing_lookback: int = 20
    bos_lookback: int = 8
    atr_period: int = 14
    sweep_min_atr: float = 0.03
    max_bos_bars: int = 6
    max_entry_bars: int = 8
    max_hold_bars: int = 48
    stop_buffer_atr: float = 0.03
    reward_r: float = 2.5
    min_risk_atr: float = 0.08
    max_risk_atr: float = 1.60


SYMBOL_COST = {
    # Conservative research-only spread + slippage approximations in price units.
    # We stress these separately; they are not claimed to match any broker.
    "EURUSD": {"spread": 0.00008, "slippage": 0.00002},
    "GBPUSD": {"spread": 0.00012, "slippage": 0.00003},
    "XAUUSD": {"spread": 0.30, "slippage": 0.08},
    "NAS100": {"spread": 1.80, "slippage": 0.50},
}

RELEVANT_CURRENCIES = {
    "EURUSD": {"EUR", "USD"},
    "GBPUSD": {"GBP", "USD"},
    "XAUUSD": {"USD"},
    "NAS100": {"USD"},
}

FEATURES = [
    "symbol", "direction", "entry_hour", "entry_dow", "is_london", "is_new_york", "is_overlap",
    "atr", "risk_distance", "risk_atr", "sweep_depth_atr", "sweep_wick_ratio",
    "bos_displacement_atr", "zone_width_atr", "sweep_to_bos_bars", "bos_to_entry_bars",
    "volume_z", "trend20_atr", "range_position_20", "cost_as_r",
    "high_event_30m", "high_event_120m", "minutes_to_nearest_high_event",
    "nearby_event_count_120m", "nearest_event_surprise", "nearest_event_currency",
]


def load_market(path: Path, symbol: str) -> pd.DataFrame:
    df = pd.read_feather(path)
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for wanted in ["date", "open", "high", "low", "close", "volume"]:
        if wanted in cols:
            rename[cols[wanted]] = wanted
    df = df.rename(columns=rename)
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}; got {list(df.columns)}")
    if "volume" not in df:
        df["volume"] = 0.0
    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date")
    df = df.drop_duplicates("date", keep="last").reset_index(drop=True)
    df["symbol"] = symbol
    return df


def add_causal_features(df: pd.DataFrame, cfg: ProxyConfig) -> pd.DataFrame:
    out = df.copy()
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.rolling(cfg.atr_period, min_periods=cfg.atr_period).mean()
    out["prev_swing_high"] = out["high"].shift(1).rolling(cfg.swing_lookback).max()
    out["prev_swing_low"] = out["low"].shift(1).rolling(cfg.swing_lookback).min()
    out["bos_up_level"] = out["high"].shift(1).rolling(cfg.bos_lookback).max()
    out["bos_dn_level"] = out["low"].shift(1).rolling(cfg.bos_lookback).min()
    vol_mean = out["volume"].shift(1).rolling(40, min_periods=20).mean()
    vol_std = out["volume"].shift(1).rolling(40, min_periods=20).std().replace(0, np.nan)
    out["volume_z"] = (out["volume"] - vol_mean) / vol_std
    ema20 = out["close"].ewm(span=20, adjust=False).mean()
    out["trend20_atr"] = (ema20 - ema20.shift(8)) / out["atr"].replace(0, np.nan)
    hi20 = out["high"].shift(1).rolling(20).max()
    lo20 = out["low"].shift(1).rolling(20).min()
    out["range_position_20"] = (out["close"] - lo20) / (hi20 - lo20).replace(0, np.nan)
    return out


def session_fields(ts: pd.Timestamp) -> tuple[int, int, int]:
    # UTC approximations. DST is deliberately not hand-tuned in this first proxy.
    h = int(ts.hour)
    london = int(7 <= h < 16)
    ny = int(12 <= h < 21)
    return london, ny, int(london and ny)


def wick_ratio(row: pd.Series, direction: str) -> float:
    body = abs(float(row.close) - float(row.open))
    rng = max(float(row.high) - float(row.low), 1e-12)
    if direction == "long":
        wick = min(float(row.open), float(row.close)) - float(row.low)
    else:
        wick = float(row.high) - max(float(row.open), float(row.close))
    return float(max(wick, 0.0) / max(body, 0.15 * rng, 1e-12))


def find_poi(df: pd.DataFrame, sweep_i: int, bos_i: int, direction: str) -> tuple[int, float, float] | None:
    """Last opposite candle from sweep through BOS; zone is candle low/high to open.

    For long setups, use the last bearish candle and [low, open].
    For short setups, use the last bullish candle and [open, high].
    """
    segment = df.iloc[sweep_i:bos_i + 1]
    if direction == "long":
        opp = segment[segment["close"] < segment["open"]]
        if opp.empty:
            return None
        idx = int(opp.index[-1])
        return idx, float(df.at[idx, "low"]), float(df.at[idx, "open"])
    opp = segment[segment["close"] > segment["open"]]
    if opp.empty:
        return None
    idx = int(opp.index[-1])
    return idx, float(df.at[idx, "open"]), float(df.at[idx, "high"])


def bar_touches(row: pd.Series, price: float) -> bool:
    return float(row.low) <= price <= float(row.high)


def resolve_m15_outcome(
    m15: pd.DataFrame,
    m5: pd.DataFrame | None,
    entry_i: int,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    max_hold_bars: int,
) -> tuple[str, pd.Timestamp, int, bool]:
    """Return result, exit time, held bars, used_5m_resolution."""
    end_i = min(len(m15) - 1, entry_i + max_hold_bars)
    for j in range(entry_i, end_i + 1):
        row = m15.iloc[j]
        if direction == "long":
            hit_stop = float(row.low) <= stop
            hit_tp = float(row.high) >= target
        else:
            hit_stop = float(row.high) >= stop
            hit_tp = float(row.low) <= target
        if not (hit_stop or hit_tp):
            continue
        if hit_stop and hit_tp:
            if m5 is not None:
                start = pd.Timestamp(row.date)
                finish = start + pd.Timedelta(minutes=15)
                sub = m5[(m5["date"] >= start) & (m5["date"] < finish)]
                for _, s in sub.iterrows():
                    if direction == "long":
                        ss = float(s.low) <= stop
                        tt = float(s.high) >= target
                    else:
                        ss = float(s.high) >= stop
                        tt = float(s.low) <= target
                    if ss and tt:
                        return "ambiguous_5m", pd.Timestamp(s.date), j - entry_i + 1, True
                    if ss:
                        return "loss", pd.Timestamp(s.date), j - entry_i + 1, True
                    if tt:
                        return "win", pd.Timestamp(s.date), j - entry_i + 1, True
            return "ambiguous_15m", pd.Timestamp(row.date), j - entry_i + 1, False
        return ("loss" if hit_stop else "win"), pd.Timestamp(row.date), j - entry_i + 1, False
    return "timeout", pd.Timestamp(m15.iloc[end_i].date), end_i - entry_i + 1, False


def detect_symbol(m15_raw: pd.DataFrame, m5: pd.DataFrame | None, symbol: str, cfg: ProxyConfig) -> pd.DataFrame:
    df = add_causal_features(m15_raw, cfg)
    records: list[dict] = []
    warm = max(cfg.swing_lookback, cfg.bos_lookback, cfg.atr_period) + 2
    i = warm
    while i < len(df) - (cfg.max_bos_bars + cfg.max_entry_bars + 2):
        r = df.iloc[i]
        atr = float(r.atr) if pd.notna(r.atr) else math.nan
        if not np.isfinite(atr) or atr <= 0:
            i += 1
            continue

        candidates: list[tuple[str, float, float]] = []
        prev_low, prev_high = float(r.prev_swing_low), float(r.prev_swing_high)
        if np.isfinite(prev_low) and float(r.low) < prev_low - cfg.sweep_min_atr * atr and float(r.close) > prev_low:
            candidates.append(("long", prev_low, prev_low - float(r.low)))
        if np.isfinite(prev_high) and float(r.high) > prev_high + cfg.sweep_min_atr * atr and float(r.close) < prev_high:
            candidates.append(("short", prev_high, float(r.high) - prev_high))
        if not candidates:
            i += 1
            continue

        emitted = False
        for direction, swept_level, sweep_depth in candidates:
            bos_level = float(r.bos_up_level if direction == "long" else r.bos_dn_level)
            if not np.isfinite(bos_level):
                continue
            bos_i = None
            for j in range(i + 1, min(len(df), i + 1 + cfg.max_bos_bars)):
                close_j = float(df.iloc[j].close)
                if (direction == "long" and close_j > bos_level) or (direction == "short" and close_j < bos_level):
                    bos_i = j
                    break
            if bos_i is None:
                continue

            poi = find_poi(df, i, bos_i, direction)
            if poi is None:
                continue
            poi_i, zone_low, zone_high = poi
            if zone_high <= zone_low:
                continue
            entry = (zone_low + zone_high) / 2.0

            entry_i = None
            for k in range(bos_i + 1, min(len(df), bos_i + 1 + cfg.max_entry_bars)):
                if bar_touches(df.iloc[k], entry):
                    entry_i = k
                    break
            if entry_i is None:
                continue

            sweep_extreme = float(r.low if direction == "long" else r.high)
            stop = sweep_extreme - cfg.stop_buffer_atr * atr if direction == "long" else sweep_extreme + cfg.stop_buffer_atr * atr
            risk = entry - stop if direction == "long" else stop - entry
            if risk <= 0:
                continue
            risk_atr = risk / atr
            if not (cfg.min_risk_atr <= risk_atr <= cfg.max_risk_atr):
                continue
            target = entry + cfg.reward_r * risk if direction == "long" else entry - cfg.reward_r * risk

            outcome, exit_time, bars_held, used_5m = resolve_m15_outcome(
                df, m5, entry_i, direction, entry, stop, target, cfg.max_hold_bars
            )
            if outcome.startswith("ambiguous"):
                gross_r = np.nan
            elif outcome == "win":
                gross_r = cfg.reward_r
            elif outcome == "loss":
                gross_r = -1.0
            else:
                # Timeouts are marked-to-market at the final close and clipped to stop/TP range.
                final_close = float(df.iloc[min(len(df)-1, entry_i + cfg.max_hold_bars)].close)
                raw_r = (final_close - entry) / risk if direction == "long" else (entry - final_close) / risk
                gross_r = float(np.clip(raw_r, -1.0, cfg.reward_r))

            cost_cfg = SYMBOL_COST[symbol]
            base_cost = float(cost_cfg["spread"] + cost_cfg["slippage"])
            cost_as_r = base_cost / risk
            net_r = gross_r - cost_as_r if np.isfinite(gross_r) else np.nan

            entry_row = df.iloc[entry_i]
            bos_row = df.iloc[bos_i]
            london, ny, overlap = session_fields(pd.Timestamp(entry_row.date))
            bos_disp = abs(float(bos_row.close) - bos_level) / atr
            zone_width_atr = (zone_high - zone_low) / atr
            rec = {
                "setup_id": f"PUB_{symbol}_{pd.Timestamp(entry_row.date).strftime('%Y%m%d_%H%M')}_{direction}",
                "symbol": symbol,
                "direction": direction,
                "sweep_time": pd.Timestamp(r.date),
                "bos_time": pd.Timestamp(bos_row.date),
                "poi_time": pd.Timestamp(df.iloc[poi_i].date),
                "entry_time": pd.Timestamp(entry_row.date),
                "exit_time": exit_time,
                "entry": entry,
                "stop": stop,
                "target": target,
                "gross_r": gross_r,
                "cost_as_r": cost_as_r,
                "net_r": net_r,
                "outcome": outcome,
                "used_5m_resolution": used_5m,
                "bars_held": bars_held,
                "entry_hour": int(pd.Timestamp(entry_row.date).hour),
                "entry_dow": int(pd.Timestamp(entry_row.date).dayofweek),
                "is_london": london,
                "is_new_york": ny,
                "is_overlap": overlap,
                "atr": atr,
                "risk_distance": risk,
                "risk_atr": risk_atr,
                "sweep_depth_atr": sweep_depth / atr,
                "sweep_wick_ratio": wick_ratio(r, direction),
                "bos_displacement_atr": bos_disp,
                "zone_width_atr": zone_width_atr,
                "sweep_to_bos_bars": bos_i - i,
                "bos_to_entry_bars": entry_i - bos_i,
                "volume_z": float(entry_row.volume_z) if pd.notna(entry_row.volume_z) else np.nan,
                "trend20_atr": float(entry_row.trend20_atr) if pd.notna(entry_row.trend20_atr) else np.nan,
                "range_position_20": float(entry_row.range_position_20) if pd.notna(entry_row.range_position_20) else np.nan,
                "swept_level": swept_level,
            }
            records.append(rec)
            emitted = True
            break
        i += 2 if emitted else 1
    return pd.DataFrame(records)


def parse_number(value: object) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    s = str(value).strip().replace(",", "")
    if not s or s.lower() in {"nan", "none", "null"}:
        return np.nan
    # Compound releases like bond yield|bid-to-cover are excluded from surprise math.
    if "|" in s or "/" in s:
        return np.nan
    mult = 1.0
    if s.endswith("K"):
        mult, s = 1e3, s[:-1]
    elif s.endswith("M"):
        mult, s = 1e6, s[:-1]
    elif s.endswith("B"):
        mult, s = 1e9, s[:-1]
    elif s.endswith("T"):
        mult, s = 1e12, s[:-1]
    s = s.replace("%", "")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return float(m.group()) * mult if m else np.nan


def load_calendar(path: Path) -> pd.DataFrame:
    cal = pd.read_csv(path, low_memory=False)
    cal["event_time"] = pd.to_datetime(cal["DateTime"], utc=True, errors="coerce")
    cal = cal.dropna(subset=["event_time", "Currency"]).copy()
    impact_map = {"Non-Economic": 0, "Low Impact Expected": 1, "Medium Impact Expected": 2, "High Impact Expected": 3}
    cal["impact_n"] = cal["Impact"].map(impact_map).fillna(0).astype(int)
    cal["actual_n"] = cal["Actual"].map(parse_number)
    cal["forecast_n"] = cal["Forecast"].map(parse_number)
    raw_surprise = (cal["actual_n"] - cal["forecast_n"]) / (cal["forecast_n"].abs() + 1e-9)
    raw_surprise = raw_surprise.clip(-10, 10)
    # Use the dataset's own explanatory text where it clearly states the sign convention.
    detail = cal["Detail"].fillna("").str.lower()
    polarity = np.where(detail.str.contains("actual.*less than.*forecast.*good", regex=True), -1.0, 1.0)
    cal["surprise"] = raw_surprise * polarity
    return cal[["event_time", "Currency", "impact_n", "Event", "surprise"]].sort_values("event_time")


def attach_calendar(trades: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    rows = []
    cal_by_cur = {c: g.reset_index(drop=True) for c, g in cal.groupby("Currency")}
    for rec in trades.to_dict("records"):
        ts = pd.Timestamp(rec["entry_time"])
        symbol = rec["symbol"]
        candidates = []
        for cur in RELEVANT_CURRENCIES[symbol]:
            g = cal_by_cur.get(cur)
            if g is None or g.empty:
                continue
            window = g[(g.event_time >= ts - pd.Timedelta(hours=2)) & (g.event_time <= ts + pd.Timedelta(hours=2))].copy()
            if not window.empty:
                window["delta_min"] = (window.event_time - ts).dt.total_seconds() / 60
                candidates.append(window)
        if candidates:
            near = pd.concat(candidates, ignore_index=True)
            near["abs_delta"] = near["delta_min"].abs()
            high = near[near.impact_n >= 3]
            nearest = near.sort_values(["abs_delta", "impact_n"], ascending=[True, False]).iloc[0]
            nearest_high_min = float(high.abs_delta.min()) if not high.empty else 9999.0
            rec.update({
                "high_event_30m": int(nearest_high_min <= 30),
                "high_event_120m": int(nearest_high_min <= 120),
                "minutes_to_nearest_high_event": min(nearest_high_min, 9999.0),
                "nearby_event_count_120m": int(len(near)),
                "nearest_event_surprise": float(nearest.surprise) if pd.notna(nearest.surprise) else np.nan,
                "nearest_event_currency": str(nearest.Currency),
                "nearest_event_name": str(nearest.Event),
                "nearest_event_delta_min": float(nearest.delta_min),
            })
        else:
            rec.update({
                "high_event_30m": 0,
                "high_event_120m": 0,
                "minutes_to_nearest_high_event": 9999.0,
                "nearby_event_count_120m": 0,
                "nearest_event_surprise": np.nan,
                "nearest_event_currency": "NONE",
                "nearest_event_name": "NONE",
                "nearest_event_delta_min": np.nan,
            })
        rows.append(rec)
    return pd.DataFrame(rows)


def performance(x: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(x, errors="coerce").dropna()
    if s.empty:
        return {"n": 0, "win_rate": np.nan, "expectancy_r": np.nan, "profit_factor": np.nan, "total_r": 0.0, "max_drawdown_r": np.nan}
    gains, losses = s[s > 0].sum(), -s[s < 0].sum()
    eq = np.r_[0.0, s.cumsum().to_numpy()]
    peak = np.maximum.accumulate(eq)
    return {
        "n": int(len(s)),
        "win_rate": float((s > 0).mean()),
        "expectancy_r": float(s.mean()),
        "profit_factor": float(gains / losses) if losses > 0 else np.inf,
        "total_r": float(s.sum()),
        "max_drawdown_r": float((eq - peak).min()),
    }


def build_model(frame: pd.DataFrame, features: list[str]) -> Pipeline:
    cats = [c for c in features if frame[c].dtype == "object"]
    nums = [c for c in features if c not in cats]
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), nums),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cats),
    ])
    model = LGBMClassifier(
        n_estimators=240, learning_rate=0.025, num_leaves=15, max_depth=4,
        min_child_samples=45, colsample_bytree=0.85, subsample=0.9,
        reg_alpha=0.6, reg_lambda=1.2, random_state=42, verbose=-1,
    )
    return Pipeline([("pre", pre), ("model", model)])


def run_walk_forward(trades: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    usable = trades[trades.net_r.notna()].copy()
    usable["win"] = (usable.net_r > 0).astype(int)
    usable["year"] = pd.to_datetime(usable.entry_time, utc=True).dt.year
    years = sorted(y for y in usable.year.unique() if y >= 2022)
    rows, preds = [], []
    for year in years:
        train = usable[usable.year < year].copy()
        test = usable[usable.year == year].copy()
        if len(train) < 300 or len(test) < 30 or train.win.nunique() < 2 or test.win.nunique() < 2:
            continue
        pipe = build_model(train, FEATURES)
        pipe.fit(train[FEATURES], train.win)
        p_train = pipe.predict_proba(train[FEATURES])[:, 1]
        p_test = pipe.predict_proba(test[FEATURES])[:, 1]
        q50, q70 = float(np.quantile(p_train, 0.50)), float(np.quantile(p_train, 0.70))
        row = {
            "test_year": int(year), "train_n": int(len(train)), "test_n": int(len(test)),
            "auc": float(roc_auc_score(test.win, p_test)), "brier": float(brier_score_loss(test.win, p_test)),
        }
        row.update({f"all_{k}": v for k, v in performance(test.net_r).items()})
        for name, th in [("q50", q50), ("q70", q70)]:
            sel = test[p_test >= th]
            row[f"{name}_threshold"] = th
            row[f"{name}_coverage"] = float(len(sel) / len(test))
            row.update({f"{name}_{k}": v for k, v in performance(sel.net_r).items()})
        rows.append(row)
        tmp = test[["setup_id", "symbol", "direction", "entry_time", "outcome", "gross_r", "cost_as_r", "net_r", "win"]].copy()
        tmp["p_win"] = p_test
        tmp["test_year"] = year
        tmp["q50_threshold"] = q50
        tmp["q70_threshold"] = q70
        tmp["select_q50"] = p_test >= q50
        tmp["select_q70"] = p_test >= q70
        preds.append(tmp)
    yearly = pd.DataFrame(rows)
    pred = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame()
    yearly.to_csv(out_dir / "public_walk_forward_yearly.csv", index=False)
    pred.to_csv(out_dir / "public_walk_forward_predictions.csv", index=False)
    return yearly, pred


def cost_stress(pred: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    if pred.empty:
        return pd.DataFrame()
    rows = []
    for mult in [1.0, 1.5, 2.0, 3.0]:
        stressed = pred.gross_r - mult * pred.cost_as_r
        for name, mask in [
            ("all", np.ones(len(pred), dtype=bool)),
            ("q50", pred.select_q50.to_numpy(bool)),
            ("q70", pred.select_q70.to_numpy(bool)),
        ]:
            p = performance(stressed[mask])
            rows.append({"cost_multiple": mult, "selection": name, **p})
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "public_cost_stress.csv", index=False)
    return out


def symbol_summary(trades: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rows = []
    for symbol, g in trades.groupby("symbol"):
        valid = g[g.net_r.notna()]
        rows.append({
            "symbol": symbol,
            "trades_total": int(len(g)),
            "ambiguous": int(g.outcome.astype(str).str.startswith("ambiguous").sum()),
            "timeouts": int((g.outcome == "timeout").sum()),
            "used_5m_resolution": int(g.used_5m_resolution.sum()),
            **performance(valid.net_r),
        })
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "public_symbol_summary.csv", index=False)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--calendar", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = ProxyConfig()

    all_trades = []
    data_quality = []
    for symbol in ["EURUSD", "GBPUSD", "XAUUSD", "NAS100"]:
        m15_path = args.data_dir / f"{symbol}-15m.feather"
        m5_path = args.data_dir / f"{symbol}-5m.feather"
        m15 = load_market(m15_path, symbol)
        m5 = load_market(m5_path, symbol) if m5_path.exists() else None
        data_quality.append({
            "symbol": symbol,
            "m15_rows": len(m15),
            "m15_start": str(m15.date.min()),
            "m15_end": str(m15.date.max()),
            "m15_duplicate_dates": int(m15.date.duplicated().sum()),
            "m5_rows": len(m5) if m5 is not None else 0,
            "m5_start": str(m5.date.min()) if m5 is not None else None,
            "m5_end": str(m5.date.max()) if m5 is not None else None,
        })
        trades = detect_symbol(m15, m5, symbol, cfg)
        all_trades.append(trades)

    trades = pd.concat(all_trades, ignore_index=True).sort_values("entry_time").reset_index(drop=True)
    calendar = load_calendar(args.calendar)
    trades = attach_calendar(trades, calendar)
    trades.to_csv(args.out / "public_v2_proxy_trades.csv", index=False)
    pd.DataFrame(data_quality).to_csv(args.out / "public_data_quality.csv", index=False)
    sym = symbol_summary(trades, args.out)
    yearly, pred = run_walk_forward(trades, args.out)
    stress = cost_stress(pred, args.out)

    valid = trades[trades.net_r.notna()].copy()
    ambiguous_n = int(trades.outcome.astype(str).str.startswith("ambiguous").sum())
    result = {
        "experiment": "public_data_v2_proxy_v1",
        "proxy_config": asdict(cfg),
        "symbols": ["EURUSD", "GBPUSD", "XAUUSD", "NAS100"],
        "data_note": "NatoG93/market-data 15m + 5m public Hugging Face dataset; Forex Factory calendar archive for macro-event context.",
        "trade_count_total": int(len(trades)),
        "trade_count_valid": int(len(valid)),
        "ambiguous_count": ambiguous_n,
        "baseline": performance(valid.net_r),
        "walk_forward_years": yearly.test_year.astype(int).tolist() if not yearly.empty else [],
        "pooled_oos": {},
    }
    if not pred.empty:
        result["pooled_oos"] = {
            "n": int(len(pred)),
            "auc": float(roc_auc_score(pred.win, pred.p_win)),
            "brier": float(brier_score_loss(pred.win, pred.p_win)),
            "all": performance(pred.net_r),
            "q50": performance(pred.loc[pred.select_q50, "net_r"]),
            "q70": performance(pred.loc[pred.select_q70, "net_r"]),
        }
    (args.out / "public_summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    print("\nSymbol summary:\n", sym.to_string(index=False))
    if not yearly.empty:
        print("\nWalk-forward:\n", yearly.to_string(index=False))
    if not stress.empty:
        print("\nCost stress:\n", stress.to_string(index=False))


if __name__ == "__main__":
    main()
