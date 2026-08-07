from __future__ import annotations

"""V2 Quant v0.3 research stack.

The v0.3 design deliberately separates three questions:

1. PRICE: can a stricter, completed-bar-only price/setup model rank V2 proxy trades?
2. EVENTS: does information that was genuinely known around economic releases add signal?
3. GOLD MACRO: does a lagged macro/geopolitical state model improve XAUUSD ranking?

This module never uses the entry candle's final close/volume as an entry-time feature and
never exposes an event's actual surprise to a trade timestamp that occurred before the event.
Daily macro observations are lagged by one day; monthly GPR is conservatively lagged until
after month-end to reduce point-in-time leakage.
"""

import argparse
import json
import math
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import public_data_v2_proxy as proxy


PRICE_SETUP_FEATURES = [
    "symbol", "direction", "entry_hour", "entry_dow", "is_london", "is_new_york", "is_overlap",
    "risk_atr", "sweep_depth_atr", "sweep_wick_ratio", "bos_displacement_atr", "zone_width_atr",
    "sweep_to_bos_bars", "bos_to_entry_bars", "cost_as_r",
    "pre_ret_1", "pre_ret_4", "pre_ret_16", "pre_ret_96",
    "pre_rv_8", "pre_rv_32", "pre_rv_96", "pre_atr_ratio_14_96",
    "pre_range_pos_20", "pre_range_pos_50", "pre_body_atr", "pre_range_atr",
    "pre_upper_wick_atr", "pre_lower_wick_atr", "pre_ema20_dev_atr", "pre_ema50_dev_atr",
    "pre_ema20_slope8_atr", "pre_dist_high20_atr", "pre_dist_low20_atr", "pre_volume_z",
]

EVENT_FEATURES = [
    "symbol", "direction", "entry_hour", "is_london", "is_new_york", "is_overlap",
    "prev_event_currency", "prev_event_category", "next_event_currency", "next_event_category",
    "minutes_since_prev_event", "minutes_to_next_event", "prev_event_impact", "next_event_impact",
    "prev_surprise_z", "prev_abs_surprise_z", "pre_event_30m", "pre_event_120m",
    "post_event_30m", "post_event_120m", "known_event_count_past120", "scheduled_event_count_next120",
]

FRED_SERIES = {
    "DFII10": "real10y",
    "DGS10": "nom10y",
    "T10YIE": "breakeven10y",
    "DTWEXBGS": "broad_usd",
    "VIXCLS": "vix",
    "DCOILWTICO": "wti",
    "DFF": "fedfunds",
    "BAMLH0A0HYM2": "hy_spread",
}


