from __future__ import annotations

"""V2 v3.4 market-intelligence challenger study.

Research-only. Reuses the frozen v1.9 V2 setup universe and public M5 OHLC.
All setup features are frozen using information available at or before the
setup's BOS time. Entry-confirmation variants wait for a completed M15 candle.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

SYMBOLS = ("EURUSD", "GBPUSD")
YEARS = (2022, 2023, 2024, 2025)
PIP = 0.0001
REWARD_R = 2.5
KOJO_R = 3.0
BOOT_REPS = 2500
SEED = 3401


def utc(v: Any) -> pd.Timestamp:
    x = pd.Timestamp(v)
    return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")


def load_market(path: Path) -> pd.DataFrame:
    df = pd.read_feather(path)
    cols = {str(c).lower(): c for c in df.columns}
    tcol = cols.get("date") or cols.get("datetime") or cols.get("timestamp") or cols.get("time")
    if tcol is None:
        raise ValueError(f"{path}: no time column")
    ren = {tcol: "date"}
    for k in ("open", "high", "low", "close"):
        if k not in cols:
            raise ValueError(f"{path}: missing {k}")
        ren[cols[k]] = k
    x = df.rename(columns=ren)[["date", "open", "high", "low", "close"]].copy()
    x["date"] = pd.to_datetime(x["date"], utc=True)
    for c in ("open", "high", "low", "close"):
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.dropna().sort_values("date").drop_duplicates("date").reset_index(drop=True)
    x = x[(x.open > 0) & (x.high >= x.low) & (x.low > 0) & (x.close > 0)]
    return x.reset_index(drop=True)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    x = df.set_index("date")
    y = x.resample(rule, label="left", closed="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")
    ).dropna()
    return y.reset_index()


def tr(df: pd.DataFrame) -> pd.Series:
    prev = df.close.shift(1)
    return pd.concat([(df.high-df.low), (df.high-prev).abs(), (df.low-prev).abs()], axis=1).max(axis=1)


def add_atr(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    x = df.copy()
    x["atr"] = tr(x).rolling(n, min_periods=n).mean()
    return x


def completed_before(df: pd.DataFrame, t: pd.Timestamp, minutes: int) -> pd.DataFrame:
    return df[df.date + pd.Timedelta(minutes=minutes) <= t]


def pivots(df: pd.DataFrame, left: int = 2, right: int = 2) -> tuple[list[tuple[int,float]], list[tuple[int,float]]]:
    hi, lo = [], []
    h = df.high.to_numpy(float); l = df.low.to_numpy(float)
    for i in range(left, len(df)-right):
        if h[i] > np.max(h[i-left:i]) and h[i] >= np.max(h[i+1:i+right+1]):
            hi.append((i, float(h[i])))
        if l[i] < np.min(l[i-left:i]) and l[i] <= np.min(l[i+1:i+right+1]):
            lo.append((i, float(l[i])))
    return hi, lo


def structure_label(df: pd.DataFrame) -> str:
    if len(df) < 12:
        return "mixed"
    hi, lo = pivots(df)
    if len(hi) < 2 or len(lo) < 2:
        return "mixed"
    hh = hi[-1][1] > hi[-2][1]; hl = lo[-1][1] > lo[-2][1]
    lh = hi[-1][1] < hi[-2][1]; ll = lo[-1][1] < lo[-2][1]
    if hh and hl: return "bullish"
    if lh and ll: return "bearish"
    return "mixed"


def ema_label(df: pd.DataFrame) -> str:
    if len(df) < 50:
        return "mixed"
    c = df.close
    e20 = c.ewm(span=20, adjust=False).mean().iloc[-1]
    e50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
    p = c.iloc[-1]
    if p > e20 > e50: return "bullish"
    if p < e20 < e50: return "bearish"
    return "mixed"


def agrees(label: str, direction: str) -> bool:
    return (direction == "long" and label == "bullish") or (direction == "short" and label == "bearish")


def candle_shape(row: pd.Series) -> dict[str, float]:
    o,h,l,c = map(float, (row.open,row.high,row.low,row.close))
    rng=max(h-l,1e-12); body=abs(c-o); upper=h-max(o,c); lower=min(o,c)-l
    return {"body_ratio":body/rng,"upper_ratio":upper/rng,"lower_ratio":lower/rng,"bull":float(c>o),"bear":float(c<o)}


def candle_patterns(cur: pd.Series, prev: pd.Series | None = None) -> dict[str,bool]:
    s=candle_shape(cur)
    bull_reject = float(cur.close)>float(cur.open) and s["lower_ratio"]>=0.45 and s["lower_ratio"] >= 1.8*s["body_ratio"]
    bear_reject = float(cur.close)<float(cur.open) and s["upper_ratio"]>=0.45 and s["upper_ratio"] >= 1.8*s["body_ratio"]
    doji = s["body_ratio"] <= 0.12
    bull_eng=bear_eng=False
    if prev is not None:
        po,pc=float(prev.open),float(prev.close); o,c=float(cur.open),float(cur.close)
        bull_eng=pc<po and c>o and o<=pc and c>=po
        bear_eng=pc>po and c<o and o>=pc and c<=po
    return {"bull_engulf":bool(bull_eng), "bear_engulf":bool(bear_eng),
            "hammer_like":bool(bull_reject), "shooting_star_like":bool(bear_reject), "doji":bool(doji)}


def fvg_at(df15: pd.DataFrame, bos_t: pd.Timestamp, direction: str) -> tuple[bool,float]:
    q = completed_before(df15, bos_t + pd.Timedelta(minutes=15), 15)
    if len(q) < 3:
        return False,0.0
    a,_,c = q.iloc[-3],q.iloc[-2],q.iloc[-1]
    qa=add_atr(q)
    atr = float(qa.atr.iloc[-1]) if len(q)>=14 else np.nan
    gap=max(0.0,float(c.low)-float(a.high)) if direction=="long" else max(0.0,float(a.low)-float(c.high))
    return gap>0, float(gap/atr) if np.isfinite(atr) and atr>0 else 0.0


def prior_period_levels(df: pd.DataFrame, t: pd.Timestamp, rule: str) -> tuple[float|None,float|None]:
    x=df[df.date < t].set_index("date")
    if x.empty: return None,None
    r=x.resample(rule).agg({"high":"max","low":"min"}).dropna()
    if len(r)<2: return None,None
    p=r.iloc[-2]
    return float(p.high),float(p.low)


def nearest_major_distance(price: float, atr: float, levels: Iterable[float|None]) -> float:
    xs=[abs(price-float(v))/atr for v in levels if v is not None and np.isfinite(v)]
    return min(xs) if xs and atr>0 else np.nan


def equal_level_distance(h4: pd.DataFrame, t: pd.Timestamp, price: float, atr15: float) -> tuple[float,float]:
    q=completed_before(h4,t,240).tail(80)
    if len(q)<10 or atr15<=0: return np.nan,np.nan
    hs,ls=pivots(q)
    qa=add_atr(q)
    h4atr=float(qa.atr.iloc[-1]) if len(q)>=14 and np.isfinite(qa.atr.iloc[-1]) else 0.0
    tol=max(0.15*h4atr,2*PIP)
    def cluster(vals: list[float]) -> float:
        if len(vals)<2: return np.nan
        best=np.nan
        for i in range(len(vals)):
            for j in range(i+1,len(vals)):
                if abs(vals[i]-vals[j])<=tol:
                    d=abs(price-(vals[i]+vals[j])/2)/atr15
                    best=d if not np.isfinite(best) else min(best,d)
        return best
    return cluster([v for _,v in hs[-8:]]), cluster([v for _,v in ls[-8:]])


def session_name(t: pd.Timestamp) -> str:
    h=t.hour
    if 0<=h<7:return "asia"
    if 7<=h<12:return "london"
    if 12<=h<16:return "overlap"
    if 16<=h<21:return "new_york"
    return "off_hours"


def annotate_setup(s: pd.Series, frames: dict[str,pd.DataFrame]) -> dict[str,Any]:
    t=utc(s.bos_time); direction=str(s.direction); price=float(s.bos_reference); atr15=float(s.atr)
    m15=frames["15m"]; out={}
    for name,mins in (("m15",15),("h1",60),("h4",240),("d1",1440),("w1",10080),("mn1",43200)):
        q=completed_before(frames[name],t,mins)
        out[f"{name}_structure"]=structure_label(q.tail(160))
        out[f"{name}_ema"]=ema_label(q.tail(220))
    out["struct_align_count"]=sum(agrees(out[f"{k}_structure"],direction) for k in ("h4","d1","w1","mn1"))
    out["ema_align_count"]=sum(agrees(out[f"{k}_ema"],direction) for k in ("h4","d1","w1","mn1"))
    pdh,pdl=prior_period_levels(m15,t,"1D"); pwh,pwl=prior_period_levels(m15,t,"W-MON"); pmh,pml=prior_period_levels(m15,t,"MS")
    out.update(prev_day_high=pdh,prev_day_low=pdl,prev_week_high=pwh,prev_week_low=pwl,prev_month_high=pmh,prev_month_low=pml)
    out["major_level_dist_atr"]=nearest_major_distance(price,atr15,[pdh,pdl,pwh,pwl,pmh,pml])
    eqh,eql=equal_level_distance(frames["h4"],t,price,atr15)
    out["equal_high_dist_atr"]=eqh; out["equal_low_dist_atr"]=eql
    rel=eqh if direction=="short" else eql
    out["liquidity_location"]=bool((np.isfinite(out["major_level_dist_atr"]) and out["major_level_dist_atr"]<=0.75) or (np.isfinite(rel) and rel<=0.75))
    fvg,gap=fvg_at(m15,t,direction); out["fvg"]=fvg; out["fvg_atr"]=gap
    out["strong_displacement"]=bool(float(s.bos_displacement_atr)>=0.20)
    out["session"]=session_name(t); out["active_session"]=out["session"] in ("london","overlap","new_york")
    poi_t=utc(s.poi_time); q=m15[m15.date==poi_t]
    if q.empty:
        out.update(poi_body_ratio=np.nan,poi_rejection=False)
    else:
        sh=candle_shape(q.iloc[-1]); out["poi_body_ratio"]=sh["body_ratio"]
        out["poi_rejection"]=bool(sh["body_ratio"]>=0.35 and max(sh["upper_ratio"],sh["lower_ratio"])<=0.60)
    score=0
    score += 2 if out["struct_align_count"]>=3 else 1 if out["struct_align_count"]>=2 else 0
    score += int(out["liquidity_location"])+int(out["strong_displacement"])+int(out["fvg"])+int(out["active_session"])+int(out["poi_rejection"])
    out["context_score"]=score
    return out


def metric(g: pd.DataFrame) -> dict[str,Any]:
    if g.empty:return {"n":0}
    x=g[g.risk_valid.astype(bool)].copy(); filled=x[x.filled.astype(bool)].copy(); decisive=filled[filled.outcome.isin(["win","loss"])]
    return {"n":int(len(x)),"filled":int(len(filled)),"fill_rate":float(len(filled)/len(x)) if len(x) else None,
            "decisive":int(len(decisive)),"win_rate":float((decisive.outcome=="win").mean()) if len(decisive) else None,
            "opportunity_r":float(x.gross_r_primary.mean()) if len(x) else None,
            "pessimistic_r":float(x.gross_r_pessimistic.mean()) if len(x) else None,
            "ambiguous_rate":float(filled.outcome.astype(str).str.startswith("ambiguous").mean()) if len(filled) else None}


def bootstrap_delta(df: pd.DataFrame, mask: pd.Series, reps:int=BOOT_REPS) -> dict[str,Any]:
    base=df.gross_r_primary.to_numpy(float); cand=np.where(mask.to_numpy(bool),base,0.0); d=cand-base
    rng=np.random.default_rng(SEED); vals=np.empty(reps)
    for i in range(reps):
        idx=rng.integers(0,len(d),len(d)); vals[i]=d[idx].mean()
    return {"n":int(len(d)),"delta_opportunity_r":float(d.mean()),"low95":float(np.quantile(vals,.025)),"high95":float(np.quantile(vals,.975))}


def directional_confirmation(cur: pd.Series, prev: pd.Series|None, direction:str)->tuple[bool,str]:
    p=candle_patterns(cur,prev); sh=candle_shape(cur)
    if direction=="long":
        if p["bull_engulf"]:return True,"bull_engulf"
        if p["hammer_like"]:return True,"hammer_like"
        if float(cur.close)>float(cur.open) and sh["body_ratio"]>=0.55:return True,"strong_bull"
    else:
        if p["bear_engulf"]:return True,"bear_engulf"
        if p["shooting_star_like"]:return True,"shooting_star_like"
        if float(cur.close)<float(cur.open) and sh["body_ratio"]>=0.55:return True,"strong_bear"
    return False,"none"


def simulate_from_close(m5: pd.DataFrame, start:pd.Timestamp, direction:str, entry:float, stop:float, rr:float=REWARD_R, bars:int=144)->dict[str,Any]:
    risk=entry-stop if direction=="long" else stop-entry
    if risk<=0:return {"status":"invalid","gross":0.0}
    target=entry+rr*risk if direction=="long" else entry-rr*risk
    pos=int(m5.date.searchsorted(start,side="left")); q=m5.iloc[pos:pos+bars]
    for _,r in q.iterrows():
        hs=float(r.low)<=stop if direction=="long" else float(r.high)>=stop
        ht=float(r.high)>=target if direction=="long" else float(r.low)<=target
        if hs and ht:return {"status":"ambiguous","gross":0.0}
        if hs:return {"status":"loss","gross":-1.0}
        if ht:return {"status":"win","gross":rr}
    if q.empty:return {"status":"missing","gross":0.0}
    last=float(q.iloc[-1].close); gr=(last-entry)/risk if direction=="long" else (entry-last)/risk
    return {"status":"timeout","gross":float(np.clip(gr,-1,rr))}


def confirmation_variant(base: pd.DataFrame, frames_by:dict[str,dict[str,pd.DataFrame]])->pd.DataFrame:
    rows=[]
    for _,r in base.iterrows():
        if not bool(r.risk_valid) or not bool(r.filled) or pd.isna(r.fill_time): continue
        sym=str(r.symbol); direction=str(r.direction); fill=utc(r.fill_time); m15=frames_by[sym]["15m"]; m5=frames_by[sym]["5m"]
        bar_start=fill.floor("15min"); idx=m15.index[m15.date==bar_start]
        if len(idx)==0 or int(idx[0])<1: continue
        i=int(idx[0]); cur,prev=m15.iloc[i],m15.iloc[i-1]; ok,pattern=directional_confirmation(cur,prev,direction)
        if not ok: continue
        entry=float(cur.close); stop=float(r.stop); sim=simulate_from_close(m5,bar_start+pd.Timedelta(minutes=15),direction,entry,stop,REWARD_R)
        rows.append({"setup_id":r.setup_id,"symbol":sym,"year":int(r.year),"pattern":pattern,"entry":entry,**sim})
    return pd.DataFrame(rows)


def swing_pattern_bias(w1: pd.DataFrame, t:pd.Timestamp)->str:
    q=completed_before(w1,t,10080).tail(80); hs,ls=pivots(q); qa=add_atr(q)
    atr=float(qa.atr.iloc[-1]) if len(q)>=14 and np.isfinite(qa.atr.iloc[-1]) else np.nan
    if not np.isfinite(atr): return "mixed"
    tol=0.35*atr
    if len(hs)>=2 and abs(hs[-1][1]-hs[-2][1])<=tol:
        between=[v for i,v in ls if hs[-2][0]<i<hs[-1][0]]
        if between and float(q.close.iloc[-1])<min(between): return "bearish"
    if len(ls)>=2 and abs(ls[-1][1]-ls[-2][1])<=tol:
        between=[v for i,v in hs if ls[-2][0]<i<ls[-1][0]]
        if between and float(q.close.iloc[-1])>max(between): return "bullish"
    if len(hs)>=3 and len(ls)>=2:
        a,b,c=hs[-3:]; shoulders=abs(a[1]-c[1])<=tol and b[1]>a[1]+0.2*atr and b[1]>c[1]+0.2*atr
        neck=[v for i,v in ls if a[0]<i<c[0]]
        if shoulders and neck and float(q.close.iloc[-1])<np.mean(neck): return "bearish"
    if len(ls)>=3 and len(hs)>=2:
        a,b,c=ls[-3:]; shoulders=abs(a[1]-c[1])<=tol and b[1]<a[1]-0.2*atr and b[1]<c[1]-0.2*atr
        neck=[v for i,v in hs if a[0]<i<c[0]]
        if shoulders and neck and float(q.close.iloc[-1])>np.mean(neck): return "bullish"
    return "mixed"


def standalone_proxies(frames_by:dict[str,dict[str,pd.DataFrame]], start="2022-01-01", end="2025-12-31")->pd.DataFrame:
    rows=[]
    lo_t=pd.Timestamp(start,tz="UTC"); hi_t=pd.Timestamp(end,tz="UTC")+pd.Timedelta(days=1)
    for sym,fr in frames_by.items():
        h4=add_atr(fr["h4"]); d1=fr["d1"]; w1=fr["w1"]; mn=fr["mn1"]; m15=fr["15m"]; m5=fr["5m"]
        for i in range(60,len(h4)-1):
            t=utc(h4.iloc[i].date)+pd.Timedelta(hours=4)
            if t<lo_t or t>=hi_t: continue
            cur=h4.iloc[i]; prev=h4.iloc[i-1]; pat=candle_patterns(cur,prev)
            ds=structure_label(completed_before(d1,t,1440).tail(100)); ws=structure_label(completed_before(w1,t,10080).tail(100)); ms=structure_label(completed_before(mn,t,43200).tail(80)); dapo_pat=swing_pattern_bias(w1,t)
            pdh,pdl=prior_period_levels(m15,t,"1D"); pwh,pwl=prior_period_levels(m15,t,"W-MON"); pmh,pml=prior_period_levels(m15,t,"MS")
            atr=float(cur.atr) if np.isfinite(cur.atr) else np.nan
            if not np.isfinite(atr) or atr<=0: continue
            close=float(cur.close)
            for direction in ("long","short"):
                signok=(direction=="long" and dapo_pat=="bullish") or (direction=="short" and dapo_pat=="bearish")
                trendok=sum(agrees(x,direction) for x in (ds,ws,ms))>=2
                lvl=nearest_major_distance(close,atr,[pdh,pdl,pwh,pwl,pmh,pml])
                candleok=(direction=="long" and (pat["bull_engulf"] or pat["hammer_like"])) or (direction=="short" and (pat["bear_engulf"] or pat["shooting_star_like"]))
                if signok and trendok and np.isfinite(lvl) and lvl<=1.0 and candleok:
                    stop=float(cur.low) if direction=="long" else float(cur.high); sim=simulate_from_close(m5,t,direction,close,stop,3.0,432)
                    rows.append({"strategy":"dapo_public_proxy","symbol":sym,"time":t,"year":t.year,"direction":direction,**sim})
            q=completed_before(m15,t,15).tail(32)
            if len(q)>=22:
                qa=add_atr(q); sweep_long=sweep_short=False
                for j in range(max(20,len(q)-12),len(q)):
                    a=float(qa.atr.iloc[j]) if np.isfinite(qa.atr.iloc[j]) else 0
                    if a<=0: continue
                    ph=float(q.high.iloc[j-20:j].max()); pl=float(q.low.iloc[j-20:j].min())
                    sweep_short |= float(q.high.iloc[j])>ph+.03*a and float(q.close.iloc[j])<ph
                    sweep_long |= float(q.low.iloc[j])<pl-.03*a and float(q.close.iloc[j])>pl
                h4s=structure_label(completed_before(h4,t,240).tail(100))
                for direction,sweep in (("long",sweep_long),("short",sweep_short)):
                    trendok=agrees(ds,direction) and (agrees(ws,direction) or agrees(h4s,direction))
                    candleok=(direction=="long" and (pat["bull_engulf"] or pat["hammer_like"] or float(cur.close)>float(cur.open))) or (direction=="short" and (pat["bear_engulf"] or pat["shooting_star_like"] or float(cur.close)<float(cur.open)))
                    if sweep and trendok and candleok:
                        stop=float(cur.low) if direction=="long" else float(cur.high); sim=simulate_from_close(m5,t,direction,close,stop,KOJO_R,144)
                        rows.append({"strategy":"kojo_public_proxy","symbol":sym,"time":t,"year":t.year,"direction":direction,**sim})
    return pd.DataFrame(rows)


def standalone_metric(g:pd.DataFrame)->dict[str,Any]:
    if g.empty:return {"n":0}
    decisive=g[g.status.isin(["win","loss"])]
    return {"n":int(len(g)),"wins":int((g.status=="win").sum()),"losses":int((g.status=="loss").sum()),
            "timeouts":int((g.status=="timeout").sum()),"ambiguous":int((g.status=="ambiguous").sum()),
            "win_rate":float((decisive.status=="win").mean()) if len(decisive) else None,"mean_r":float(g.gross.mean())}


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",type=Path,required=True); ap.add_argument("--v19-dir",type=Path,required=True); ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    setups=pd.read_csv(args.v19_dir/"v19_poi_setups.csv"); sim=pd.read_csv(args.v19_dir/"v19_poi_depth_simulations.csv")
    for c in ("bos_time","sweep_time","poi_time"): setups[c]=pd.to_datetime(setups[c],utc=True)
    for c in ("bos_time","sweep_time","poi_time","fill_time"):
        if c in sim.columns: sim[c]=pd.to_datetime(sim[c],utc=True,errors="coerce")
    frames_by={}
    for sym in SYMBOLS:
        m5=load_market(args.data_dir/f"{sym}-5m.feather")
        frames_by[sym]={"5m":m5,"15m":resample(m5,"15min"),"h1":resample(m5,"1h"),"h4":resample(m5,"4h"),"d1":resample(m5,"1D"),"w1":resample(m5,"W-MON"),"mn1":resample(m5,"MS")}
    annotations=[]
    for _,s in setups.iterrows():
        if int(s.year) in YEARS:
            annotations.append({"setup_id":s.setup_id,"symbol":s.symbol,"direction":s.direction,"year":int(s.year),**annotate_setup(s,frames_by[str(s.symbol)])})
    ann=pd.DataFrame(annotations)
    base=sim[(np.isclose(sim.depth.astype(float),.50)) & sim.year.astype(int).isin(YEARS)].copy().merge(ann,on=["setup_id","symbol","direction","year"],how="inner")
    base=base[base.risk_valid.astype(bool)].reset_index(drop=True)
    masks={
        "v2_baseline":pd.Series(True,index=base.index),
        "v2_htf_struct_2plus":base.struct_align_count>=2,
        "v2_htf_struct_3plus":base.struct_align_count>=3,
        "v2_major_liquidity":base.liquidity_location.astype(bool),
        "v2_displacement_fvg":base.strong_displacement.astype(bool)&base.fvg.astype(bool),
        "v2_active_session":base.active_session.astype(bool),
        "v2_poi_candle_quality":base.poi_rejection.astype(bool),
        "v2_context_score_3plus":base.context_score>=3,
        "v2_context_score_4plus":base.context_score>=4,
        "v2_context_score_5plus":base.context_score>=5,
        "v2_dapo_hybrid":(base.struct_align_count>=3)&base.liquidity_location.astype(bool)&(base.context_score>=4),
        "v2_kojo_hybrid":(base.struct_align_count>=2)&base.liquidity_location.astype(bool)&base.strong_displacement.astype(bool)&(base.context_score>=4),
    }
    results={}
    for k,m in masks.items():
        results[k]=metric(base[m])
        if k!="v2_baseline": results[k]["paired_delta"]=bootstrap_delta(base,m)
    yearly=[]
    for k,m in masks.items():
        for y in YEARS: yearly.append({"strategy":k,"year":y,**metric(base[(base.year==y)&m])})
    yearly_df=pd.DataFrame(yearly)
    confirm=confirmation_variant(base,frames_by); confirm_summary=standalone_metric(confirm) if not confirm.empty else {"n":0}
    confirm_by_pattern=[]
    if not confirm.empty:
        for p,g in confirm.groupby("pattern"): confirm_by_pattern.append({"pattern":p,**standalone_metric(g)})
    standalone=standalone_proxies(frames_by); standalone_summary={}
    if not standalone.empty:
        for k,g in standalone.groupby("strategy"): standalone_summary[k]=standalone_metric(g)
    else: standalone_summary={"dapo_public_proxy":{"n":0},"kojo_public_proxy":{"n":0}}
    ablations=[]
    for feat in ("fvg","strong_displacement","active_session","poi_rejection","liquidity_location"):
        for val,g in base.groupby(feat): ablations.append({"feature":feat,"value":bool(val),**metric(g)})
    for c in ("struct_align_count","context_score"):
        for val,g in base.groupby(c): ablations.append({"feature":c,"value":int(val),**metric(g)})
    ablation_df=pd.DataFrame(ablations)
    summary={
        "study":"V2 v3.4 market intelligence challengers",
        "boundary":"Public-price research. Kojo/Dapo strategies are transparent public-principles proxies, not claims of their proprietary paid systems.",
        "years":list(YEARS),"symbols":list(SYMBOLS),"baseline_setups":int(len(base)),"strategies":results,
        "candle_confirmation":{"summary":confirm_summary,"by_pattern":confirm_by_pattern},"standalone_public_proxies":standalone_summary,
        "promotion_policy":"No baseline rule is promoted unless paired opportunity-R improves with 95% bootstrap lower bound > 0, at least 3/4 completed years are non-inferior, and both pairs are non-inferior with adequate sample.",
        "notes":["Monthly/weekly/daily/H4 structure uses completed bars only.","Major liquidity map uses previous day/week/month highs/lows plus repeated H4 pivot clusters.","FVG is a strict three-candle gap around BOS; displacement is normalized by V2 ATR.","Candle confirmation waits for the M15 touch candle to close, then re-enters from its close using the frozen structural stop."]}
    (args.out/"v34_summary.json").write_text(json.dumps(summary,indent=2,default=str)); ann.to_csv(args.out/"v34_setup_context.csv",index=False); ablation_df.to_csv(args.out/"v34_feature_ablations.csv",index=False); yearly_df.to_csv(args.out/"v34_strategy_yearly.csv",index=False); confirm.to_csv(args.out/"v34_candle_confirmation_trades.csv",index=False); standalone.to_csv(args.out/"v34_public_proxy_trades.csv",index=False)
    print(json.dumps(summary,indent=2,default=str))


if __name__=="__main__":
    main()
