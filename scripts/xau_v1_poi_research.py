from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--start', default='2020-01-01')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    raw = json.loads(args.json.read_text())
    df = pd.DataFrame(raw)
    required = {'timestamp','open','high','low','close'}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f'XAU Dukascopy JSON missing {sorted(missing)}; columns={list(df.columns)}')
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    if 'volume' not in df: df['volume'] = 0.0
    df = df[['date','open','high','low','close','volume']].copy()
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna().drop_duplicates('date', keep='last').sort_values('date').reset_index(drop=True)
    feather = args.out / 'XAUUSD-15m.feather'
    df.to_feather(feather)

    import v19_poi_penetration_research as v19
    v19.SYMBOLS = ('XAUUSD',)
    v19.COMPLETED_YEARS = (2022, 2023, 2024, 2025)
    result_dir = args.out / 'poi'
    old = sys.argv[:]
    try:
        sys.argv = ['v19_poi_penetration_research.py', '--data-dir', str(args.out), '--start', args.start, '--out', str(result_dir)]
        v19.main()
    finally:
        sys.argv = old

    summary = json.loads((result_dir / 'v19_poi_penetration_summary.json').read_text())
    summary['study'] = 'V2 XAU v0.4 POI penetration walk-forward'
    summary['asset'] = 'XAUUSD'
    summary['source'] = 'Dukascopy public/indicative XAUUSD M15 via dukascopy-node'
    summary['boundary'] = 'Gold-specific OHLC structural proxy only; no broker execution or live-money claim.'
    (args.out / 'XAU_V04_POI_SUMMARY.json').write_text(json.dumps(summary, indent=2, default=str))

    mid = summary.get('midpoint_completed') or {}
    best = summary.get('best_descriptive_completed') or {}
    boot = summary.get('walkforward_completed_bootstrap_candidate_minus_midpoint') or {}
    wf = summary.get('walkforward') or []
    def pct(x): return '—' if x is None else f'{100*x:.2f}%'
    def rr(x): return '—' if x is None else f'{x:+.4f}R'
    lines = [
        '# V2 XAU v0.4 POI Walk-Forward Result', '',
        '**Research only. Gold parameters are not promoted from this report alone.**', '',
        f"Source rows: {len(df):,} XAUUSD M15 candles from {df.date.min()} to {df.date.max()}.", '',
        '## Completed-year midpoint baseline (2022-2025)', '',
        f"- valid-risk setups: {mid.get('valid_risk_setups','—')}",
        f"- fill rate: {pct(mid.get('fill_rate'))}",
        f"- resolved fills: {mid.get('resolved_fills','—')}",
        f"- resolved win rate: {pct(mid.get('win_rate_resolved'))}",
        f"- opportunity expectancy: {rr(mid.get('opportunity_expectancy_r'))}",
        f"- ambiguous rate among fills: {pct(mid.get('ambiguous_rate_filled'))}", '',
        '## Descriptive best depth', '',
        f"- depth: {pct(best.get('depth'))}",
        f"- opportunity expectancy: {rr(best.get('opportunity_expectancy_r'))}",
        f"- fill rate: {pct(best.get('fill_rate'))}", '',
        '## Chronological walk-forward', '',
        '| Year | Chosen depth | Candidate R | Midpoint R | Delta |',
        '|---:|---:|---:|---:|---:|',
    ]
    for r in wf:
        lines.append(f"| {r.get('year')} | {pct(r.get('chosen_depth'))} | {rr(r.get('candidate_opportunity_r'))} | {rr(r.get('midpoint_opportunity_r'))} | {rr(r.get('delta_r'))} |")
    lines += ['', f"Bootstrap paired candidate-minus-midpoint: n={boot.get('n','—')}, point={rr(boot.get('point'))}, 95% interval [{rr(boot.get('low95'))}, {rr(boot.get('high95'))}].", '',
              f"**Frozen decision from this protocol: {summary.get('decision','—')}**", '',
              'A descriptive best depth is not a production rule. Promotion requires chronological stability, cost stress, finer-path ambiguity checks and prospective XAU shadow evidence.']
    (args.out / 'XAU_V04_POI_RESULT.md').write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__ == '__main__':
    main()