def perf(x: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(x, errors="coerce").dropna()
    if s.empty:
        return {"n": 0, "win_rate": np.nan, "expectancy_r": np.nan, "profit_factor": np.nan, "total_r": 0.0, "max_drawdown_r": np.nan}
    gains = float(s[s > 0].sum())
    losses = float(-s[s < 0].sum())
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


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev = df.close.shift(1)
    return pd.concat([(df.high - df.low), (df.high - prev).abs(), (df.low - prev).abs()], axis=1).max(axis=1)


def completed_bar_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    """Features become available only when a 15-minute bar has completed."""
    x = df.copy().sort_values("date").reset_index(drop=True)
    close = x.close.astype(float)
    logc = np.log(close.replace(0, np.nan))
    lr = logc.diff()
    tr = _true_range(x)
    atr14 = tr.rolling(14, min_periods=14).mean()
    atr96 = tr.rolling(96, min_periods=48).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    hi20 = x.high.rolling(20, min_periods=20).max()
    lo20 = x.low.rolling(20, min_periods=20).min()
    hi50 = x.high.rolling(50, min_periods=30).max()
    lo50 = x.low.rolling(50, min_periods=30).min()
    vol_mu = x.volume.rolling(40, min_periods=20).mean()
    vol_sd = x.volume.rolling(40, min_periods=20).std().replace(0, np.nan)
    body = (x.close - x.open).abs()
    upper = x.high - x[["open", "close"]].max(axis=1)
    lower = x[["open", "close"]].min(axis=1) - x.low

    f = pd.DataFrame({"available_time": pd.to_datetime(x.date, utc=True) + pd.Timedelta(minutes=15)})
    f["pre_ret_1"] = lr
    f["pre_ret_4"] = logc - logc.shift(4)
    f["pre_ret_16"] = logc - logc.shift(16)
    f["pre_ret_96"] = logc - logc.shift(96)
    f["pre_rv_8"] = lr.rolling(8, min_periods=6).std()
    f["pre_rv_32"] = lr.rolling(32, min_periods=20).std()
    f["pre_rv_96"] = lr.rolling(96, min_periods=48).std()
    f["pre_atr_ratio_14_96"] = atr14 / atr96.replace(0, np.nan)
    f["pre_range_pos_20"] = (close - lo20) / (hi20 - lo20).replace(0, np.nan)
    f["pre_range_pos_50"] = (close - lo50) / (hi50 - lo50).replace(0, np.nan)
    f["pre_body_atr"] = body / atr14.replace(0, np.nan)
    f["pre_range_atr"] = (x.high - x.low) / atr14.replace(0, np.nan)
    f["pre_upper_wick_atr"] = upper / atr14.replace(0, np.nan)
    f["pre_lower_wick_atr"] = lower / atr14.replace(0, np.nan)
    f["pre_ema20_dev_atr"] = (close - ema20) / atr14.replace(0, np.nan)
    f["pre_ema50_dev_atr"] = (close - ema50) / atr14.replace(0, np.nan)
    f["pre_ema20_slope8_atr"] = (ema20 - ema20.shift(8)) / atr14.replace(0, np.nan)
    f["pre_dist_high20_atr"] = (hi20 - close) / atr14.replace(0, np.nan)
    f["pre_dist_low20_atr"] = (close - lo20) / atr14.replace(0, np.nan)
    f["pre_volume_z"] = (x.volume - vol_mu) / vol_sd
    return f


def attach_completed_price_features(trades: pd.DataFrame, data_dir: Path) -> pd.DataFrame:
    chunks = []
    for symbol, g in trades.groupby("symbol", sort=False):
        market = proxy.load_market(data_dir / f"{symbol}-15m.feather", symbol)
        feat = completed_bar_feature_table(market).sort_values("available_time")
        part = g.copy().sort_values("entry_time")
        part["entry_time"] = pd.to_datetime(part.entry_time, utc=True)
        part = pd.merge_asof(part, feat, left_on="entry_time", right_on="available_time", direction="backward", allow_exact_matches=True)
        chunks.append(part)
    return pd.concat(chunks, ignore_index=True).sort_values("entry_time").reset_index(drop=True)


def event_category(name: object) -> str:
    s = str(name).lower()
    rules = [
        (r"fomc|interest rate|cash rate|bank rate|refinancing rate|monetary policy|rate statement", "rates"),
        (r"cpi|pce|inflation|consumer price|producer price|ppi", "inflation"),
        (r"non-farm|nonfarm|employment|unemployment|jobless|claims|earnings|payroll|vacanc|jolts", "labor"),
        (r"gdp|pmi|ism|industrial production|retail sales|consumer confidence|sentiment|durable", "growth"),
        (r"trade balance|current account|import|export", "external"),
        (r"housing|home sales|building permit|mortgage", "housing"),
        (r"speech|testifies|press conference|minutes", "communication"),
        (r"auction|bond|yield", "rates_market"),
    ]
    for pat, cat in rules:
        if re.search(pat, s):
            return cat
    return "other"


def load_causal_calendar(path: Path) -> pd.DataFrame:
    cal = pd.read_csv(path, low_memory=False)
    cal["event_time"] = pd.to_datetime(cal["DateTime"], utc=True, errors="coerce")
    cal = cal.dropna(subset=["event_time", "Currency"]).copy()
    impact_map = {"Non-Economic": 0, "Low Impact Expected": 1, "Medium Impact Expected": 2, "High Impact Expected": 3}
    cal["impact_n"] = cal["Impact"].map(impact_map).fillna(0).astype(int)
    cal["actual_n"] = cal["Actual"].map(proxy.parse_number)
    cal["forecast_n"] = cal["Forecast"].map(proxy.parse_number)
    cal["event_name"] = cal["Event"].fillna("UNKNOWN").astype(str)
    cal["event_category"] = cal.event_name.map(event_category)
    cal["raw_surprise"] = cal.actual_n - cal.forecast_n
    cal = cal.sort_values("event_time").reset_index(drop=True)

    # Standardize surprises only with PREVIOUS releases of the same currency/event.
    keys = ["Currency", "event_name"]
    grp = cal.groupby(keys, sort=False)["raw_surprise"]
    hist_mean = grp.transform(lambda s: s.shift(1).expanding(min_periods=5).mean())
    hist_std = grp.transform(lambda s: s.shift(1).expanding(min_periods=5).std()).replace(0, np.nan)
    cal["surprise_z"] = ((cal.raw_surprise - hist_mean) / hist_std).clip(-6, 6)
    return cal[["event_time", "Currency", "impact_n", "event_name", "event_category", "surprise_z"]]


def _relevant_currencies(symbol: str) -> set[str]:
    return proxy.RELEVANT_CURRENCIES.get(symbol, {"USD"})


def attach_causal_event_features(trades: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    rows = []
    cal_by_cur = {c: g.sort_values("event_time").reset_index(drop=True) for c, g in cal.groupby("Currency")}
    for rec in trades.to_dict("records"):
        ts = pd.Timestamp(rec["entry_time"])
        relevant = []
        for cur in _relevant_currencies(str(rec["symbol"])):
            g = cal_by_cur.get(cur)
            if g is not None and not g.empty:
                relevant.append(g)
        if relevant:
            pool = pd.concat(relevant, ignore_index=True).sort_values("event_time")
            important = pool[pool.impact_n >= 2]
            prev = important[important.event_time <= ts]
            nxt = important[important.event_time > ts]
            p = prev.iloc[-1] if not prev.empty else None
            n = nxt.iloc[0] if not nxt.empty else None
            since = (ts - p.event_time).total_seconds() / 60 if p is not None else 9999.0
            eta = (n.event_time - ts).total_seconds() / 60 if n is not None else 9999.0
            past120 = important[(important.event_time <= ts) & (important.event_time >= ts - pd.Timedelta(minutes=120))]
            next120 = important[(important.event_time > ts) & (important.event_time <= ts + pd.Timedelta(minutes=120))]
            rec.update({
                "prev_event_currency": str(p.Currency) if p is not None else "NONE",
                "prev_event_category": str(p.event_category) if p is not None else "NONE",
                "next_event_currency": str(n.Currency) if n is not None else "NONE",
                "next_event_category": str(n.event_category) if n is not None else "NONE",
                "minutes_since_prev_event": float(min(since, 9999.0)),
                "minutes_to_next_event": float(min(eta, 9999.0)),
                "prev_event_impact": int(p.impact_n) if p is not None else 0,
                "next_event_impact": int(n.impact_n) if n is not None else 0,
                # This is known because p is strictly in the past. No future surprise is attached.
                "prev_surprise_z": float(p.surprise_z) if p is not None and pd.notna(p.surprise_z) else np.nan,
                "prev_abs_surprise_z": float(abs(p.surprise_z)) if p is not None and pd.notna(p.surprise_z) else np.nan,
                "pre_event_30m": int(0 < eta <= 30),
                "pre_event_120m": int(0 < eta <= 120),
                "post_event_30m": int(0 <= since <= 30),
                "post_event_120m": int(0 <= since <= 120),
                "known_event_count_past120": int(len(past120)),
                "scheduled_event_count_next120": int(len(next120)),
            })
        else:
            rec.update({
                "prev_event_currency": "NONE", "prev_event_category": "NONE",
                "next_event_currency": "NONE", "next_event_category": "NONE",
                "minutes_since_prev_event": 9999.0, "minutes_to_next_event": 9999.0,
                "prev_event_impact": 0, "next_event_impact": 0,
                "prev_surprise_z": np.nan, "prev_abs_surprise_z": np.nan,
                "pre_event_30m": 0, "pre_event_120m": 0, "post_event_30m": 0, "post_event_120m": 0,
                "known_event_count_past120": 0, "scheduled_event_count_next120": 0,
            })
        rows.append(rec)
    return pd.DataFrame(rows)


def _preprocessor(frame: pd.DataFrame, features: list[str]) -> ColumnTransformer:
    cats = [c for c in features if not pd.api.types.is_numeric_dtype(frame[c])]
    nums = [c for c in features if c not in cats]
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), nums),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cats),
    ])


