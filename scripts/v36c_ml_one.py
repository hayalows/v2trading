from __future__ import annotations
import argparse,sys
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

VOL_GATES=(0.0,0.40,0.60)
PROB_GATES=(0.60,0.65,0.70)

def load_frames(data_dir):
    f={}
    for s in ("EURUSD","GBPUSD"):
        x=q.enrich_single(q.load_duka(data_dir/f"{s.lower()}-m15.json",s))
        f[s]=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
    return q.add_cross_features(f)

def c_gate(t:pd.DataFrame):
    p=t[t.year<=2022]
    m=q.metrics(p); pair={s:q.metrics(g) for s,g in p.groupby('symbol')}
    y=p[p.year.between(2017,2022)].groupby('year').net_r.mean()
    total=m['sum_r']; share=0.0
    if total>0 and len(p):
        annual=p.groupby('year').net_r.sum(); share=float(annual.max()/total)
    stress=float(p.stress_r.mean()) if len(p) else np.nan
    ok=(m['n']>=300 and all(s in pair and pair[s]['n']>=100 for s in ('EURUSD','GBPUSD')) and
        m['mean_r']>=.04 and m['pf']>=1.10 and m['win_rate']>=.55 and
        all(pair[s]['mean_r']>0 for s in ('EURUSD','GBPUSD')) and int((y>0).sum())>=4 and stress>=0 and share<=.45)
    return ok,{'pre':m,'pair':pair,'positive_2017_22':int((y>0).sum()),'stress_mean_r':stress,'max_year_share':share}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--sm',type=float,required=True);ap.add_argument('--rr',type=float,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    frames=load_frames(a.data_dir);allframes=[]
    for s,x in frames.items():
        z=x.copy();z['symbol_code']=0 if s=='EURUSD' else 1;allframes.append(z)
    base=pd.concat(allframes,ignore_index=True).sort_values(['date','symbol']).reset_index(drop=True)
    labs=[]
    for s,x in frames.items():labs.append(pd.DataFrame({'date':x.date,'symbol':s,'y':q.barrier_label(x,a.sm,a.rr)}))
    z=base.merge(pd.concat(labs,ignore_index=True),on=['date','symbol'],how='left');feats=q.FEATURES+['symbol_code'];pred=np.full(len(z),np.nan)
    # Selection workers explicitly stop at 2022; no holdout prediction is made here.
    for year in range(2013,2023):
        tr=(z.date.dt.year<=year-1)&(z.date.dt.year>=2005)&z[feats].notna().all(axis=1)&z.y.ne(0)
        te=(z.date.dt.year==year)&z[feats].notna().all(axis=1)
        if tr.sum()<5000 or te.sum()==0:continue
        m=LGBMClassifier(n_estimators=120,learning_rate=.04,num_leaves=15,max_depth=5,min_child_samples=200,subsample=.8,colsample_bytree=.8,reg_lambda=1.0,random_state=q.SEED,n_jobs=2,verbosity=-1)
        m.fit(z.loc[tr,feats],(z.loc[tr,'y']>0).astype(int));pred[te]=m.predict_proba(z.loc[te,feats])[:,1]
    z['p_long']=pred;rows=[]
    for th in PROB_GATES:
      for vg in VOL_GATES:
        ts=[]
        for s,df in frames.items():
            qq=z[z.symbol==s][['date','p_long']].dropna();mp=pd.Series(qq.p_long.to_numpy(),index=qq.date);pv=df.date.map(mp).to_numpy(float)
            base_cost_r=(q.BASE_COST[s]*q.PIP)/(a.sm*df.atr14.to_numpy(float));stress_cost_r=(q.STRESS_COST[s]*q.PIP)/(a.sm*df.atr14.to_numpy(float))
            eligible=(base_cost_r<=.08)&(stress_cost_r<=.15)&(df.atr_pctile20d.to_numpy(float)>=vg)
            d=np.where(eligible&(pv>=th),1,np.where(eligible&(pv<=1-th),-1,0)).astype(np.int8);d=q.to_events(d)
            b=q.simulate_config(df,d,a.sm,a.rr,q.BASE_COST[s])
            if b.empty:continue
            b['symbol']=s;b['stress_r']=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(a.sm*b.atr);ts.append(b)
        if not ts:continue
        t=pd.concat(ts,ignore_index=True).sort_values('signal_time');ok,g=c_gate(t);pre=g['pre']
        name=f"C_LGBM_sm{a.sm:g}_rr{a.rr:g}_p{th:g}_v{vg:g}"
        # Ranking has no holdout data: stress margin + baseline expectancy + PF + WR + sample support.
        annual=t[(t.year>=2017)&(t.year<=2022)].groupby('year').net_r.mean()
        robust=float((annual.median() if len(annual) else -9)+.60*g['stress_mean_r']+.15*pre['mean_r']+.05*(pre['pf']-1)+.03*(pre['win_rate']-.55)+.002*np.log1p(pre['n'])) if ok else -999.0
        rows.append({'kind':'ml_cost_aware','name':name,'family':'cost_aware_ml','stop_atr':a.sm,'rr':a.rr,'threshold':th,'vol_gate':vg,
          **{f'pre_{k}':v for k,v in pre.items()},'pre_stress_mean_r':g['stress_mean_r'],'pre_positive_years_2017_22':g['positive_2017_22'],'pre_max_year_share':g['max_year_share'],
          'eur_mean_r':g['pair'].get('EURUSD',{}).get('mean_r',np.nan),'gbp_mean_r':g['pair'].get('GBPUSD',{}).get('mean_r',np.nan),'pre_pass':ok,'robust_score':robust})
    out=pd.DataFrame(rows);out.to_csv(a.out/f'v36c_sm{a.sm:g}_rr{a.rr:g}.csv',index=False);print(out.sort_values(['pre_pass','robust_score','pre_mean_r'],ascending=[False,False,False]).to_string(index=False))
if __name__=='__main__':main()
