from __future__ import annotations
import argparse,glob,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

def load_frames(d):
    f={}
    for s in ("EURUSD","GBPUSD"):
        x=q.enrich_single(q.load_duka(d/f"{s.lower()}-m15.json",s));f[s]=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
    return q.add_cross_features(f)

def all_ranks(rdir):
    xs=[];rp=rdir/"v36_rule_grid.csv"
    if rp.exists():xs.append(pd.read_csv(rp))
    for p in sorted(rdir.glob("v36_ml_sm*_rr*.csv")):
        try:xs.append(pd.read_csv(p))
        except:pass
    if not xs:return pd.DataFrame()
    z=pd.concat(xs,ignore_index=True,sort=False)
    if "pre_pass" in z:z["pre_pass"]=z.pre_pass.astype(str).str.lower().eq("true")
    return z.sort_values(["pre_pass","robust_score","pre_mean_r","pre_win_rate"],ascending=[False,False,False,False]).reset_index(drop=True)

def simulate_rule(frames,row):
    rules={r.name:r for r in q.build_rules()};rule=rules[str(row["name"])];ts=[];sm=float(row.stop_atr);rr=float(row.rr)
    for s,df in frames.items():
        d=q.to_events(rule.fn(df));b=q.simulate_config(df,d,sm,rr,q.BASE_COST[s])
        if b.empty:continue
        b["symbol"]=s;b["stress_r"]=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*b.atr);ts.append(b)
    return pd.concat(ts,ignore_index=True).sort_values("signal_time") if ts else pd.DataFrame()

def simulate_ml(frames,row):
    sm=float(row.stop_atr);rr=float(row.rr);th=float(row.threshold);afs=[]
    for s,x in frames.items():
        z=x.copy();z["symbol_code"]=0 if s=="EURUSD" else 1;afs.append(z)
    base=pd.concat(afs,ignore_index=True).sort_values(["date","symbol"]).reset_index(drop=True)
    labs=[]
    for s,x in frames.items():labs.append(pd.DataFrame({"date":x.date,"symbol":s,"y":q.barrier_label(x,sm,rr)}))
    z=base.merge(pd.concat(labs,ignore_index=True),on=["date","symbol"],how="left");feats=q.FEATURES+["symbol_code"];pred=np.full(len(z),np.nan)
    # This is the only selected-model reconstruction that creates 2023-2025 predictions.
    for year in range(2013,2026):
        tr=(z.date.dt.year<=year-1)&(z.date.dt.year>=2005)&z[feats].notna().all(axis=1)&z.y.ne(0);te=(z.date.dt.year==year)&z[feats].notna().all(axis=1)
        if tr.sum()<5000 or te.sum()==0:continue
        m=LGBMClassifier(n_estimators=120,learning_rate=.04,num_leaves=15,max_depth=5,min_child_samples=200,subsample=.8,colsample_bytree=.8,reg_lambda=1.0,random_state=q.SEED,n_jobs=2,verbosity=-1)
        m.fit(z.loc[tr,feats],(z.loc[tr,"y"]>0).astype(int));pred[te]=m.predict_proba(z.loc[te,feats])[:,1]
    z["p_long"]=pred;ts=[]
    for s,df in frames.items():
        qq=z[z.symbol==s][["date","p_long"]].dropna();mp=pd.Series(qq.p_long.to_numpy(),index=qq.date);pv=df.date.map(mp).to_numpy(float)
        d=np.where(pv>=th,1,np.where(pv<=1-th,-1,0)).astype(np.int8);d=q.to_events(d);b=q.simulate_config(df,d,sm,rr,q.BASE_COST[s])
        if b.empty:continue
        b["symbol"]=s;b["stress_r"]=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*b.atr);ts.append(b)
    return pd.concat(ts,ignore_index=True).sort_values("signal_time") if ts else pd.DataFrame()

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",type=Path,required=True);ap.add_argument("--results-dir",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    rank=all_ranks(a.results_dir);rank.to_csv(a.out/"v36_all_candidates.csv",index=False)
    result={"protocol":"V3.6 zero-base parallel frozen","total_configs_tested":int(len(rank)),"prehold_survivors":int(rank.pre_pass.sum()) if len(rank) else 0,"holdout_opened":False}
    if rank.empty or not rank.pre_pass.any():
        result.update({"selected":None,"holdout_status":"REJECT","reason":"No pre-2023 candidate cleared the preregistered gate. Holdout was not used to rescue any rule."})
    else:
        sel=rank[rank.pre_pass].iloc[0].copy();frames=load_frames(a.data_dir)
        t=simulate_rule(frames,sel) if sel.kind=="rule" else simulate_ml(frames,sel)
        status,gate=q.holdout_gate(t);neigh=q.neighborhood_check(rank,sel);t.to_csv(a.out/"v36_selected_trades.csv",index=False)
        selected={k:(v.item() if hasattr(v,"item") else v) for k,v in sel.dropna().to_dict().items()}
        result.update({"selected":selected,"holdout_opened":True,"holdout_status":status,"holdout_gate":gate,"parameter_neighborhood":neigh,
                       "prehold_reconstructed":q.metrics(t[t.year<=2022]),"selected_rr":float(sel.rr),"selected_stop_atr":float(sel.stop_atr)})
        if status=="PROMOTE" and (not np.isfinite(neigh.get("positive_share",np.nan)) or neigh["positive_share"]<.50):
            result["holdout_status"]="WATCHLIST";result["reason"]="Strong holdout metrics but insufficient local parameter stability."
    (a.out/"v36_summary.json").write_text(json.dumps(result,indent=2,default=str));print(json.dumps(result,indent=2,default=str));print(rank.head(30).to_string(index=False))
if __name__=="__main__":main()