def lgbm_pipeline(frame: pd.DataFrame, features: list[str], seed: int, small: bool = False) -> Pipeline:
    pre = _preprocessor(frame, features)
    model = LGBMClassifier(
        n_estimators=320 if not small else 220,
        learning_rate=0.018 if not small else 0.025,
        num_leaves=15 if not small else 9,
        max_depth=4 if not small else 3,
        min_child_samples=40 if not small else 25,
        colsample_bytree=0.78,
        subsample=0.85,
        reg_alpha=0.9,
        reg_lambda=1.8,
        random_state=seed,
        verbose=-1,
    )
    return Pipeline([("pre", pre), ("model", model)])


def logistic_pipeline(frame: pd.DataFrame, features: list[str]) -> Pipeline:
    return Pipeline([
        ("pre", _preprocessor(frame, features)),
        ("model", LogisticRegression(C=0.35, max_iter=3000, solver="liblinear")),
    ])


def bagged_prob(train: pd.DataFrame, test: pd.DataFrame, features: list[str], seeds: Iterable[int], small: bool = False) -> tuple[np.ndarray, np.ndarray]:
    p_tr, p_te = [], []
    for seed in seeds:
        m = lgbm_pipeline(train, features, seed=seed, small=small)
        m.fit(train[features], train.win)
        p_tr.append(m.predict_proba(train[features])[:, 1])
        p_te.append(m.predict_proba(test[features])[:, 1])
    return np.mean(p_tr, axis=0), np.mean(p_te, axis=0)


