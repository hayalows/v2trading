from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

def load_frames(data_dir):
    frames={}
    for s in ("EURUSD","GBPUSD"):
        x=q.enrich_single(q.load_duka(data_dir/f"{s.lower()}-m15.json",s))
        frames[s]=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
    return q.add_cross_features(frames)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);ap.add_argument("--chunk",type=int,required=True);ap.add_argument("--chunks",type=int,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    frames=load_frames(a.data_dir);rules=q.build_rules();selected=[r for i,r in enumerate(rules) if i%a.chunks==a.chunk]
    rows=[];tested=0
    for ri,rule in enumerate(selected,1):
        dm={s:q.to_events(rule.fn(df)) for s,df in frames.items()}
        for sm in q.STOP_GRID:
            for rr in q.RR_GRID:
                tested+=1;ts=[]
                for s,df in frames.items():
                    b=q.simulate_config(df,dm[s],sm,rr,q.BASE_COST[s])
                    if b.empty:continue
                    b["symbol"]=s;b["stress_r"]=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*b.atr);ts.append(b)
                if not ts:continue
                t=pd.concat(ts,ignore_index=True).sort_values("signal_time");pre=q.metrics(t[t.year<=2022]);ok,d=q.prehold_pass(t)
                rows.append({"kind":"rule","name":rule.name,"family":rule.family,"stop_atr":sm,"rr":rr,
                    **{f"pre_{k}":v for k,v in pre.items()},"pre_stress_mean_r":d["stress_mean_r"],"pre_positive_years_2017_22":d["positive_2017_22"],"pre_max_year_share":d["max_year_share"],"pre_pass":ok,"robust_score":q.robustness_score(t) if ok else -999.0})
        if ri%3==0:print(f"chunk {a.chunk}: {ri}/{len(selected)} templates",flush=True)
    out=pd.DataFrame(rows).sort_values(["pre_pass","robust_score","pre_mean_r"],ascending=[False,False,False])
    out.to_csv(a.out/f"v36_rules_chunk{a.chunk}.csv",index=False)
    meta={"chunk":a.chunk,"chunks":a.chunks,"templates":len(selected),"configs_tested":tested,"prehold_survivors":int(out.pre_pass.fillna(False).sum())}
    (a.out/f"v36_rules_chunk{a.chunk}.json").write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2));print(out.head(15).to_string(index=False))
if __name__=="__main__":main()
