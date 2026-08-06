from __future__ import annotations

import numpy as np
import pandas as pd


def performance(net_r: pd.Series) -> dict[str, float]:
    x = pd.Series(net_r, dtype=float).dropna()
    gains = x[x > 0].sum()
    losses = -x[x < 0].sum()
    return {
        "n": int(len(x)),
        "win_rate": float((x > 0).mean()),
        "expectancy_r": float(x.mean()),
        "profit_factor": float(gains / losses) if losses > 0 else float("inf"),
        "total_r": float(x.sum()),
        "max_drawdown_r": float(max_drawdown(x.to_numpy())),
    }


def max_drawdown(returns: np.ndarray) -> float:
    equity = np.cumsum(np.asarray(returns, dtype=float))
    equity = np.r_[0.0, equity]
    peaks = np.maximum.accumulate(equity)
    return float((equity - peaks).min())


def stressed_net_r(frame: pd.DataFrame, spread_multiple: float) -> pd.Series:
    """Stress total execution friction as a multiple of recovered spread cost."""
    return frame["gross_r"] - spread_multiple * frame["spread_as_r"]
