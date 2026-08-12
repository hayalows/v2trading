from __future__ import annotations

"""Post-result robustness diagnostic for V2 v2.4 exit policies.

Triggered because the first frozen run revealed high M5 path ambiguity for early
break-even triggers. This script does not retroactively change the frozen policy
family. It scores every common policy row under explicit ambiguity assumptions.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

START_EQUITY = 500.0
RISK_PCT = 0.01
YEARS = {2022, 2023, 2024, 2025}


def equity(rs: pd.Series) -> tuple[float, float]:
    eq = START_EQUITY
    peak = eq
    dd = 0.0
    for r in rs.astype(float):
        eq *= max(1e-9, 1 + RISK_PCT * r)
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak)
    return float(eq), float(dd)


def scenario_series(g: pd.DataFrame, scenario: str, net: bool) -> pd.Series:
    base = g["net_r" if net else "gross_r"].copy()
    miss = ~np.isfinite(base)
    if net:
        costs = g.loc[miss, "cost_as_r"].astype(float)
        gross = {"pessimistic": -1.0, "neutral": 0.0, "optimistic": 2.5}[scenario]
        base.loc[miss] = gross - costs
    else:
        base.loc[miss] = {"pessimistic": -1.0, "neutral": 0.0, "optimistic": 2.5}[scenario]
    return base.astype(float)


def stats(g: pd.DataFrame, scenario: str, net: bool) -> dict:
    x = g.sort_values(["entry_time", "setup_id"]).copy()
    rs = scenario_series(x, scenario, net)
    eq, dd = equity(rs)
    return {
        "n": int(len(x)),
        "ambiguous": int((~np.isfinite(x["net_r"])).sum()),
        "ambiguity_rate": float((~np.isfinite(x["net_r"])).mean()),
        "mean_r": float(rs.mean()),
        "final_equity": eq,
        "max_drawdown": dd,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.input)
    df = df[df.year.isin(YEARS)].copy()

    result = {}
    for policy, g in df.groupby("policy"):
        result[policy] = {
            "gross": {s: stats(g, s, False) for s in ("pessimistic", "neutral", "optimistic")},
            "net_cost_stress": {s: stats(g, s, True) for s in ("pessimistic", "neutral", "optimistic")},
        }

    neutral_gross = sorted(result.items(), key=lambda kv: kv[1]["gross"]["neutral"]["mean_r"], reverse=True)
    neutral_net = sorted(result.items(), key=lambda kv: kv[1]["net_cost_stress"]["neutral"]["mean_r"], reverse=True)
    payload = {
        "status": "post-result robustness diagnostic",
        "reason": "first frozen run exposed policy-dependent M5 path ambiguity",
        "common_rows_per_policy": int(df.groupby("policy").size().min()),
        "results": result,
        "neutral_gross_ranking": [p for p, _ in neutral_gross],
        "neutral_net_ranking": [p for p, _ in neutral_net],
        "decision": "NO_EXIT_POLICY_PROMOTION",
    }
    (args.out / "v24_ambiguity_sensitivity.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# V2 v2.4 Exit Policy Robustness Note",
        "",
        "**Status: post-result diagnostic. No rule promotion.**",
        "",
        "The frozen v2.4 run exposed large policy-dependent M5 ordering ambiguity, especially for early break-even triggers. Comparing only resolved rows would bias the ranking because difficult paths disappear at different rates for different policies.",
        "",
        "This diagnostic therefore scores every common 2022-2025 policy row under three explicit assumptions for unresolved M5 paths: pessimistic = -1R, neutral = 0R, optimistic = +2.5R. The neutral case is the primary sensitivity view. Existing V2 spread/slippage approximations are also shown separately as a cost stress.",
        "",
        "## Neutral ambiguity comparison",
        "",
        "| Policy | Ambiguity | Gross mean R | Cost-stressed mean R | $500 cost-stressed equity |",
        "|---|---:|---:|---:|---:|",
    ]
    for policy, d in neutral_gross:
        g = d["gross"]["neutral"]
        n = d["net_cost_stress"]["neutral"]
        lines.append(f"| {policy} | {100*g['ambiguity_rate']:.1f}% | {g['mean_r']:+.4f} | {n['mean_r']:+.4f} | ${n['final_equity']:.2f} |")
    hold = result["hold_sltp"]["gross"]["neutral"]["mean_r"]
    t48 = result["timeout_48"]["gross"]["neutral"]["mean_r"]
    t96 = result["timeout_96"]["gross"]["neutral"]["mean_r"]
    be75 = result["be_075"]["gross"]["neutral"]
    lines += [
        "",
        "## What survives the stress test",
        "",
        f"- Hold-to-SL/TP: {hold:+.4f}R neutral structural mean.",
        f"- 96-bar timeout: {t96:+.4f}R, effectively tied with hold in this structural proxy.",
        f"- Current 48-bar timeout: {t48:+.4f}R, slightly lower than hold by {hold-t48:+.4f}R per setup.",
        f"- +0.75R break-even: {be75['mean_r']:+.4f}R neutral structural mean, but {100*be75['ambiguity_rate']:.1f}% of rows require unresolved intrabar ordering. Its resolved-row headline is therefore not reliable enough for promotion.",
        "- Partial-profit variants do not beat hold or the 96-bar timeout in the neutral all-row structural comparison.",
        "",
        "## Decision",
        "",
        "**NO_EXIT_POLICY_PROMOTION.** Keep the current paper engine frozen. Run hold-to-SL/TP, 96-bar timeout, break-even and partial-profit rules prospectively in shadow mode. Give priority to obtaining finer path data for the break-even candidates.",
        "",
        "The cost-stressed means are negative for every policy in this public-data proxy. That reinforces the existing v0.4 boundary: exit tuning cannot rescue unvalidated execution labels.",
    ]
    (args.out / "V24_EXIT_POLICY_ROBUSTNESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
