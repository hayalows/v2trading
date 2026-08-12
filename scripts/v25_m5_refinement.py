from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
import v19_poi_penetration_research as v19

SYMS=('EURUSD','GBPUSD','XAUUSD'); YEARS=(2022,2023,2024,2025); START=500.0; RISK_PCT=.01; DEPTH=.50

def load(path:Path):
    x=pd.DataFrame(json.loads(path.read_text()));x['date']=pd.to_datetime(x.timestamp,unit='ms',utc=True)
    for c in ['open','high','low','close','volume']:
        if c not in x:x[c]=0
        x[c]=pd.to_numeric(x[c],errors='coerce')
    return x[['date','open','high','low','close','volume']].dropna().drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)

def simulate_m5(m15,m5,s):
    direction=str(s.direction);lo,hi=float(s.poi_low),float(s.poi_high);entry=v19.poi_entry(direction,lo,hi,DEPTH);stop=float(s.stop);atr=float(s.atr);risk=entry-stop if direction=='long' else stop-entry;risk_atr=risk/atr if atr>0 else np.nan;valid=bool(np.isfinite(risk_atr) and risk>0 and v19.MIN_RISK_ATR<=risk_atr<=v19.MAX_RISK_ATR);target=entry+v19.REWARD_R*risk if direction=='long' else entry-v19.REWARD_R*risk;start_i=int(s.bos_i)+1;end_i=min(len(m15),start_i+v19.HORIZON_BARS);start_t=pd.Timestamp(m15.iloc[start_i].date) if start_i<len(m15) else pd.Timestamp(s.bos_time)+pd.Timedelta(minutes=15);end_t=pd.Timestamp(m15.iloc[end_i].date) if end_i<len(m15) else pd.Timestamp(m15.iloc[-1].date)+pd.Timedelta(minutes=15);bars=m5[(m5.date>=start_t)&(m5.date<end_t)];filled=False;fill_time=pd.NaT;out='not_filled';exit_time=pd.NaT
    if valid and len(bars):
        for _,r in bars.iterrows():
            if not filled:
                if float(r.low)<=entry<=float(r.high):
                    filled=True;fill_time=pd.Timestamp(r.date);hs=v19.stop_hit(direction,r,stop);ht=v19.target_hit(direction,r,target)
                    if hs or ht:out='ambiguous_m5_entry';exit_time=pd.Timestamp(r.date);break
                continue
            hs=v19.stop_hit(direction,r,stop);ht=v19.target_hit(direction,r,target)
            if hs and ht:out='ambiguous_m5_exit';exit_time=pd.Timestamp(r.date);break
            if hs:out='loss';exit_time=pd.Timestamp(r.date);break
            if ht:out='win';exit_time=pd.Timestamp(r.date);break
        if filled and out=='not_filled':out='unresolved'
    return {'setup_id':s.setup_id,'symbol':s.symbol,'direction':direction,'year':int(s.year),'bos_time':s.bos_time,'entry':entry,'stop':stop,'target':target,'risk':risk,'risk_atr':risk_atr,'risk_valid':valid,'filled':filled,'fill_time':fill_time,'exit_time':exit_time,'outcome':out}

def account(g,amb_loss=False):
    bal=START;curve=[bal];n=0
    for _,r in g.sort_values('fill_time').iterrows():
        if r.outcome=='win':rr=2.5
        elif r.outcome=='loss':rr=-1
        elif str(r.outcome).startswith('ambiguous') and amb_loss:rr=-1
        else:continue
        bal*=1+RISK_PCT*rr;curve.append(bal);n+=1
    peak=curve[0];dd=0
    for x in curve:peak=max(peak,x);dd=max(dd,(peak-x)/peak if peak else 0)
    return {'ending_balance':round(bal,2),'return_pct':round((bal/START-1)*100,2),'max_drawdown_pct':round(dd*100,2),'trades_counted':n}

def summary(g):
    v=g[g.risk_valid];f=v[v.filled];r=f[f.outcome.isin(['win','loss'])];a=f[f.outcome.astype(str).str.startswith('ambiguous')];w=int((r.outcome=='win').sum());return {'valid_setups':len(v),'fills':len(f),'fill_rate_pct':round(100*len(f)/len(v),2) if len(v) else None,'resolved':len(r),'wins':w,'losses':int((r.outcome=='loss').sum()),'resolved_win_rate_pct':round(100*w/len(r),2) if len(r) else None,'residual_ambiguous':len(a),'residual_ambiguous_rate_filled_pct':round(100*len(a)/len(f),2) if len(f) else None,'unresolved':int((f.outcome=='unresolved').sum()),'clean_account':account(v,False),'residual_ambiguity_stress_account':account(v,True)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);rows=[];meta={}
    for sym in SYMS:
        m15=load(a.data_dir/f'{sym.lower()}-m15.json');m5=load(a.data_dir/f'{sym.lower()}-m5.json');meta[sym]={'m15_rows':len(m15),'m5_rows':len(m5),'m5_from':str(m5.date.min()),'m5_to':str(m5.date.max())};setups=v19.detect_pois(m15,sym);setups=setups[setups.year.isin(YEARS)]
        for _,s in setups.iterrows():rows.append(simulate_m5(m15,m5,s))
    df=pd.DataFrame(rows);result={'study':'V2.5 M5 path-refined common-engine simulation','generated_at':pd.Timestamp.utcnow().isoformat(),'protocol':{'years':'2022-2025 completed years','detector':'M15 V2 structural detector','execution_path':'Dukascopy BID M5 OHLC','entry_depth':.5,'reward_r':2.5,'horizon':'same 192-M15-bar window','start_balance_usd':500,'risk_pct':1,'costs':'excluded','residual_ambiguity':'same M5 bar can still contain entry/SL/TP ordering ambiguity'},'data':meta,'markets':{},'portfolio':summary(df)}
    for s in SYMS:result['markets'][s]=summary(df[df.symbol==s])
    (a.out/'v25-m5-refined.json').write_text(json.dumps(result,indent=2,default=str));df.to_csv(a.out/'v25-m5-trades.csv',index=False);print(json.dumps(result,indent=2,default=str))
if __name__=='__main__':main()
