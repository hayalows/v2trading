from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
import v19_poi_penetration_research as v19

SYMBOLS = ('EURUSD','GBPUSD','XAUUSD')
DEPTH = 0.50
START_BALANCE = 500.0
RISK_PCT = 0.01
YEARS = (2022, 2023, 2024, 2025)


def load_json(path: Path) -> pd.DataFrame:
    raw = json.loads(path.read_text())
    df = pd.DataFrame(raw)
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    if 'volume' not in df: df['volume'] = 0.0
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df[['date','open','high','low','close','volume']].dropna().drop_duplicates('date', keep='last').sort_values('date').reset_index(drop=True)


def dd_stats(values):
    peak = values[0]
    max_dd = 0.0
    for x in values:
        peak = max(peak, x)
        if peak > 0: max_dd = max(max_dd, (peak-x)/peak)
    return max_dd


def equity(rows: pd.DataFrame, mode: str):
    bal = START_BALANCE
    curve = [bal]
    used = 0
    for _, r in rows.sort_values('fill_time').iterrows():
        o = r.outcome
        if mode == 'clean':
            if o not in ('win','loss'): continue
            rr = 2.5 if o == 'win' else -1.0
        elif mode == 'neutral':
            if not bool(r.filled): continue
            rr = 2.5 if o == 'win' else -1.0 if o == 'loss' else 0.0
        elif mode == 'pessimistic':
            if not bool(r.filled): continue
            rr = 2.5 if o == 'win' else -1.0 if (o == 'loss' or str(o).startswith('ambiguous')) else 0.0
        elif mode == 'optimistic':
            if not bool(r.filled): continue
            rr = 2.5 if (o == 'win' or str(o).startswith('ambiguous')) else -1.0 if o == 'loss' else 0.0
        else: raise ValueError(mode)
        bal *= (1.0 + RISK_PCT * rr)
        curve.append(bal); used += 1
    return {'ending_balance': round(bal,2), 'return_pct': round((bal/START_BALANCE-1)*100,2), 'max_drawdown_pct': round(dd_stats(curve)*100,2), 'trades_counted': used}


def summarize(g: pd.DataFrame):
    valid = g[g.risk_valid].copy()
    filled = valid[valid.filled].copy()
    resolved = filled[filled.outcome.isin(['win','loss'])]
    amb = filled[filled.outcome.astype(str).str.startswith('ambiguous')]
    unr = filled[filled.outcome.eq('unresolved')]
    wins = int((resolved.outcome=='win').sum()); losses = int((resolved.outcome=='loss').sum())
    opp = float(valid.gross_r_primary.sum()/len(valid)) if len(valid) else None
    exp_res = float(resolved.gross_r_primary.mean()) if len(resolved) else None
    return {
        'valid_setups': int(len(valid)), 'fills': int(len(filled)), 'fill_rate_pct': round(100*len(filled)/len(valid),2) if len(valid) else None,
        'resolved': int(len(resolved)), 'wins': wins, 'losses': losses,
        'resolved_win_rate_pct': round(100*wins/len(resolved),2) if len(resolved) else None,
        'ambiguous': int(len(amb)), 'ambiguous_rate_filled_pct': round(100*len(amb)/len(filled),2) if len(filled) else None,
        'unresolved': int(len(unr)), 'expectancy_per_resolved_fill_r': round(exp_res,4) if exp_res is not None else None,
        'opportunity_expectancy_r': round(opp,4) if opp is not None else None,
        'account': {m: equity(valid, m) for m in ['clean','neutral','pessimistic','optimistic']}
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data-dir',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    sims=[]; meta={}
    for symbol in SYMBOLS:
        df=load_json(args.data_dir/f'{symbol.lower()}-m15.json'); meta[symbol]={'rows':len(df),'from':str(df.date.min()),'to':str(df.date.max())}
        setups=v19.detect_pois(df,symbol)
        rows=[]
        for _,s in setups.iterrows():
            z=v19.zone_diagnostics(df,s); rows.append(v19.simulate_depth(df,s,DEPTH,z))
        sim=pd.DataFrame(rows); sims.append(sim)
    allsim=pd.concat(sims,ignore_index=True)
    allsim['fill_time']=pd.to_datetime(allsim.fill_time,utc=True,errors='coerce')
    bench=allsim[allsim.year.isin(YEARS)].copy()
    ytd=allsim[allsim.year.eq(2026)].copy()
    result={'study':'V2.5 common-engine three-market simulation','generated_at':pd.Timestamp.utcnow().isoformat(),'protocol':{'years':'2022-2025 completed years','entry_depth':0.5,'reward_r':2.5,'horizon_bars':192,'start_balance_usd':START_BALANCE,'risk_per_filled_trade_pct':1.0,'costs':'excluded','execution':'Dukascopy BID M15 OHLC structural proxy; ambiguous same-bar paths are not silently resolved'},'data':meta,'markets':{},'portfolio':summarize(bench),'ytd_2026':{}}
    for s in SYMBOLS:
        result['markets'][s]=summarize(bench[bench.symbol.eq(s)])
        result['ytd_2026'][s]=summarize(ytd[ytd.symbol.eq(s)])
    result['portfolio']['note']='Combined market sequence is sorted by recorded fill timestamp and does not enforce a concurrent-risk cap. Treat as gross research sensitivity, not executable account history.'
    (args.out/'v25-sim.json').write_text(json.dumps(result,indent=2,default=str))
    bench.to_csv(args.out/'v25-midpoint-trades.csv',index=False)
    print(json.dumps(result,indent=2,default=str))

if __name__=='__main__': main()
