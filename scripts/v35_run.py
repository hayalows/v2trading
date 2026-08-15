from __future__ import annotations

"""Efficient runner for the preregistered V3.5 study.
The protocol/rules are unchanged. This runner fixes signal timestamp plumbing and
uses indexed 24-hour M5 simulation windows so the historical scan is reproducible
without repeatedly slicing the full remaining dataset.
"""
import pandas as pd
import numpy as np
import v35_trend_candle_engine as eng


def simulate(m5,start,direction,stop,rr):
    pos=int(m5.date.searchsorted(start,side="left"))
    if pos>=len(m5): return None
    end=int(m5.date.searchsorted(start+pd.Timedelta(hours=24),side="left"))
    end=max(pos+1,min(end,len(m5)))
    entry=float(m5.iloc[pos].open)
    risk=entry-stop if direction=="long" else stop-entry
    if risk<=0: return None
    target=entry+rr*risk if direction=="long" else entry-rr*risk
    q=m5.iloc[pos:end]
    for _,b in q.iterrows():
        hs=float(b.low)<=stop if direction=="long" else float(b.high)>=stop
        ht=float(b.high)>=target if direction=="long" else float(b.low)<=target
        if hs and ht: return entry,target,"ambiguous",-1.0,0.0,pd.Timestamp(b.date)
        if hs: return entry,target,"loss",-1.0,-1.0,pd.Timestamp(b.date)
        if ht: return entry,target,"win",rr,rr,pd.Timestamp(b.date)
    b=q.iloc[-1]
    gr=(float(b.close)-entry)/risk if direction=="long" else (entry-float(b.close))/risk
    return entry,target,"timeout",float(gr),float(gr),pd.Timestamp(b.date)


def make_trade(name,symbol,r,m5,direction,zone,rr,trigger):
    signal_time=pd.Timestamp(r.end)
    pos=int(m5.date.searchsorted(signal_time,side="left"))
    if pos>=len(m5): return None
    entry=float(m5.iloc[pos].open); atr=float(r.atr)
    if name.startswith("CANDLE_ONLY"):
        stop=entry-atr if direction=="long" else entry+atr
    elif direction=="long":
        stop=min(float(r.roll_low8),float(zone) if zone is not None else float(r.roll_low8))-.10*atr
    else:
        stop=max(float(r.roll_high8),float(zone) if zone is not None else float(r.roll_high8))+.10*atr
    risk=entry-stop if direction=="long" else stop-entry
    if not(np.isfinite(atr) and atr>0 and .10*atr<=risk<=2*atr): return None
    q=simulate(m5,signal_time,direction,stop,rr)
    if not q: return None
    entry,target,status,gr,gn,exit_time=q
    return eng.Trade(name,symbol,signal_time,signal_time,direction,entry,stop,target,rr,status,gr,gn,exit_time,trigger,zone,signal_time.year,eng.sess(signal_time))

eng.simulate=simulate
eng.make_trade=make_trade

if __name__=="__main__":
    eng.main()
