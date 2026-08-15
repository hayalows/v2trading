from __future__ import annotations
"""Execution accelerator for the frozen V3.6 study.
It imports v36_zero_base_quant and replaces only the repeated path simulator with
an outcome cache. Signal definitions, partitions, costs, stops, targets, ML,
and promotion gates remain in the preregistered module unchanged.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant as q

_CACHE={}

def _precompute(df:pd.DataFrame,sm:float,rr:float,cost_pips:float,horizon:int):
    key=(id(df),float(sm),float(rr),float(cost_pips),int(horizon))
    if key in _CACHE:return _CACHE[key]
    n=len(df); maxsig=n-horizon-2
    atr=df.atr14.to_numpy(float); op=df.open.to_numpy(float); hi=df.high.to_numpy(float); lo=df.low.to_numpy(float); cl=df.close.to_numpy(float)
    sig=np.arange(maxsig+1,dtype=np.int32); entry_i=sig+1
    valid=np.isfinite(atr[sig])&np.isfinite(op[entry_i])&(atr[sig]>0)
    vs=sig[valid]; ei=entry_i[valid]; a=atr[vs]; entry=op[ei]; risk=sm*a
    offsets=np.arange(horizon,dtype=np.int32)
    mat=ei[:,None]+offsets[None,:]
    highs=hi[mat]; lows=lo[mat]
    result={"valid":valid,"sig":vs}
    for d in (1,-1):
        target=entry+d*rr*risk; stop=entry-d*risk
        if d==1:
            ht=highs>=target[:,None]; hs=lows<=stop[:,None]
        else:
            ht=lows<=target[:,None]; hs=highs>=stop[:,None]
        at=ht.any(1); ass=hs.any(1)
        ft=np.where(at,ht.argmax(1),horizon+1); fs=np.where(ass,hs.argmax(1),horizon+1)
        win=at&(ft<fs); loss=ass&(fs<=ft)
        off=np.minimum(ft,fs); unresolved=~(win|loss); off=np.where(unresolved,horizon-1,off).astype(np.int32)
        exit_i=ei+off
        gross=np.where(win,rr,np.where(loss,-1,d*(cl[exit_i]-entry)/risk)).astype(np.float32)
        cost=((cost_pips*q.PIP)/risk).astype(np.float32)
        net=(gross-cost).astype(np.float32)
        status=np.where(win,1,np.where(loss,-1,0)).astype(np.int8)
        result[d]={"exit":exit_i.astype(np.int32),"gross":gross,"net":net,"status":status}
    result["entry_i"]=ei.astype(np.int32); result["entry"]=entry; result["atr"]=a; result["risk"]=risk
    _CACHE[key]=result
    print(f"cached outcome path sm={sm:g} rr={rr:g} cost={cost_pips:g} rows={len(vs):,}",flush=True)
    return result

def fast_simulate(df:pd.DataFrame,direction:np.ndarray,stop_mult:float,rr:float,cost_pips:float,horizon:int=q.HORIZON)->pd.DataFrame:
    pc=_precompute(df,stop_mult,rr,cost_pips,horizon)
    ev=np.flatnonzero(direction!=0).astype(np.int32)
    if not len(ev):return pd.DataFrame()
    # valid signal indices are contiguous from 0..maxsig; map signal index directly then verify ATR validity.
    pos=np.searchsorted(pc["sig"],ev)
    ok=(pos<len(pc["sig"]))
    pos2=np.minimum(pos,len(pc["sig"])-1)
    ok &= pc["sig"][pos2]==ev
    ev=ev[ok]; pos=pos[ok]
    if not len(ev):return pd.DataFrame()
    dirs=direction[ev].astype(np.int8)
    chosen=[]; last_exit=-1
    for j,(si,di,pi) in enumerate(zip(ev,dirs,pos)):
        ex=int(pc[int(di)]["exit"][pi])
        if int(si)>last_exit:
            chosen.append(j); last_exit=ex
    if not chosen:return pd.DataFrame()
    jj=np.asarray(chosen,dtype=np.int32); ev=ev[jj]; pos=pos[jj]; dirs=dirs[jj]
    ei=pc["entry_i"][pos]; entry=pc["entry"][pos]; atr=pc["atr"][pos]; risk=pc["risk"][pos]
    exit_i=np.empty(len(jj),dtype=np.int32); gross=np.empty(len(jj)); net=np.empty(len(jj)); st=np.empty(len(jj),dtype=np.int8)
    for d in (1,-1):
        m=dirs==d
        if m.any():
            z=pc[d]; exit_i[m]=z["exit"][pos[m]]; gross[m]=z["gross"][pos[m]]; net[m]=z["net"][pos[m]]; st[m]=z["status"][pos[m]]
    stop=entry-dirs*risk; target=entry+dirs*rr*risk
    status=np.where(st==1,"win",np.where(st==-1,"loss","timeout"))
    dt=df.date.to_numpy()
    return pd.DataFrame({
        "signal_idx":ev,"signal_time":dt[ev],"entry_time":dt[ei],"exit_time":dt[exit_i],"direction":dirs,
        "entry":entry,"stop":stop,"target":target,"gross_r":gross,"cost_r":gross-net,"net_r":net,"status":status,
        "year":pd.DatetimeIndex(dt[ev]).year,"month":pd.DatetimeIndex(dt[ev]).to_period("M").astype(str),
        "hour":pd.DatetimeIndex(dt[ev]).hour,"atr":atr
    })

q.simulate_config=fast_simulate

if __name__=="__main__":
    q.main()
