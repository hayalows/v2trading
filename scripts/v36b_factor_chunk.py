from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36b_usd_factor as b
q=b.q

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--chunk',type=int,required=True);ap.add_argument('--chunks',type=int,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    raw=b.load_all(a.data_dir);fac=b.factor_table(raw);frames=b.attach_factor(raw,fac);rules=b.build_rules();selected=[r for i,r in enumerate(rules) if i%a.chunks==a.chunk]
    rows=[];tested=0
    for ri,r in enumerate(selected,1):
        dm={s:q.to_events(r.fn(frames[s],s)) for s in b.TARGETS}
        for sm in q.STOP_GRID:
            for rr in q.RR_GRID:
                tested+=1;ts=[]
                for s in b.TARGETS:
                    x=frames[s];t=q.simulate_config(x,dm[s],sm,rr,q.BASE_COST[s])
                    if t.empty:continue
                    t['symbol']=s;t['stress_r']=t.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*t.atr);ts.append(t)
                if not ts:continue
                t=pd.concat(ts,ignore_index=True).sort_values('signal_time');pre=q.metrics(t[t.year<=2022]);ok,d=q.prehold_pass(t)
                rows.append({'kind':'factor','name':r.name,'family':r.family,'lookback':r.lb,'stop_atr':sm,'rr':rr,
                  **{f'pre_{k}':v for k,v in pre.items()},'pre_stress_mean_r':d['stress_mean_r'],'pre_positive_years_2017_22':d['positive_2017_22'],'pre_max_year_share':d['max_year_share'],'pre_pass':ok,'robust_score':q.robustness_score(t) if ok else -999.0})
        if ri%3==0:print(f'factor chunk {a.chunk}: {ri}/{len(selected)}',flush=True)
    z=pd.DataFrame(rows).sort_values(['pre_pass','robust_score','pre_mean_r'],ascending=[False,False,False]);z.to_csv(a.out/f'v36b_chunk{a.chunk}.csv',index=False)
    m={'chunk':a.chunk,'chunks':a.chunks,'templates':len(selected),'configs_tested':tested,'prehold_survivors':int(z.pre_pass.fillna(False).sum())};(a.out/f'v36b_chunk{a.chunk}.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2));print(z.head(15).to_string(index=False))
if __name__=='__main__':main()
