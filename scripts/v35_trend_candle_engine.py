from __future__ import annotations

"""V3.5 standalone trend/support-resistance/candlestick challenger.
Research-only. Generates its own trades from public M5 OHLC and does not depend
on V2 sweep/BOS/POI setups. Rules are frozen in V35_TREND_CANDLE_ENGINE_PROTOCOL.md.
"""
import argparse,json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

SYMBOLS=("EURUSD","GBPUSD"); YEARS=(2022,2023,2024,2025); PIP=.0001; BOOT_REPS=2000; SEED=3501

def load_market(path:Path)->pd.DataFrame:
    df=pd.read_feather(path); cols={str(c).lower():c for c in df.columns}; tcol=cols.get("date") or cols.get("datetime") or cols.get("timestamp") or cols.get("time")
    if tcol is None: raise ValueError(f"{path}: no time column")
    ren={tcol:"date"}
    for k in ("open","high","low","close"):
        if k not in cols: raise ValueError(f"{path}: missing {k}")
        ren[cols[k]]=k
    x=df.rename(columns=ren)[["date","open","high","low","close"]].copy(); x.date=pd.to_datetime(x.date,utc=True)
    for c in ("open","high","low","close"): x[c]=pd.to_numeric(x[c],errors="coerce")
    return x.dropna().sort_values("date").drop_duplicates("date").query("open>0 and high>=low and low>0 and close>0").reset_index(drop=True)

