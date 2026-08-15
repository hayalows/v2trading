from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

def load_frames(d):
    f={}
    for s in ('EURUSD','GBPUSD'):
        x=q.enrich_single(q.load_duka(d/f'{s.lower()}-m15.json',s));f[s]=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
    return q.add_cross_features(f)

def c_holdout(t):
    h=t[t.year>=2023];m=q.metrics(h);pair={s:q.metrics(g) for s,g in h.groupby('symbol')};yr=h.groupby('year').net_r.mean();stress=float(h.stress_r.mean()) if len(h) else np.nan;ci=q.block_boot_ci(h,1500,q.SEED+36);mon=h.groupby('month').net_r.sum();share=float(mon.max()/m['sum_r']) if m['sum_r']>0 and len(mon) else np.nan
    watch=(m['n']>=120 and all(s in pair and pair[s]['n']>=40 for s in ('EURUSD','GBPUSD')) and m['win_rate']>=.55 and m['mean_r']>=.05 and m['pf']>=1.10 and all(pair[s]['mean_r']>0 for s in ('EURUSD','GBPUSD')) and int((yr>0).sum())>=2 and stress>=0 and ci[0]>-.02 and (not np.isfinite(share) or share<.50))
    promote=watch and m['win_rate']>=.58 and m['mean_r']>=.10 and m['pf']>=1.20 and stress>=.03 and ci[0]>0
    return ('PROMOTE' if promote else 'WATCHLIST' if watch else 'REJECT'),{'metrics':m,'pair':pair,'positive_years':int((yr>0).sum()),'stress_mean_r':stress,'bootstrap95':ci,'max_month_share':share}

def reconstruct(frames,row):
    sm=float(row.stop_atr);rr=float(row.rr);th=float(row.threshold);vg=float(row.vol_gate);afs=[]
    for s,x in frames.items():z=x.copy();z['symbol_code']=0 if s=='EURUSD' else 1;afs.append(z)
    base=pd.concat(afs,ignore_index=True).sort_values(['date','symbol']).reset_index(drop=True);labs=[]
    for s,x in frames.items():labs.append(pd.DataFrame({'date':x.date,'symbol':s,'y':q.barrier_label(x,sm,rr)}))
    z=base.merge(pd.concat(labs,ignore_index=True),on=['date','symbol'],how='left');feats=q.FEATURES+['symbol_code'];pred=np.full(len(z),np.nan)
    # Only the single selected prehold configuration receives final-holdout predictions.
    for year in range(2013,2026):
        tr=(z.date.dt.year<=year-1)&(z.date.dt.year>=2005)&z[feats].notna().all(axis=1)&z.y.ne(0);te=(z.date.dt.year==year)&z[feats].notna().all(axis=1)
        if tr.sum()<5000 or te.sum()==0:continue
        m=LGBMClassifier(n_estimators=120,learning_rate=.04,num_leaves=15,max_depth=5,min_child_samples=200,subsample=.8,colsample_bytree=.8,reg_lambda=1.0,random_state=q.SEED,n_jobs=2,verbosity=-1);m.fit(z.loc[tr,feats],(z.loc[tr,'y']>0).astype(int));pred[te]=m.predict_proba(z.loc[te,feats])[:,1]
    z['p_long']=pred;ts=[]
    for s,df in frames.items():
        qq=z[z.symbol==s][['date','p_long']].dropna();mp=pd.Series(qq.p_long.to_numpy(),index=qq.date);pv=df.date.map(mp).to_numpy(float)
        bc=(q.BASE_COST[s]*q.PIP)/(sm*df.atr14.to_numpy(float));sc=(q.STRESS_COST[s]*q.PIP)/(sm*df.atr14.to_numpy(float));eligible=(bc<=.08)&(sc<=.15)&(df.atr_pctile20d.to_numpy(float)>=vg)
        d=np.where(eligible&(pv>=th),1,np.where(eligible&(pv<=1-th),-1,0)).astype(np.int8);d=q.to_events(d);b=q.simulate_config(df,d,sm,rr,q.BASE_COST[s])
        if b.empty:continue
        b['symbol']=s;b['stress_r']=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*b.atr);ts.append(b)
    return pd.concat(ts,ignore_index=True).sort_values('signal_time') if ts else pd.DataFrame()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--results-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    ps=sorted(a.results_dir.glob('v36c_sm*_rr*.csv'));rank=pd.concat([pd.read_csv(p) for p in ps],ignore_index=True);rank['pre_pass']=rank.pre_pass.astype(str).str.lower().eq('true');rank=rank.sort_values(['pre_pass','robust_score','pre_stress_mean_r','pre_mean_r'],ascending=[False,False,False,False]).reset_index(drop=True);rank.to_csv(a.out/'v36c_all_candidates.csv',index=False)
    res={'protocol':'V3.6C cost-aware ML frozen','configs_tested':int(len(rank)),'prehold_survivors':int(rank.pre_pass.sum()),'holdout_opened':False}
    if not rank.pre_pass.any():res.update({'selected':None,'holdout_status':'REJECT','reason':'No cost-aware ML candidate cleared the stricter pre-2023 gate; holdout remained unopened.'})
    else:
        sel=rank[rank.pre_pass].iloc[0];frames=load_frames(a.data_dir);t=reconstruct(frames,sel);status,gate=c_holdout(t);t.to_csv(a.out/'v36c_selected_trades.csv',index=False);res.update({'selected':{k:(v.item() if hasattr(v,'item') else v) for k,v in sel.dropna().to_dict().items()},'holdout_opened':True,'holdout_status':status,'holdout_gate':gate,'prehold_reconstructed':q.metrics(t[t.year<=2022])})
    (a.out/'v36c_summary.json').write_text(json.dumps(res,indent=2,default=str));print(json.dumps(res,indent=2,default=str));print(rank.head(30).to_string(index=False))
if __name__=='__main__':main()
