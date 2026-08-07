from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from public_data_v2_proxy import load_market

NAMES={0:'NO_SETUP',1:'LIQUIDITY_NEARBY',2:'POI_USED',3:'SWEEP_CONFIRMED',4:'WAITING_FOR_BOS',5:'BOS_CONFIRMED',6:'FRESH_POI_IDENTIFIED',7:'APPROACHING_POI',8:'ENTRY_ZONE_REACHED'}

def formation_np(w):
    n=len(w)
    if n<45:return 0,None
    o=w[:,0];h=w[:,1];l=w[:,2];c=w[:,3]
    prev=np.r_[c[0],c[:-1]]
    tr=np.maximum(h-l,np.maximum(np.abs(h-prev),np.abs(l-prev)))
    def atr(i): return float(tr[max(0,i-13):i+1].mean())
    a=max(atr(n-1),abs(c[-1])*1e-5); ref=float(c[-1]); sweep_i=-1;direction=None
    for i in range(max(22,n-12),n):
        ph=float(h[i-20:i].max());pl=float(l[i-20:i].min());ai=max(atr(i),a)
        bear=h[i]>ph+.03*ai and c[i]<ph;bull=l[i]<pl-.03*ai and c[i]>pl
        if bear or bull:sweep_i=i;direction='short' if bear else 'long'
    if sweep_i<0:
        hs=[];ls=[];start=max(0,n-60)
        for i in range(max(start+2,2),n-2):
            if h[i]>h[i-1] and h[i]>=h[i-2] and h[i]>h[i+1] and h[i]>=h[i+2]:hs.append(float(h[i]))
            if l[i]<l[i-1] and l[i]<=l[i-2] and l[i]<l[i+1] and l[i]<=l[i+2]:ls.append(float(l[i]))
        hi=hs[-1] if hs else float(h[-20:].max());lo=ls[-1] if ls else float(l[-20:].min());dh=abs(ref-hi)/a;dl=abs(ref-lo)/a
        return (1,'long' if dl<dh else 'short') if min(dh,dl)<=.35 else (0,None)
    pre0=max(0,sweep_i-8)
    if pre0==sweep_i:return 3,direction
    bos_high=float(h[pre0:sweep_i].max());bos_low=float(l[pre0:sweep_i].min());bos=-1
    for i in range(sweep_i+1,n):
        if (direction=='long' and c[i]>bos_high) or (direction=='short' and c[i]<bos_low):bos=i;break
    if bos<0:return (4 if n-1-sweep_i>=1 else 3),direction
    poi=-1
    for i in range(bos,sweep_i-1,-1):
        if (direction=='long' and c[i]<o[i]) or (direction=='short' and c[i]>o[i]):poi=i;break
    if poi<0:return 5,direction
    ph=float(h[poi]);pl=float(l[poi]);mid=(ph+pl)/2;dist=abs(ref-mid)/a;inside=pl<=ref<=ph;touched=False
    if bos+1<n-1:
        touched=bool(np.any((l[bos+1:n-1]<=ph)&(h[bos+1:n-1]>=pl)))
    if touched and not inside:return 2,direction
    if inside:return 8,direction
    if dist<=.5:return 7,direction
    return 6,direction

def replay(df,symbol):
    x=df[['open','high','low','close']].to_numpy(float);times=pd.to_datetime(df.date,utc=True);rows=[]
    for i in range(80,len(df)):
        start=max(0,i-119);stage,direction=formation_np(x[start:i+1]);rows.append((symbol,i,times.iloc[i],float(x[i,3]),stage,direction,NAMES[stage]))
    return pd.DataFrame(rows,columns=['symbol','bar_i','time','close','stage','direction','code'])

def episodes(s,horizon=32):
    s=s.reset_index(drop=True);rows=[];i=0
    while i<len(s):
        r=s.iloc[i]
        if int(r.stage)<3 or int(r.stage)==8 or r.direction not in {'long','short'}:i+=1;continue
        end=min(len(s)-1,i+horizon);hit=None;mx=int(r.stage)
        for j in range(i+1,end+1):
            rr=s.iloc[j]
            if rr.direction==r.direction:
                mx=max(mx,int(rr.stage))
                if int(rr.stage)==8:hit=j;break
        rows.append((r.symbol,r.time,int(r.stage),r.direction,hit is not None,s.iloc[hit].time if hit is not None else pd.NaT,(hit-i)*15 if hit is not None else np.nan,mx))
        i=hit+1 if hit is not None else end+1
    return pd.DataFrame(rows,columns=['symbol','start_time','start_stage','direction','converted_to_stage8','entry_time','lead_minutes','max_stage'])

def recall(s,lookback=32):
    s=s.reset_index(drop=True);idx=np.where(s.stage.to_numpy(int)==8)[0];uniq=[]
    for i in idx:
        if not uniq or i-uniq[-1]>1:uniq.append(int(i))
    caught=0;leads=[]
    for i in uniq:
        p=s.iloc[max(0,i-lookback):i];m=p[(p.direction==s.iloc[i].direction)&(p.stage>=3)&(p.stage<8)]
        if len(m):caught+=1;leads.append((i-int(m.index[0]))*15)
    return len(uniq),caught,float(np.median(leads)) if leads else None

def summary(s,e):
    ue,c,lead=recall(s);d={'bars_replayed':len(s),'unique_stage8_entries':ue,'entries_with_prior_stage3plus':c,'entry_recall':c/ue if ue else None,'median_warning_minutes':lead,'candidate_thresholds':{}}
    for t in [3,4,5,6,7]:
        z=e[e.start_stage>=t];d['candidate_thresholds'][str(t)]={'episodes':len(z),'converted':int(z.converted_to_stage8.sum()) if len(z) else 0,'conversion_rate':float(z.converted_to_stage8.mean()) if len(z) else None,'median_lead_minutes':float(z.loc[z.converted_to_stage8,'lead_minutes'].median()) if len(z) and z.converted_to_stage8.any() else None}
    return d

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--start',default='2023-01-01');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);ss=[];ee=[];by={}
    for sym in ['EURUSD','GBPUSD']:
        df=load_market(a.data_dir/f'{sym}-15m.feather',sym);df=df[df.date>=pd.Timestamp(a.start,tz='UTC')].reset_index(drop=True);s=replay(df,sym);e=episodes(s);ss.append(s);ee.append(e);by[sym]=summary(s,e)
    s=pd.concat(ss,ignore_index=True);e=pd.concat(ee,ignore_index=True);s.to_csv(a.out/'prospective_states.csv',index=False);e.to_csv(a.out/'formation_episodes.csv',index=False)
    ue=sum(v['unique_stage8_entries'] for v in by.values());caught=sum(v['entries_with_prior_stage3plus'] for v in by.values());result={'version':'v0.6 prospective detector validation','symbols':by,'pooled':{'bars_replayed':len(s),'episodes':len(e),'converted':int(e.converted_to_stage8.sum()),'episode_conversion_rate':float(e.converted_to_stage8.mean()) if len(e) else None,'unique_stage8_entries':ue,'entries_with_prior_stage3plus':caught,'entry_recall':caught/ue if ue else None},'note':'Formation conversion only; not profitability or execution.'};(a.out/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
