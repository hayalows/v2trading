from __future__ import annotations
import argparse,sys
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

def load_frames(data_dir):
    f={}
    for s in ("EURUSD","GBPUSD"):
        x=q.enrich_single(q.load_duka(data_dir/f"{s.lower()}-m15.json",s))
        f[s]=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
    return q.add_cross_features(f)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);ap.add_argument("--sm",type=float,required=True);ap.add_argument("--rr",type=float,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    frames=load_frames(a.data_dir);allframes=[]
    for s,x in frames.items():
        z=x.copy();z["symbol_code"]=0 if s=="EURUSD" else 1;allframes.append(z)
    base=pd.concat(allframes,ignore_index=True).sort_values(["date","symbol"]).reset_index(drop=True)
    pieces=[]
    for s,x in frames.items(): pieces.append(pd.DataFrame({"date":x.date,"symbol":s,"y":q.barrier_label(x,a.sm,a.rr)}))
    z=base.merge(pd.concat(pieces,ignore_index=True),on=["date","symbol"],how="left")
    feats=q.FEATURES+["symbol_code"];preds=np.full(len(z),np.nan)
    # Deliberately stops at 2022: no final-holdout prediction is created in model-selection workers.
    for year in range(2013,2023):
        tr=(z.date.dt.year<=year-1)&(z.date.dt.year>=2005)&z[feats].notna().all(axis=1)&z.y.ne(0)
        te=(z.date.dt.year==year)&z[feats].notna().all(axis=1)
        if tr.sum()<5000 or te.sum()==0:continue
        model=LGBMClassifier(n_estimators=120,learning_rate=.04,num_leaves=15,max_depth=5,min_child_samples=200,subsample=.8,colsample_bytree=.8,reg_lambda=1.0,random_state=q.SEED,n_jobs=2,verbosity=-1)
        model.fit(z.loc[tr,feats],(z.loc[tr,"y"]>0).astype(int));preds[te]=model.predict_proba(z.loc[te,feats])[:,1]
    z["p_long"]=preds;rows=[]
    for th in (.55,.60,.65,.70):
        ts=[]
        for s,df in frames.items():
            qq=z[z.symbol==s][["date","p_long"]].dropna();pmap=pd.Series(qq.p_long.to_numpy(),index=qq.date);pv=df.date.map(pmap).to_numpy(float)
            d=np.where(pv>=th,1,np.where(pv<=1-th,-1,0)).astype(np.int8);d=q.to_events(d)
            b=q.simulate_config(df,d,a.sm,a.rr,q.BASE_COST[s])
            if b.empty:continue
            b["symbol"]=s;b["stress_r"]=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(a.sm*b.atr);ts.append(b)
        if not ts:continue
        t=pd.concat(ts,ignore_index=True).sort_values("signal_time");pre=q.metrics(t[t.year<=2022]);ok,det=q.prehold_pass(t)
        rows.append({"kind":"ml","name":f"ML_LGBM_sm{a.sm:g}_rr{a.rr:g}_p{th:g}","family":"ml_meta","stop_atr":a.sm,"rr":a.rr,"threshold":th,
                     **{f"pre_{k}":v for k,v in pre.items()},"pre_stress_mean_r":det["stress_mean_r"],"pre_positive_years_2017_22":det["positive_2017_22"],"pre_max_year_share":det["max_year_share"],"pre_pass":ok,"robust_score":q.robustness_score(t) if ok else -999.0})
    out=pd.DataFrame(rows);name=f"v36_ml_sm{a.sm:g}_rr{a.rr:g}.csv";out.to_csv(a.out/name,index=False);print(out.to_string(index=False))
if __name__=="__main__":main()
