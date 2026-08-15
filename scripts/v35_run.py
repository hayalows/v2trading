from __future__ import annotations

"""Thin runner for the preregistered V3.5 study.
Keeps the research entrypoint explicit and patches the signal timestamp into the
Trade record from the completed trigger bar before invoking the frozen scanner.
"""
import pandas as pd
import numpy as np
import v35_trend_candle_engine as eng


def make_trade(name,symbol,r,m5,direction,zone,rr,trigger):
    signal_time=pd.Timestamp(r.end)
    start=signal_time
    pos=int(m5.date.searchsorted(start,side="left"))
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
    q=eng.simulate(m5,start,direction,stop,rr)
    if not q: return None
    entry,target,status,gr,gn,exit_time=q
    return eng.Trade(name,symbol,signal_time,start,direction,entry,stop,target,rr,status,gr,gn,exit_time,trigger,zone,signal_time.year,eng.sess(signal_time))

eng.make_trade=make_trade

if __name__=="__main__":
    eng.main()