def resample(df,rule,minutes):
    y=(df.set_index("date").resample(rule,label="left",closed="left").agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last")).dropna().reset_index()); y["end"]=y.date+pd.Timedelta(minutes=minutes); return y

def tr(df):
    pc=df.close.shift(1); return pd.concat([(df.high-df.low),(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)

def basic(df):
    x=df.copy(); x["atr"]=tr(x).rolling(14,min_periods=14).mean(); x["ema20"]=x.close.ewm(span=20,adjust=False).mean(); x["ema50"]=x.close.ewm(span=50,adjust=False).mean(); x["ema_label"]=np.where((x.close>x.ema20)&(x.ema20>x.ema50),"bullish",np.where((x.close<x.ema20)&(x.ema20<x.ema50),"bearish","mixed")); x["ema_slope20"]=x.ema20-x.ema20.shift(20); return x

def structure(df,left=2,right=2):
    x=df.copy(); n=len(x); H=x.high.to_numpy(float); L=x.low.to_numpy(float); he={}; le={}
    for i in range(left,n-right):
        if H[i]>np.max(H[i-left:i]) and H[i]>=np.max(H[i+1:i+right+1]): he.setdefault(i+right,[]).append((i,float(H[i])))
        if L[i]<np.min(L[i-left:i]) and L[i]<=np.min(L[i+1:i+right+1]): le.setdefault(i+right,[]).append((i,float(L[i])))
    hs=[]; ls=[]; labs=[]; h1=[]; h2=[]; l1=[]; l2=[]; hi=[]; li=[]
    for j in range(n):
        hs.extend(he.get(j,[])); ls.extend(le.get(j,[])); lab="mixed"
        if len(hs)>=2 and len(ls)>=2:
            bull=hs[-1][1]>hs[-2][1] and ls[-1][1]>ls[-2][1]; bear=hs[-1][1]<hs[-2][1] and ls[-1][1]<ls[-2][1]; lab="bullish" if bull else "bearish" if bear else "mixed"
        labs.append(lab); h1.append(hs[-1][1] if hs else np.nan); h2.append(hs[-2][1] if len(hs)>=2 else np.nan); l1.append(ls[-1][1] if ls else np.nan); l2.append(ls[-2][1] if len(ls)>=2 else np.nan); hi.append(hs[-1][0] if hs else -1); li.append(ls[-1][0] if ls else -1)
    x["structure"]=labs; x["pivot_high1"]=h1; x["pivot_high2"]=h2; x["pivot_low1"]=l1; x["pivot_low2"]=l2; x["pivot_high_idx"]=hi; x["pivot_low_idx"]=li; return x

def h4_extra(h4):
    x=h4.copy(); seen_h=[]; seen_l=[]; eqh=[]; eql=[]; ph=-2; pl=-2
    for _,r in x.iterrows():
        if np.isfinite(r.pivot_high1) and int(r.pivot_high_idx)>=0 and int(r.pivot_high_idx)!=ph: seen_h.append(float(r.pivot_high1)); ph=int(r.pivot_high_idx)
        if np.isfinite(r.pivot_low1) and int(r.pivot_low_idx)>=0 and int(r.pivot_low_idx)!=pl: seen_l.append(float(r.pivot_low1)); pl=int(r.pivot_low_idx)
        tol=max(.15*float(r.atr) if np.isfinite(r.atr) else 0,2*PIP)
        def cluster(vals):
            out=np.nan; z=vals[-8:]
            for i in range(len(z)):
                for j in range(i+1,len(z)):
                    if abs(z[i]-z[j])<=tol: out=(z[i]+z[j])/2
            return out
        eqh.append(cluster(seen_h)); eql.append(cluster(seen_l))
    x["equal_high"]=eqh; x["equal_low"]=eql; x["impulse_low"]=x.pivot_low1; x["impulse_high"]=x.pivot_high1; x["impulse_low_idx"]=x.pivot_low_idx; x["impulse_high_idx"]=x.pivot_high_idx; return x

def candles(m):
    x=m.copy(); rng=(x.high-x.low).replace(0,np.nan); body=(x.close-x.open).abs(); x["body_ratio"]=body/rng; x["upper_ratio"]=(x.high-x[["open","close"]].max(axis=1))/rng; x["lower_ratio"]=(x[["open","close"]].min(axis=1)-x.low)/rng; po=x.open.shift(1); pc=x.close.shift(1)
    x["bull_engulf"]=(pc<po)&(x.close>x.open)&(x.open<=pc)&(x.close>=po); x["bear_engulf"]=(pc>po)&(x.close<x.open)&(x.open>=pc)&(x.close<=po); x["hammer"]=(x.close>x.open)&(x.lower_ratio>=.45)&(x.lower_ratio>=1.8*x.body_ratio); x["shooting"]=(x.close<x.open)&(x.upper_ratio>=.45)&(x.upper_ratio>=1.8*x.body_ratio); pos=(x.close-x.low)/rng; x["strong_bull"]=(x.close>x.open)&(x.body_ratio>=.60)&(pos>=.75); x["strong_bear"]=(x.close<x.open)&(x.body_ratio>=.60)&(pos<=.25); x["doji"]=x.body_ratio<=.12; x["bull_trigger"]=x.bull_engulf|x.hammer|x.strong_bull; x["bear_trigger"]=x.bear_engulf|x.shooting|x.strong_bear; x["trigger_name_long"]=np.select([x.bull_engulf,x.hammer,x.strong_bull],["engulfing","rejection","strong_body"],default="none"); x["trigger_name_short"]=np.select([x.bear_engulf,x.shooting,x.strong_bear],["engulfing","rejection","strong_body"],default="none"); x["roll_low8"]=x.low.rolling(8,min_periods=3).min(); x["roll_high8"]=x.high.rolling(8,min_periods=3).max(); return x

def periods(m15):
    z=m15.copy().set_index("date"); d=z.resample("1D").agg(high=("high","max"),low=("low","min")).shift(1).rename(columns={"high":"prev_day_high","low":"prev_day_low"}); w=z.resample("W-MON").agg(high=("high","max"),low=("low","min")).shift(1).rename(columns={"high":"prev_week_high","low":"prev_week_low"}); out=z.reset_index()
    for p in (d,w):
        q=p.reset_index().rename(columns={"date":"period_date"}); out=pd.merge_asof(out.sort_values("date"),q.sort_values("period_date"),left_on="date",right_on="period_date",direction="backward").drop(columns=["period_date"])
    return out

def context(m15,h1,h4,d1):
    x=m15.sort_values("end").copy()
    def merge(f,p,cols):
        nonlocal x; q=f[["end"]+cols].rename(columns={c:f"{p}_{c}" for c in cols}); x=pd.merge_asof(x.sort_values("end"),q.sort_values("end"),on="end",direction="backward")
    merge(h1,"h1",["atr","structure","ema_label","pivot_high1","pivot_low1"]); merge(h4,"h4",["atr","structure","ema_label","ema_slope20","pivot_high1","pivot_high2","pivot_low1","pivot_low2","equal_high","equal_low","impulse_low","impulse_high","impulse_low_idx","impulse_high_idx"]); merge(d1,"d1",["atr","structure","ema_label","pivot_high1","pivot_low1"]); return x

def levels(r):
    out=[]
    for n in ("h4_pivot_high1","h4_pivot_high2","h4_pivot_low1","h4_pivot_low2","d1_pivot_high1","d1_pivot_low1","prev_day_high","prev_day_low","prev_week_high","prev_week_low","h4_equal_high","h4_equal_low"):
        v=getattr(r,n,np.nan)
        if np.isfinite(v): out.append((n,float(v)))
    return out

def zones(r):
    px=float(r.close); tol=.30*float(r.h1_atr) if np.isfinite(r.h1_atr) else 0; a=levels(r); S=[z for z in a if z[1]<=px+tol]; R=[z for z in a if z[1]>=px-tol]; s=min(S,key=lambda z:abs(z[1]-px)) if S else None; q=min(R,key=lambda z:abs(z[1]-px)) if R else None; return (s[1] if s else None,q[1] if q else None)
def at_sup(r,s): return s is not None and float(r.low)<=s+.30*float(r.h1_atr) and float(r.close)>=s-.30*float(r.h1_atr)
def at_res(r,s): return s is not None and float(r.high)>=s-.30*float(r.h1_atr) and float(r.close)<=s+.30*float(r.h1_atr)
def sess(t): return "asia" if t.hour<7 else "london" if t.hour<12 else "overlap" if t.hour<16 else "new_york" if t.hour<21 else "off_hours"

@dataclass
class Trade:
    strategy:str; symbol:str; signal_time:pd.Timestamp; entry_time:pd.Timestamp; direction:str; entry:float; stop:float; target:float; rr:float; status:str; gross_r:float; gross_r_neutral:float; exit_time:pd.Timestamp; trigger:str; zone:float|None; year:int; sess:str

def simulate(m5,start,direction,stop,rr):
    pos=int(m5.date.searchsorted(start,side="left"));
    if pos>=len(m5): return None
    entry=float(m5.iloc[pos].open); risk=entry-stop if direction=="long" else stop-entry
    if risk<=0:return None
    target=entry+rr*risk if direction=="long" else entry-rr*risk; q=m5.iloc[pos:][m5.iloc[pos:].date<start+pd.Timedelta(hours=24)]
    if q.empty:return None
    for _,b in q.iterrows():
        hs=float(b.low)<=stop if direction=="long" else float(b.high)>=stop; ht=float(b.high)>=target if direction=="long" else float(b.low)<=target
        if hs and ht:return entry,target,"ambiguous",-1.,0.,pd.Timestamp(b.date)
        if hs:return entry,target,"loss",-1.,-1.,pd.Timestamp(b.date)
        if ht:return entry,target,"win",rr,rr,pd.Timestamp(b.date)
    b=q.iloc[-1]; gr=(float(b.close)-entry)/risk if direction=="long" else (entry-float(b.close))/risk; return entry,target,"timeout",float(gr),float(gr),pd.Timestamp(b.date)

def make_trade(name,symbol,r,m5,direction,zone,rr,trigger):
    start=pd.Timestamp(r.end); pos=int(m5.date.searchsorted(start,side="left"));
    if pos>=len(m5):return None
    entry=float(m5.iloc[pos].open); atr=float(r.atr)
    if name.startswith("CANDLE_ONLY"): stop=entry-atr if direction=="long" else entry+atr
    elif direction=="long": stop=min(float(r.roll_low8),float(zone) if zone is not None else float(r.roll_low8))-.10*atr
    else: stop=max(float(r.roll_high8),float(zone) if zone is not None else float(r.roll_high8))+.10*atr
    risk=entry-stop if direction=="long" else stop-entry
    if not(np.isfinite(atr) and atr>0 and .10*atr<=risk<=2*atr):return None
    q=simulate(m5,start,direction,stop,rr)
    if not q:return None
    entry,target,status,gr,gn,exit_time=q; return Trade(name,symbol,t,start,direction,entry,stop,target,rr,status,gr,gn,exit_time,trigger,zone,t.year,sess(t))

def scan(symbol,m5):
    m15=candles(basic(resample(m5,"15min",15))); h1=structure(basic(resample(m5,"1h",60))); h4=h4_extra(structure(basic(resample(m5,"4h",240)))); d1=structure(basic(resample(m5,"1D",1440))); m15=context(periods(m15),h1,h4,d1); m15=m15[(m15.end.dt.year>=2022)&(m15.end.dt.year<=2025)].reset_index(drop=True)
    RR={"TCR_2.5R":2.5,"TCR_2R":2.,"TCR_3R":3.,"BRC_2.5R":2.5,"DFP_3R":3.,"DFP_2.5R":2.5,"KOJO_PX_3R":3.,"CANDLE_ONLY_2.5R":2.5,"TCR_SR_NO_CANDLE_2.5R":2.5,"TCR_CANDLE_NO_SR_2.5R":2.5,"TCR_TREND_ONLY_2.5R":2.5,"DFP_NO_SR_3R":3.,"DFP_NO_CANDLE_3R":3.}; active={k:pd.Timestamp.min.tz_localize("UTC") for k in RR}; out=[]; pendL=pendS=None; prevL=prevS=False
    for i,r in m15.iterrows():
        if not np.isfinite(r.atr) or not np.isfinite(r.h1_atr):continue
        t=pd.Timestamp(r.end); sup,res=zones(r); bt=bool(r.bull_trigger); st=bool(r.bear_trigger); bn=str(r.trigger_name_long); sn=str(r.trigger_name_short); d1b=r.d1_structure=="bullish"; d1s=r.d1_structure=="bearish"; h4b=r.h4_structure=="bullish"; h4s=r.h4_structure=="bearish"; hb=h4b or (r.h4_structure=="mixed" and r.h4_ema_label=="bullish" and float(r.h4_ema_slope20)>0); hs=h4s or (r.h4_structure=="mixed" and r.h4_ema_label=="bearish" and float(r.h4_ema_slope20)<0); AS=at_sup(r,sup); AR=at_res(r,res)
        if pendL is None and res is not None and d1b and float(r.close)>res+.10*float(r.h1_atr):pendL=(i,res,i+8)
        if pendS is None and sup is not None and d1s and float(r.close)<sup-.10*float(r.h1_atr):pendS=(i,sup,i+8)
        def emit(name,d,z,trig):
            if t<=active[name]:return
            q=make_trade(name,symbol,r,m5,d,z,RR[name],trig)
            if q:out.append(q); active[name]=q.exit_time
        if d1b and hb and AS and bt:
            for n in ("TCR_2.5R","TCR_2R","TCR_3R"):emit(n,"long",sup,bn)
        if d1s and hs and AR and st:
            for n in ("TCR_2.5R","TCR_2R","TCR_3R"):emit(n,"short",res,sn)
        aL=d1b and hb; aS=d1s and hs
        if aL and AS:emit("TCR_SR_NO_CANDLE_2.5R","long",sup,"none")
        if aS and AR:emit("TCR_SR_NO_CANDLE_2.5R","short",res,"none")
        if aL and bt:emit("TCR_CANDLE_NO_SR_2.5R","long",None,bn)
        if aS and st:emit("TCR_CANDLE_NO_SR_2.5R","short",None,sn)
        if aL and not prevL:emit("TCR_TREND_ONLY_2.5R","long",None,"trend_change")
        if aS and not prevS:emit("TCR_TREND_ONLY_2.5R","short",None,"trend_change")
        prevL=aL; prevS=aS
        if pendL:
            bi,lvl,ex=pendL
            if i>ex:pendL=None
            elif i>bi and abs(float(r.low)-lvl)<=.30*float(r.h1_atr) and float(r.close)>=lvl-.15*float(r.h1_atr) and bt:emit("BRC_2.5R","long",lvl,bn);pendL=None
        if pendS:
            bi,lvl,ex=pendS
            if i>ex:pendS=None
            elif i>bi and abs(float(r.high)-lvl)<=.30*float(r.h1_atr) and float(r.close)<=lvl+.15*float(r.h1_atr) and st:emit("BRC_2.5R","short",lvl,sn);pendS=None
        lo=float(r.h4_impulse_low) if np.isfinite(r.h4_impulse_low) else np.nan; hi=float(r.h4_impulse_high) if np.isfinite(r.h4_impulse_high) else np.nan; ha=float(r.h4_atr) if np.isfinite(r.h4_atr) else np.nan; li=int(r.h4_impulse_low_idx) if np.isfinite(r.h4_impulse_low_idx) else -1; hii=int(r.h4_impulse_high_idx) if np.isfinite(r.h4_impulse_high_idx) else -1
        if np.isfinite(lo) and np.isfinite(hi) and hi>lo and np.isfinite(ha) and hi-lo>=1.25*ha:
            rg=hi-lo
            if d1b and hii>li:
                z50=hi-.5*rg; z618=hi-.618*rg; z786=hi-.786*rg; pocket=float(r.low)<=z50 and float(r.high)>=z618 and float(r.close)>=z786; ov=sup is not None and z618-.35*float(r.h1_atr)<=sup<=z50+.35*float(r.h1_atr)
                if pocket and ov and bt:emit("DFP_3R","long",sup,bn);emit("DFP_2.5R","long",sup,bn)
                if pocket and bt:emit("DFP_NO_SR_3R","long",None,bn)
                if pocket and ov:emit("DFP_NO_CANDLE_3R","long",sup,"none")
            if d1s and li>hii:
                z50=lo+.5*rg; z618=lo+.618*rg; z786=lo+.786*rg; pocket=float(r.high)>=z50 and float(r.low)<=z618 and float(r.close)<=z786; ov=res is not None and z50-.35*float(r.h1_atr)<=res<=z618+.35*float(r.h1_atr)
                if pocket and ov and st:emit("DFP_3R","short",res,sn);emit("DFP_2.5R","short",res,sn)
                if pocket and st:emit("DFP_NO_SR_3R","short",None,sn)
                if pocket and ov:emit("DFP_NO_CANDLE_3R","short",res,"none")
        if h4b and AS and bt and float(r.close)>=sup-.15*float(r.h1_atr):emit("KOJO_PX_3R","long",sup,bn)
        if h4s and AR and st and float(r.close)<=res+.15*float(r.h1_atr):emit("KOJO_PX_3R","short",res,sn)
        if bt and not st:emit("CANDLE_ONLY_2.5R","long",None,bn)
        elif st and not bt:emit("CANDLE_ONLY_2.5R","short",None,sn)
    return pd.DataFrame([q.__dict__ for q in out])

def dd(x):
    c=x.cumsum(); return float((c-c.cummax()).min()) if len(c) else np.nan

def boot(vals):
    if len(vals)<2:return [np.nan,np.nan]
    rng=np.random.default_rng(SEED); m=np.array([rng.choice(vals,len(vals),replace=True).mean() for _ in range(BOOT_REPS)]); return [float(np.quantile(m,.025)),float(np.quantile(m,.975))]
def metric(g):
    if g.empty:return {"n":0}
    w=int((g.status=="win").sum()); l=int((g.status=="loss").sum()); a=int((g.status=="ambiguous").sum()); to=int((g.status=="timeout").sum()); pos=float(g.loc[g.gross_r>0,"gross_r"].sum()); neg=float(-g.loc[g.gross_r<0,"gross_r"].sum()); dec=w+l
    return {"n":int(len(g)),"wins":w,"losses":l,"ambiguous":a,"timeouts":to,"decisive_win_rate":w/dec if dec else None,"pessimistic_win_rate":w/(dec+a) if dec+a else None,"mean_r":float(g.gross_r.mean()),"neutral_mean_r":float(g.gross_r_neutral.mean()),"median_r":float(g.gross_r.median()),"profit_factor":pos/neg if neg else None,"max_drawdown_r":dd(g.gross_r),"bootstrap95_mean_r":boot(g.gross_r.to_numpy(float))}
def summarize(t):
    out={"protocol":"V3.5 frozen standalone trend-candle engine","years":list(YEARS),"symbols":list(SYMBOLS),"strategies":{}}
    for s in sorted(t.strategy.unique()):
        g=t[t.strategy==s].sort_values("signal_time"); it={"pooled":metric(g),"by_symbol":{},"by_year":{},"by_direction":{},"by_session":{},"by_trigger":{}}
        for x in SYMBOLS:it["by_symbol"][x]=metric(g[g.symbol==x])
        for y in YEARS:it["by_year"][str(y)]=metric(g[g.year==y])
        for d in ("long","short"):it["by_direction"][d]=metric(g[g.direction==d])
        for k,h in g.groupby("sess"):it["by_session"][str(k)]=metric(h)
        for k,h in g.groupby("trigger"):it["by_trigger"][str(k)]=metric(h)
        out["strategies"][s]=it
    cm=out["strategies"].get("CANDLE_ONLY_2.5R",{}).get("pooled",{}).get("mean_r")
    for s in ("TCR_2.5R","BRC_2.5R","DFP_3R","KOJO_PX_3R"):
        if s not in out["strategies"]:continue
        it=out["strategies"][s]; p=it["pooled"]; sy=it["by_symbol"]; yr=it["by_year"]; py=sum((yr[str(y)].get("mean_r") if yr[str(y)].get("mean_r") is not None else -999)>0 for y in YEARS); ci=p.get("bootstrap95_mean_r",[np.nan,np.nan]); stat=(np.isfinite(ci[0]) and ci[0]>0) or py==4; beat=cm is not None and p.get("mean_r") is not None and p["mean_r"]>=cm+.05
        gate={"n200":p.get("n",0)>=200,"each_symbol50":all(sy[x].get("n",0)>=50 for x in SYMBOLS),"mean_r_gt_0_10":(p.get("mean_r") if p.get("mean_r") is not None else -999)>.10,"pf_gt_1_10":(p.get("profit_factor") or 0)>1.10,"positive_3_of_4_years":py>=3,"both_symbols_nonnegative":all((sy[x].get("mean_r") if sy[x].get("mean_r") is not None else -999)>=0 for x in SYMBOLS),"statistical_or_4of4_year_support":bool(stat),"beats_candle_control_by_0_05R":bool(beat)}; gate["historically_promising"]=all(gate.values()); it["promotion_gate"]=gate
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True); chunks=[]
    for sym in SYMBOLS:
        m5=load_market(a.data_dir/f"{sym}-5m.feather"); m5=m5[(m5.date>=pd.Timestamp("2021-09-01",tz="UTC"))&(m5.date<pd.Timestamp("2026-01-01",tz="UTC"))].reset_index(drop=True); q=scan(sym,m5); chunks.append(q); print(sym,len(q),q.strategy.value_counts().to_dict())
    t=pd.concat(chunks,ignore_index=True).sort_values(["signal_time","symbol","strategy"]).reset_index(drop=True); t.to_csv(a.out/"v35_trades.csv",index=False); s=summarize(t); (a.out/"v35_summary.json").write_text(json.dumps(s,indent=2,default=str)); rows=[]
    for k,v in s["strategies"].items():
        p=v["pooled"]; rows.append({"strategy":k,**{z:p.get(z) for z in ("n","decisive_win_rate","pessimistic_win_rate","mean_r","neutral_mean_r","profit_factor","max_drawdown_r")},"promising":v.get("promotion_gate",{}).get("historically_promising")})
    pd.DataFrame(rows).sort_values("mean_r",ascending=False).to_csv(a.out/"v35_leaderboard.csv",index=False); print(json.dumps(s,indent=2,default=str))
if __name__=="__main__":main()