def walk_forward_price(df: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = df[df.net_r.notna()].copy()
    x["entry_time"] = pd.to_datetime(x.entry_time, utc=True)
    x["exit_time"] = pd.to_datetime(x.exit_time, utc=True)
    x["year"] = x.entry_time.dt.year
    x["win"] = (x.net_r > 0).astype(int)
    rows, pred_rows = [], []
    for year in [2023, 2024, 2025]:
        boundary = pd.Timestamp(f"{year}-01-01", tz="UTC")
        # Purge any trade that could overlap the test boundary.
        train = x[(x.entry_time < boundary) & (x.exit_time < boundary - pd.Timedelta(hours=1))].copy()
        test = x[x.year == year].copy()
        if len(train) < 300 or len(test) < 50:
            continue
        p_train, p_test = bagged_prob(train, test, PRICE_SETUP_FEATURES, seeds=[11, 23, 47, 71, 101])
        q50, q70 = np.quantile(p_train, [0.50, 0.70])
        row = {"test_year": year, "train_n": len(train), "test_n": len(test),
               "auc": roc_auc_score(test.win, p_test), "brier": brier_score_loss(test.win, p_test)}
        row.update({f"all_{k}": v for k, v in perf(test.net_r).items()})
        for name, th in [("q50", q50), ("q70", q70)]:
            mask = p_test >= th
            row[f"{name}_threshold"] = float(th)
            row[f"{name}_coverage"] = float(mask.mean())
            row.update({f"{name}_{k}": v for k, v in perf(test.loc[mask, "net_r"]).items()})
        rows.append(row)
        z = test[["setup_id", "symbol", "direction", "entry_time", "exit_time", "net_r", "win"]].copy()
        z["p_price"] = p_test
        z["q50_threshold"] = q50
        z["q70_threshold"] = q70
        pred_rows.append(z)
    yearly = pd.DataFrame(rows)
    preds = pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame()
    yearly.to_csv(out / "v03_price_walk_forward.csv", index=False)
    preds.to_csv(out / "v03_price_oos_predictions.csv", index=False)
    return yearly, preds


def walk_forward_event(df: pd.DataFrame, price_preds: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = df[df.net_r.notna()].copy()
    x["entry_time"] = pd.to_datetime(x.entry_time, utc=True)
    x["exit_time"] = pd.to_datetime(x.exit_time, utc=True)
    x["year"] = x.entry_time.dt.year
    x["win"] = (x.net_r > 0).astype(int)
    x["event_relevant"] = (x.minutes_since_prev_event <= 180) | (x.minutes_to_next_event <= 180)
    x = x[x.event_relevant].copy()
    rows, pred_rows = [], []
    for year in [2023, 2024, 2025]:
        boundary = pd.Timestamp(f"{year}-01-01", tz="UTC")
        train = x[(x.entry_time < boundary) & (x.exit_time < boundary - pd.Timedelta(hours=1))]
        test = x[x.year == year]
        if len(train) < 100 or len(test) < 20 or train.win.nunique() < 2 or test.win.nunique() < 2:
            continue
        p_train, p_test = bagged_prob(train, test, EVENT_FEATURES, seeds=[13, 31, 53], small=True)
        rows.append({
            "test_year": year, "train_n": len(train), "test_n": len(test),
            "event_auc": roc_auc_score(test.win, p_test), "event_brier": brier_score_loss(test.win, p_test),
            "event_expectancy_r": float(test.net_r.mean()),
        })
        z = test[["setup_id", "symbol", "entry_time", "net_r", "win"]].copy()
        z["p_event"] = p_test
        pred_rows.append(z)
    yearly = pd.DataFrame(rows)
    ep = pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame()
    yearly.to_csv(out / "v03_event_model_yearly.csv", index=False)
    ep.to_csv(out / "v03_event_oos_predictions.csv", index=False)

    if not price_preds.empty:
        combined = price_preds.copy()
        combined = combined.merge(ep[["setup_id", "p_event"]] if not ep.empty else pd.DataFrame(columns=["setup_id", "p_event"]), on="setup_id", how="left")
        combined["p_combined"] = np.where(combined.p_event.notna(), 0.80 * combined.p_price + 0.20 * combined.p_event, combined.p_price)
        combined.to_csv(out / "v03_price_event_combined_oos.csv", index=False)
    return yearly, ep


def _fred_features(path: Path, series_id: str, prefix: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    date_col = d.columns[0]
    value_col = d.columns[1]
    d["date"] = pd.to_datetime(d[date_col], errors="coerce")
    d["value"] = pd.to_numeric(d[value_col], errors="coerce")
    d = d.dropna(subset=["date", "value"]).sort_values("date")
    if prefix in {"broad_usd", "vix", "wti"}:
        lv = np.log(d.value.where(d.value > 0))
        d[f"{prefix}_level"] = d.value
        d[f"{prefix}_chg1"] = lv.diff(1)
        d[f"{prefix}_chg5"] = lv.diff(5)
        d[f"{prefix}_chg20"] = lv.diff(20)
    else:
        d[f"{prefix}_level"] = d.value
        d[f"{prefix}_chg1"] = d.value.diff(1)
        d[f"{prefix}_chg5"] = d.value.diff(5)
        d[f"{prefix}_chg20"] = d.value.diff(20)
    # Daily closes/observations are not assumed available during the same trading day.
    d["available_time"] = pd.to_datetime(d.date, utc=True) + pd.Timedelta(days=1)
    keep = ["available_time"] + [c for c in d.columns if c.startswith(prefix + "_")]
    return d[keep]


def attach_macro(trades: pd.DataFrame, macro_dir: Path, gpr_path: Path | None) -> tuple[pd.DataFrame, list[str]]:
    x = trades.copy().sort_values("entry_time")
    x["entry_time"] = pd.to_datetime(x.entry_time, utc=True)
    macro_features: list[str] = []
    for sid, prefix in FRED_SERIES.items():
        path = macro_dir / f"{sid}.csv"
        if not path.exists():
            continue
        f = _fred_features(path, sid, prefix).sort_values("available_time")
        cols = [c for c in f.columns if c != "available_time"]
        macro_features.extend(cols)
        x = pd.merge_asof(x.sort_values("entry_time"), f, left_on="entry_time", right_on="available_time", direction="backward")
        x = x.drop(columns=["available_time"])

    if gpr_path and gpr_path.exists():
        g = pd.read_excel(gpr_path)
        month_col = "month" if "month" in g.columns else g.columns[0]
        g["month"] = pd.to_datetime(g[month_col], errors="coerce")
        candidates = [c for c in ["GPR", "GPRT", "GPRA"] if c in g.columns]
        g = g.dropna(subset=["month"]).sort_values("month")
        for c in candidates:
            g[c] = pd.to_numeric(g[c], errors="coerce")
            g[f"{c.lower()}_chg1m"] = g[c].diff(1)
        # Conservative publication proxy: only expose a month's value 10 days after month-end.
        g["available_time"] = pd.to_datetime(g.month + pd.offsets.MonthEnd(0) + pd.Timedelta(days=10), utc=True)
        keep = ["available_time"] + candidates + [f"{c.lower()}_chg1m" for c in candidates]
        g = g[keep].dropna(subset=["available_time"]).sort_values("available_time")
        rename = {c: c.lower() for c in candidates}
        g = g.rename(columns=rename)
        cols = [c for c in g.columns if c != "available_time"]
        macro_features.extend(cols)
        x = pd.merge_asof(x.sort_values("entry_time"), g, left_on="entry_time", right_on="available_time", direction="backward")
        x = x.drop(columns=["available_time"])

    # Interactions suggested by gold's opportunity-cost / risk channels.
    def safe_mul(a: str, b: str, name: str) -> None:
        nonlocal x, macro_features
        if a in x.columns and b in x.columns:
            x[name] = pd.to_numeric(x[a], errors="coerce") * pd.to_numeric(x[b], errors="coerce")
            macro_features.append(name)
    safe_mul("real10y_chg5", "broad_usd_chg5", "real_yield_x_usd_5")
    safe_mul("gpr", "broad_usd_chg5", "gpr_x_usd_5")
    safe_mul("wti_chg5", "real10y_chg5", "oil_x_real_yield_5")
    return x, sorted(set(macro_features))


def gold_macro_walk_forward(df: pd.DataFrame, macro_features: list[str], price_preds: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = df[(df.symbol == "XAUUSD") & df.net_r.notna()].copy()
    x["entry_time"] = pd.to_datetime(x.entry_time, utc=True)
    x["exit_time"] = pd.to_datetime(x.exit_time, utc=True)
    x["year"] = x.entry_time.dt.year
    x["win"] = (x.net_r > 0).astype(int)
    features = ["direction", "entry_hour", "risk_atr", "cost_as_r", "pre_ret_16", "pre_ret_96", "pre_rv_32", "pre_atr_ratio_14_96"] + macro_features
    features = [c for c in features if c in x.columns]
    rows, preds = [], []
    for year in [2023, 2024, 2025]:
        boundary = pd.Timestamp(f"{year}-01-01", tz="UTC")
        train = x[(x.entry_time < boundary) & (x.exit_time < boundary - pd.Timedelta(hours=1))]
        test = x[x.year == year]
        if len(train) < 80 or len(test) < 20 or train.win.nunique() < 2 or test.win.nunique() < 2:
            continue
        model = logistic_pipeline(train, features)
        model.fit(train[features], train.win)
        p = model.predict_proba(test[features])[:, 1]
        rows.append({"test_year": year, "train_n": len(train), "test_n": len(test),
                     "macro_auc": roc_auc_score(test.win, p), "macro_brier": brier_score_loss(test.win, p)})
        z = test[["setup_id", "entry_time", "net_r", "win"]].copy()
        z["p_gold_macro"] = p
        preds.append(z)
    yearly = pd.DataFrame(rows)
    gp = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame()
    yearly.to_csv(out / "v03_gold_macro_yearly.csv", index=False)
    gp.to_csv(out / "v03_gold_macro_oos_predictions.csv", index=False)

    if not price_preds.empty:
        ppx = price_preds[price_preds.symbol == "XAUUSD"].copy()
        blend = ppx.merge(gp[["setup_id", "p_gold_macro"]] if not gp.empty else pd.DataFrame(columns=["setup_id", "p_gold_macro"]), on="setup_id", how="left")
        blend["p_gold_blend"] = np.where(blend.p_gold_macro.notna(), 0.70 * blend.p_price + 0.30 * blend.p_gold_macro, blend.p_price)
        blend.to_csv(out / "v03_gold_blended_oos.csv", index=False)
    return yearly, gp


def score_summary(pred: pd.DataFrame, score_col: str) -> dict[str, float]:
    if pred.empty or score_col not in pred:
        return {}
    z = pred.dropna(subset=[score_col, "win", "net_r"]).copy()
    if z.empty or z.win.nunique() < 2:
        return {}
    q50 = z[score_col].quantile(0.50)
    q70 = z[score_col].quantile(0.70)
    return {
        "n": int(len(z)),
        "auc": float(roc_auc_score(z.win, z[score_col])),
        "brier": float(brier_score_loss(z.win, z[score_col].clip(0, 1))),
        "all_expectancy_r": float(z.net_r.mean()),
        "q50_n": int((z[score_col] >= q50).sum()),
        "q50_expectancy_r": float(z.loc[z[score_col] >= q50, "net_r"].mean()),
        "q70_n": int((z[score_col] >= q70).sum()),
        "q70_expectancy_r": float(z.loc[z[score_col] >= q70, "net_r"].mean()),
    }


def select_tick_windows(trades: pd.DataFrame, out: Path) -> pd.DataFrame:
    """Small, stratified set for true bid/ask tick replay, not a cherry-picked winners set."""
    x = trades[trades.net_r.notna()].copy()
    x["entry_time"] = pd.to_datetime(x.entry_time, utc=True)
    x["exit_time"] = pd.to_datetime(x.exit_time, utc=True)
    instrument_map = {"EURUSD": "eurusd", "GBPUSD": "gbpusd", "XAUUSD": "xauusd", "NAS100": "usatechidxusd"}
    picks = []
    rng = np.random.default_rng(202603)
    for symbol, g in x[x.symbol.isin(instrument_map)].groupby("symbol"):
        g = g[(g.entry_time.dt.year >= 2023) & (g.entry_time.dt.year <= 2025)].copy()
        if g.empty:
            continue
        groups = [g[g.net_r > 0], g[g.net_r <= 0], g.nlargest(min(4, len(g)), "cost_as_r")]
        chosen = []
        for subgroup in groups[:2]:
            if not subgroup.empty:
                idx = rng.choice(subgroup.index.to_numpy(), size=min(3, len(subgroup)), replace=False)
                chosen.extend(idx.tolist())
        chosen.extend(groups[2].index.tolist())
        for _, r in g.loc[sorted(set(chosen))].head(10).iterrows():
            start = r.entry_time.floor("D")
            # one-day tick windows are enough for the 12h max holding period for most entries;
            # late-day entries use two calendar days.
            end = start + pd.Timedelta(days=2 if r.entry_time.hour >= 12 else 1)
            picks.append({
                "setup_id": r.setup_id, "symbol": symbol, "dukascopy_instrument": instrument_map[symbol],
                "entry_time": r.entry_time.isoformat(), "exit_time_m15": r.exit_time.isoformat(),
                "entry": r.entry, "stop": r.stop, "target": r.target, "direction": r.direction,
                "m15_outcome": r.outcome, "from": start.date().isoformat(), "to": end.date().isoformat(),
            })
    result = pd.DataFrame(picks)
    result.to_csv(out / "v03_tick_windows.csv", index=False)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--calendar", type=Path, required=True)
    ap.add_argument("--macro-dir", type=Path, required=True)
    ap.add_argument("--gpr", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(args.trades)
    for c in ["entry_time", "exit_time", "sweep_time", "bos_time", "poi_time"]:
        if c in trades:
            trades[c] = pd.to_datetime(trades[c], utc=True, errors="coerce")

    strict = attach_completed_price_features(trades, args.data_dir)
    cal = load_causal_calendar(args.calendar)
    strict = attach_causal_event_features(strict, cal)
    strict, macro_features = attach_macro(strict, args.macro_dir, args.gpr)
    strict.to_csv(args.out / "v03_trade_feature_ledger.csv", index=False)

    price_yearly, price_preds = walk_forward_price(strict, args.out)
    event_yearly, event_preds = walk_forward_event(strict, price_preds, args.out)
    gold_yearly, gold_preds = gold_macro_walk_forward(strict, macro_features, price_preds, args.out)
    tick_windows = select_tick_windows(strict, args.out)

    combined_path = args.out / "v03_price_event_combined_oos.csv"
    combined = pd.read_csv(combined_path) if combined_path.exists() else pd.DataFrame()
    gold_blend_path = args.out / "v03_gold_blended_oos.csv"
    gold_blend = pd.read_csv(gold_blend_path) if gold_blend_path.exists() else pd.DataFrame()

    summary = {
        "version": "V2 Quant v0.3",
        "design": "completed-bar price model + causal event model + lagged XAU macro/GPR model + targeted tick windows",
        "strict_price": score_summary(price_preds, "p_price"),
        "price_plus_event": score_summary(combined, "p_combined") if not combined.empty else {},
        "gold_price_only": score_summary(price_preds[price_preds.symbol == "XAUUSD"] if not price_preds.empty else pd.DataFrame(), "p_price"),
        "gold_price_plus_macro": score_summary(gold_blend, "p_gold_blend") if not gold_blend.empty else {},
        "event_model_years": event_yearly.to_dict("records"),
        "gold_macro_years": gold_yearly.to_dict("records"),
        "macro_features": macro_features,
        "tick_windows_selected": int(len(tick_windows)),
        "leakage_corrections": [
            "entry candle final close/volume are excluded; price state comes from completed M15 bars only",
            "future economic releases never expose actual/surprise fields before their event timestamp",
            "daily macro series are lagged by one day",
            "monthly GPR is only exposed after a conservative post-month-end delay",
            "training trades overlapping an OOS year boundary are purged",
        ],
    }
    (args.out / "v03_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
