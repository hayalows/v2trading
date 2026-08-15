from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

def load_frames(d):
    f={}
    for s in ('EURUSD','GBPUSD'):
        x=q.enrich_single(q.load_duka(d/f'{s.lower()}-m15.json',s));f[s]=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
    return q.add_cross_features(f)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--chunk',type=int,required=True);ap.add_argument('--chunks',type=int,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    frames=load_frames(a.data_dir);rules=q.build_rules();geoms=[(sm,rr) for sm in q.STOP_GRID for rr in q.RR_GRID];mine=[g for i,g in enumerate(geoms) if i%a.chunks==a.chunk];rows=[];tested=0
    # Warm the outcome cache once per assigned geometry/pair, then every rule reuses it.
    for sm,rr in mine:
        for s,df in frames.items():
            q.simulate_config(df, q.to_events(pd.Series(0,index=df.index).to_numpy()), sm, rr, q.BASE_COST[s])
        for ri,rule in enumerate(rules,1):
            tested+=1;ts=[]
            for s,df in frames.items():
                d=q.to_events(rule.fn(df));t=q.simulate_config(df,d,sm,rr,q.BASE_COST[s])
                if t.empty:continue
                t['symbol']=s;t['stress_r']=t.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*t.atr);ts.append(t)
            if not ts:continue
            t=pd.concat(ts,ignore_index=True).sort_values('signal_time');pre=q.metrics(t[t.year<=2022]);ok,m=q.prehold_pass(t)
            rows.append({'kind':'rule','name':rule.name,'family':rule.family,'stop_atr':sm,'rr':rr,
              **{f'pre_{k}':v for k,v in pre.items()},'pre_stress_mean_r':m['stress_mean_r'],'pre_positive_years_2017_22':m['positive_2017_22'],'pre_max_year_share':m['max_year_share'],'pre_pass':ok,'robust_score':q.robustness_score(t) if ok else -999.0})
        print(f'chunk {a.chunk}: geometry {sm}ATR/{rr}R complete ({len(rows)} rows)',flush=True)
    z=pd.DataFrame(rows).sort_values(['pre_pass','robust_score','pre_mean_r'],ascending=[False,False,False]);z.to_csv(a.out/f'v36_exit_chunk{a.chunk}.csv',index=False)
    m={'chunk':a.chunk,'geometries':mine,'configs_tested':tested,'prehold_survivors':int(z.pre_pass.fillna(False).sum())};(a.out/f'v36_exit_chunk{a.chunk}.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2));print(z.head(20).to_string(index=False))
if __name__=='__main__':main()
