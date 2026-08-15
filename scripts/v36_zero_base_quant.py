from __future__ import annotations
import argparse, json, math, warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")
PIP = 0.0001
STOP_GRID = [0.50,0.75,1.00,1.25,1.50]
RR_GRID = [0.50,0.75,1.00,1.25,1.50,2.00,2.50,3.00]
HORIZON = 32
BASE_COST = {"EURUSD":0.8, "GBPUSD":1.0}
STRESS_COST = {"EURUSD":1.5, "GBPUSD":2.0}
SEED = 3601

def _ts(x):
    if isinstance(x,(int,float,np.integer,np.floating)):
        u="ms" if abs(float(x))>1e11 else "s"
        return pd.to_datetime(x,unit=u,utc=True)
    return pd.to_datetime(x,utc=True)

def load_duka(path:Path,symbol:str)->pd.DataFrame:
    raw=json.loads(path.read_text())
    if isinstance(raw,dict):
        for k in ("data","rows","rates"):
            if isinstance(raw.get(k),list):
                raw=raw[k]; break
    rows=[]
    for x in raw:
        if isinstance(x,dict):
            t=x.get("timestamp",x.get("time",x.get("date",x.get("datetime"))))
            o=x.get("open"); h=x.get("high"); l=x.get("low"); c=x.get("close")
            v=x.get("volume",x.get("vol",0))
        elif isinstance(x,(list,tuple)) and len(x)>=5:
            t,o,h,l,c=x[:5]; v=x[5] if len(x)>5 else 0
        else:
            continue
        try:
            rows.append((_ts(t),float(o),float(h),float(l),float(c),float(v or 0)))
        except Exception:
            pass
    if len(rows)<1000:
        raise ValueError(f"{path}: only {len(rows)} usable rows")
    df=pd.DataFrame(rows,columns=["date","open","high","low","close","volume"]).dropna()
    df=df[(df.open>0)&(df.low>0)&(df.high>=df.low)&(df.close>0)].sort_values("date").drop_duplicates("date")
    df["symbol"]=symbol
    return df.reset_index(drop=True)

def true_range(df):
    pc=df.close.shift(1)
    return pd.concat([(df.high-df.low),(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)

def rsi(close,p=14):
    d=close.diff()
    up=d.clip(lower=0).ewm(alpha=1/p,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/p,adjust=False).mean()
    rs=up/dn.replace(0,np.nan)
    return 100-100/(1+rs)

def rolling_pct_rank(s,window):
    return s.rolling(window,min_periods=max(20,window//4)).rank(pct=True)

def enrich_single(df:pd.DataFrame)->pd.DataFrame:
    x=df.copy()
    x["ret1"]=x.close.pct_change()
    for n in (2,4,8,16,32,64):
        x[f"ret{n}"]=x.close.pct_change(n)
    tr=true_range(x); x["atr14"]=tr.rolling(14,min_periods=14).mean()
    x["atrp"]=x.atr14/x.close
    for n in (8,16,32,64,96):
        x[f"rv{n}"]=x.ret1.rolling(n,min_periods=max(5,n//2)).std()
        hi=x.high.rolling(n,min_periods=n).max()
        lo=x.low.rolling(n,min_periods=n).min()
        x[f"pos{n}"]=(x.close-lo)/(hi-lo).replace(0,np.nan)
        ma=x.close.rolling(n,min_periods=n).mean()
        sd=x.close.rolling(n,min_periods=n).std()
        x[f"z{n}"]=(x.close-ma)/sd.replace(0,np.nan)
        x[f"high{n}prev"]=x.high.shift(1).rolling(n,min_periods=n).max()
        x[f"low{n}prev"]=x.low.shift(1).rolling(n,min_periods=n).min()
    for n in (8,16,32,64):
        e=x.close.ewm(span=n,adjust=False).mean()
        x[f"ema{n}"]=e
        x[f"ema{n}_dist"]=(x.close-e)/x.atr14
        x[f"ema{n}_slope"]=(e-e.shift(max(2,n//4)))/x.atr14
    x["rsi7"]=rsi(x.close,7); x["rsi14"]=rsi(x.close,14); x["rsi28"]=rsi(x.close,28)
    rng=(x.high-x.low).replace(0,np.nan)
    x["body_ratio"]=(x.close-x.open).abs()/rng
    x["upper_wick"]=(x.high-x[["open","close"]].max(axis=1))/rng
    x["lower_wick"]=(x[["open","close"]].min(axis=1)-x.low)/rng
    x["close_loc"]=(x.close-x.low)/rng
    x["atr_pctile20d"]=rolling_pct_rank(x.atrp,96*20)
    x["log_volume"]=np.log1p(x.volume.clip(lower=0))
    vm=x.log_volume.rolling(96,min_periods=32).mean(); vs=x.log_volume.rolling(96,min_periods=32).std()
    x["volume_z96"]=(x.log_volume-vm)/vs.replace(0,np.nan)
    h=x.date.dt.hour + x.date.dt.minute/60
    dow=x.date.dt.dayofweek
    x["hour_sin"]=np.sin(2*np.pi*h/24); x["hour_cos"]=np.cos(2*np.pi*h/24)
    x["dow_sin"]=np.sin(2*np.pi*dow/5); x["dow_cos"]=np.cos(2*np.pi*dow/5)
    x["hour"]=x.date.dt.hour
    x["dow"]=dow

    d=(x.set_index("date").resample("1D").agg(day_high=("high","max"),day_low=("low","min"),day_open=("open","first"),day_close=("close","last")).shift(1))
    q=d.reset_index()
    x=pd.merge_asof(x.sort_values("date"),q.sort_values("date"),on="date",direction="backward")
    x["pdh_dist"]=(x.close-x.day_high)/x.atr14
    x["pdl_dist"]=(x.close-x.day_low)/x.atr14

    tmp=x[["date","high","low"]].copy(); tmp["day"]=tmp.date.dt.floor("D"); tmp["hour0"]=tmp.date.dt.hour
    asia=(tmp[tmp.hour0<7].groupby("day").agg(asia_high=("high","max"),asia_low=("low","min")).reset_index())
    x["day"]=x.date.dt.floor("D")
    x=x.merge(asia,on="day",how="left")
    x.loc[x.hour<7,["asia_high","asia_low"]]=np.nan
    x["asia_high_dist"]=(x.close-x.asia_high)/x.atr14
    x["asia_low_dist"]=(x.close-x.asia_low)/x.atr14
    x["asia_ready"]=(x.hour>=7).astype(int)
    x.loc[x.asia_ready==0,["asia_high_dist","asia_low_dist"]]=0.0

    round_step=0.005
    x["round50"]=np.round(x.close/round_step)*round_step
    x["round50_dist"]=(x.close-x.round50)/x.atr14
    return x

def add_cross_features(frames:dict[str,pd.DataFrame])->dict[str,pd.DataFrame]:
    e=frames["EURUSD"][["date","close","ret1","ret4","ret16","ret32"]].rename(columns={c:f"eur_{c}" for c in ["close","ret1","ret4","ret16","ret32"]})
    g=frames["GBPUSD"][["date","close","ret1","ret4","ret16","ret32"]].rename(columns={c:f"gbp_{c}" for c in ["close","ret1","ret4","ret16","ret32"]})
    cross=pd.merge(e,g,on="date",how="inner")
    cross["ratio"]=cross.eur_close/cross.gbp_close
    for n in (4,16,32):
        cross[f"ratio_ret{n}"]=cross.ratio.pct_change(n)
        cross[f"common_ret{n}"]=(cross[f"eur_ret{n}"]+cross[f"gbp_ret{n}"])/2
    keep=["date"]+[c for c in cross.columns if c!="date"]
    out={}
    for s,x in frames.items():
        out[s]=pd.merge(x,cross[keep],on="date",how="left").sort_values("date").reset_index(drop=True)
        for n in (4,16,32):
            out[s][f"self_rel{n}"]=(out[s][f"eur_ret{n}"]-out[s][f"gbp_ret{n}"])*(1 if s=="EURUSD" else -1)
    return out

@dataclass(frozen=True)
class Rule:
    name:str
    family:str
    fn:Callable[[pd.DataFrame],np.ndarray]

def sgn(a): return np.where(a>0,1,np.where(a<0,-1,0)).astype(np.int8)

def build_rules()->list[Rule]:
    R=[]
    for lb in (4,8,16,32,64):
        for th in (0.0,0.5,1.0):
            def f(x,lb=lb,th=th):
                z=x[f"ret{lb}"]/(x.atrp*np.sqrt(max(lb,1)))
                return np.where(z>th,1,np.where(z<-th,-1,0))
            R.append(Rule(f"MOM_lb{lb}_th{th:g}","momentum",f))
    for lb in (8,16,32,64,96):
        for buf in (0.0,0.10):
            def f(x,lb=lb,buf=buf):
                u=x[f"high{lb}prev"]+buf*x.atr14; d=x[f"low{lb}prev"]-buf*x.atr14
                return np.where(x.close>u,1,np.where(x.close<d,-1,0))
            R.append(Rule(f"DON_lb{lb}_b{buf:g}","donchian",f))
    for lb in (16,32,64):
        for vp in (0.25,0.40):
            def f(x,lb=lb,vp=vp):
                u=x[f"high{lb}prev"]; d=x[f"low{lb}prev"]; compressed=x.atr_pctile20d.shift(1)<vp
                return np.where(compressed&(x.close>u),1,np.where(compressed&(x.close<d),-1,0))
            R.append(Rule(f"COMP_lb{lb}_vp{vp:g}","compression_breakout",f))
    for slow in (32,64):
        for tol in (0.25,0.50):
            def f(x,slow=slow,tol=tol):
                bull=x[f"ema{slow}_slope"]>0.20
                bear=x[f"ema{slow}_slope"]<-0.20
                rec_up=(x.close>x.ema8)&(x.low<=x.ema8+tol*x.atr14)
                rec_dn=(x.close<x.ema8)&(x.high>=x.ema8-tol*x.atr14)
                return np.where(bull&rec_up,1,np.where(bear&rec_dn,-1,0))
            R.append(Rule(f"PULL_s{slow}_t{tol:g}","trend_pullback",f))
    for lb in (16,32,64):
        for zt in (1.0,1.5,2.0):
            for gate in (0,1):
                def f(x,lb=lb,zt=zt,gate=gate):
                    z=x[f"z{lb}"]
                    calm=(x.ema64_slope.abs()<0.40) if gate else pd.Series(True,index=x.index)
                    return np.where(calm&(z<-zt),1,np.where(calm&(z>zt),-1,0))
                R.append(Rule(f"MRZ_lb{lb}_z{zt:g}_g{gate}","mean_reversion",f))
    for buf in (0.0,0.10):
        def f(x,buf=buf):
            prev=x.close.shift(1)
            up=(prev<=x.day_high)&(x.close>x.day_high+buf*x.atr14)
            dn=(prev>=x.day_low)&(x.close<x.day_low-buf*x.atr14)
            return np.where(up,1,np.where(dn,-1,0))
        R.append(Rule(f"PD_BREAK_b{buf:g}","prev_day_breakout",f))
    for wick in (0.0,0.10):
        def f(x,wick=wick):
            sh=(x.high>x.day_high+wick*x.atr14)&(x.close<x.day_high)
            lo=(x.low<x.day_low-wick*x.atr14)&(x.close>x.day_low)
            return np.where(lo,1,np.where(sh,-1,0))
        R.append(Rule(f"PD_FALSE_w{wick:g}","prev_day_falsebreak",f))
    for buf in (0.0,0.10,0.20):
        def f(x,buf=buf):
            ok=x.hour.between(7,10)
            prev=x.close.shift(1)
            up=ok&(prev<=x.asia_high)&(x.close>x.asia_high+buf*x.atr14)
            dn=ok&(prev>=x.asia_low)&(x.close<x.asia_low-buf*x.atr14)
            return np.where(up,1,np.where(dn,-1,0))
        R.append(Rule(f"ASIA_BR_b{buf:g}","asia_breakout",f))
    for hr in (7,8,12,13,16):
        for lb in (4,8,16):
            for mode in ("cont","rev"):
                def f(x,hr=hr,lb=lb,mode=mode):
                    d=sgn(x[f"ret{lb}"].fillna(0).to_numpy())
                    if mode=="rev": d=-d
                    return np.where(x.hour.to_numpy()==hr,d,0)
                R.append(Rule(f"SESS_{mode}_h{hr}_lb{lb}","session",f))
    for mode in ("revert","break"):
        for tol in (0.10,0.20):
            def f(x,mode=mode,tol=tol):
                lvl=x.round50
                near=(x.low<=lvl+tol*x.atr14)&(x.high>=lvl-tol*x.atr14)
                if mode=="revert":
                    return np.where(near&(x.close>lvl)&(x.open<lvl),1,np.where(near&(x.close<lvl)&(x.open>lvl),-1,0))
                prev=x.close.shift(1)
                return np.where((prev<=lvl)&(x.close>lvl+tol*x.atr14),1,np.where((prev>=lvl)&(x.close<lvl-tol*x.atr14),-1,0))
            R.append(Rule(f"ROUND_{mode}_t{tol:g}","round_number",f))
    for lb in (4,16,32):
        for th in (0.0,0.5):
            def f(x,lb=lb,th=th):
                selfr=x[f"ret{lb}"]; other=x[f"gbp_ret{lb}"] if (x.symbol.iloc[0]=="EURUSD") else x[f"eur_ret{lb}"]
                scale=x.atrp*np.sqrt(lb)
                up=(selfr>th*scale)&(other>0); dn=(selfr<-th*scale)&(other<0)
                return np.where(up,1,np.where(dn,-1,0))
            R.append(Rule(f"CROSS_CONFIRM_lb{lb}_t{th:g}","cross_confirm",f))
    for lb in (4,16,32):
        for th in (0.75,1.25):
            def f(x,lb=lb,th=th):
                rel=x[f"self_rel{lb}"]; common=x[f"common_ret{lb}"]; scale=x.atrp*np.sqrt(lb)
                quiet=common.abs()<0.75*scale
                return np.where(quiet&(rel<-th*scale),1,np.where(quiet&(rel>th*scale),-1,0))
            R.append(Rule(f"CROSS_FADE_lb{lb}_t{th:g}","cross_fade",f))
    return R

def simulate_config(df:pd.DataFrame, direction:np.ndarray, stop_mult:float, rr:float, cost_pips:float, horizon:int=HORIZON)->pd.DataFrame:
    n=len(df)
    idx=np.flatnonzero((direction!=0)&np.isfinite(df.atr14.to_numpy()))
    idx=idx[idx+1<n-horizon]
    if len(idx)==0: return pd.DataFrame()
    dirs=direction[idx].astype(int)
    entry_idx=idx+1
    entry=df.open.to_numpy()[entry_idx]
    atr=df.atr14.to_numpy()[idx]
    risk=stop_mult*atr
    valid=np.isfinite(entry)&np.isfinite(risk)&(risk>0)
    idx=idx[valid]; dirs=dirs[valid]; entry_idx=entry_idx[valid]; entry=entry[valid]; atr=atr[valid]; risk=risk[valid]
    if not len(idx): return pd.DataFrame()
    offsets=np.arange(0,horizon,dtype=int)
    mat_idx=entry_idx[:,None]+offsets[None,:]
    highs=df.high.to_numpy()[mat_idx]; lows=df.low.to_numpy()[mat_idx]
    target=entry+dirs*rr*risk
    stop=entry-dirs*risk
    hit_t=np.where(dirs[:,None]>0, highs>=target[:,None], lows<=target[:,None])
    hit_s=np.where(dirs[:,None]>0, lows<=stop[:,None], highs>=stop[:,None])
    any_t=hit_t.any(axis=1); any_s=hit_s.any(axis=1)
    first_t=np.where(any_t,hit_t.argmax(axis=1),horizon+1)
    first_s=np.where(any_s,hit_s.argmax(axis=1),horizon+1)
    win=any_t & (first_t<first_s)
    loss=any_s & (first_s<=first_t)
    exit_off=np.minimum(first_t,first_s)
    unresolved=~(win|loss)
    exit_off=np.where(unresolved,horizon-1,exit_off)
    exits=df.close.to_numpy()[entry_idx+exit_off]
    gross=np.where(win,rr,np.where(loss,-1,dirs*(exits-entry)/risk))
    cost_r=(cost_pips*PIP)/risk
    net=gross-cost_r
    status=np.where(win,"win",np.where(loss,"loss","timeout"))
    exit_idx=entry_idx+exit_off
    keep=[]; last_exit=-1
    for j,(sig_i,ex_i) in enumerate(zip(idx,exit_idx)):
        if sig_i>last_exit:
            keep.append(j); last_exit=int(ex_i)
    keep=np.asarray(keep,dtype=int)
    if not len(keep): return pd.DataFrame()
    sig_idx=idx[keep]
    out=pd.DataFrame({
        "signal_idx":sig_idx,
        "signal_time":df.date.to_numpy()[sig_idx],
        "entry_time":df.date.to_numpy()[entry_idx[keep]],
        "exit_time":df.date.to_numpy()[exit_idx[keep]],
        "direction":dirs[keep],
        "entry":entry[keep],
        "stop":stop[keep],
        "target":target[keep],
        "gross_r":gross[keep],
        "cost_r":cost_r[keep],
        "net_r":net[keep],
        "status":status[keep],
        "year":pd.DatetimeIndex(df.date.to_numpy()[sig_idx]).year,
        "month":pd.DatetimeIndex(df.date.to_numpy()[sig_idx]).to_period("M").astype(str),
        "hour":pd.DatetimeIndex(df.date.to_numpy()[sig_idx]).hour,
        "atr":atr[keep],
    })
    return out

def metrics(t:pd.DataFrame)->dict[str,float]:
    if t.empty:return {"n":0,"win_rate":np.nan,"mean_r":np.nan,"pf":np.nan,"sum_r":0.0}
    w=(t.net_r>0).mean()
    gains=t.loc[t.net_r>0,"net_r"].sum()
    losses=-t.loc[t.net_r<0,"net_r"].sum()
    return {"n":int(len(t)),"win_rate":float(w),"mean_r":float(t.net_r.mean()),"pf":float(gains/losses) if losses>0 else np.inf,"sum_r":float(t.net_r.sum())}

def split_metrics(t):
    out={}
    for name,mask in {
        "discover":t.year<=2016,
        "validate":t.year.between(2017,2020),
        "confirm":t.year.between(2021,2022),
        "prehold":t.year<=2022,
        "holdout":t.year>=2023,
    }.items(): out[name]=metrics(t[mask])
    return out

def prehold_pass(t:pd.DataFrame)->tuple[bool,dict]:
    p=t[t.year<=2022]; m=metrics(p)
    bysym={s:metrics(g) for s,g in p.groupby("symbol")}
    byyr=p[p.year.between(2017,2022)].groupby("year").net_r.mean()
    total=m["sum_r"]
    contrib=0
    if total>0 and not p.empty:
        annual=p.groupby("year").net_r.sum()
        contrib=float(annual.max()/total)
    stress_mean=float(p.stress_r.mean()) if "stress_r" in p else np.nan
    ok=(m["n"]>=300 and m["mean_r"]>0 and m["pf"]>1.10 and
        (m["win_rate"]>0.50 or m["mean_r"]>=0.10) and
        all(s in bysym and bysym[s]["mean_r"]>0 for s in ("EURUSD","GBPUSD")) and
        int((byyr>0).sum())>=4 and contrib<=0.45 and stress_mean>-0.03)
    return ok,{"pre":m,"pair":bysym,"positive_2017_22":int((byyr>0).sum()),"max_year_share":contrib,"stress_mean_r":stress_mean}

def block_boot_ci(t:pd.DataFrame,reps=1000,seed=SEED):
    if t.empty:return [np.nan,np.nan]
    rng=np.random.default_rng(seed)
    groups=[g.net_r.to_numpy() for _,g in t.groupby("month") if len(g)]
    if len(groups)<3:return [np.nan,np.nan]
    vals=[]
    for _ in range(reps):
        sel=rng.integers(0,len(groups),len(groups))
        z=np.concatenate([groups[i] for i in sel])
        vals.append(z.mean())
    return [float(np.quantile(vals,.025)),float(np.quantile(vals,.975))]

def robustness_score(t):
    p=t[t.year<=2022]
    ym=p.groupby("year").net_r.mean()
    m=metrics(p); ci=block_boot_ci(p,500)
    return float((np.nanmedian(ym) if len(ym) else -9) + 0.45*ci[0] + 0.08*(m["pf"]-1) + 0.08*(m["win_rate"]-.5) + 0.003*np.log1p(m["n"]))

def to_events(raw):
    a=np.asarray(raw,dtype=np.int8)
    prev=np.r_[0,a[:-1]]
    return np.where((a!=0)&(a!=prev),a,0).astype(np.int8)

def evaluate_rules(frames:dict[str,pd.DataFrame],outdir:Path):
    rules=build_rules()
    rows=[]; trade_cache={}
    total=0
    for ri,rule in enumerate(rules,1):
        dir_map={s:to_events(rule.fn(df)) for s,df in frames.items()}
        for sm in STOP_GRID:
            for rr in RR_GRID:
                total+=1; ts=[]
                for s,df in frames.items():
                    b=simulate_config(df,dir_map[s],sm,rr,BASE_COST[s])
                    if b.empty: continue
                    b["symbol"]=s
                    b["stress_r"]=b.gross_r-(STRESS_COST[s]*PIP)/(sm*b.atr)
                    ts.append(b)
                if not ts: continue
                t=pd.concat(ts,ignore_index=True).sort_values("signal_time")
                pre=metrics(t[t.year<=2022])
                ok,detail=prehold_pass(t)
                row={"kind":"rule","name":rule.name,"family":rule.family,"stop_atr":sm,"rr":rr,"tested_id":total,
                     **{f"pre_{k}":v for k,v in pre.items()},
                     "pre_stress_mean_r":detail["stress_mean_r"],"pre_positive_years_2017_22":detail["positive_2017_22"],
                     "pre_max_year_share":detail["max_year_share"],"pre_pass":ok}
                if ok: row["robust_score"]=robustness_score(t)
                else: row["robust_score"]=-999.0
                rows.append(row)
                if ok: trade_cache[(rule.name,sm,rr)]=t
        if ri%10==0: print(f"rule families processed {ri}/{len(rules)}",flush=True)
    rank=pd.DataFrame(rows).sort_values(["pre_pass","robust_score","pre_mean_r","pre_win_rate"],ascending=[False,False,False,False])
    rank.to_csv(outdir/"v36_rule_grid.csv",index=False)
    return rank,trade_cache,len(rules),total

FEATURES=[
    "ret1","ret2","ret4","ret8","ret16","ret32","ret64","atrp","rv8","rv16","rv32","rv64",
    "pos16","pos32","pos64","pos96","z16","z32","z64","ema8_dist","ema16_dist","ema32_dist","ema64_dist",
    "ema16_slope","ema32_slope","ema64_slope","rsi7","rsi14","rsi28","body_ratio","upper_wick","lower_wick",
    "close_loc","pdh_dist","pdl_dist","asia_high_dist","asia_low_dist","asia_ready","round50_dist","log_volume","volume_z96","hour_sin","hour_cos","dow_sin","dow_cos",
    "eur_ret4","eur_ret16","eur_ret32","gbp_ret4","gbp_ret16","gbp_ret32","ratio_ret4","ratio_ret16","ratio_ret32",
    "common_ret4","common_ret16","common_ret32","self_rel4","self_rel16","self_rel32"
]

def barrier_label(df,sm,rr):
    n=len(df); idx=np.arange(0,n-HORIZON-1)
    entry=df.open.to_numpy()[idx+1]; atr=df.atr14.to_numpy()[idx]; risk=sm*atr
    mat=(idx+1)[:,None]+np.arange(HORIZON)[None,:]
    hi=df.high.to_numpy()[mat]; lo=df.low.to_numpy()[mat]
    lt=entry[:,None]+rr*risk[:,None]; ls=entry[:,None]-risk[:,None]
    st=entry[:,None]-rr*risk[:,None]; ss=entry[:,None]+risk[:,None]
    lh=hi>=lt; lstop=lo<=ls; sh=lo<=st; sstop=hi>=ss
    def first(a):
        any_=a.any(1); return np.where(any_,a.argmax(1),HORIZON+1)
    flt,fls,fst,fss=first(lh),first(lstop),first(sh),first(sstop)
    longwin=flt<fls; shortwin=fst<fss
    longtime=np.where(longwin,flt,HORIZON+2)
    shorttime=np.where(shortwin,fst,HORIZON+2)
    y=np.zeros(n,dtype=np.int8)
    y[idx[longtime<shorttime]]=1
    y[idx[shorttime<longtime]]=-1
    return y

def ml_walkforward(frames:dict[str,pd.DataFrame],outdir:Path):
    model_grid=[(sm,rr) for sm in (0.75,1.0,1.25) for rr in (0.75,1.0,1.25,1.5)]
    thresholds=(0.55,0.60,0.65,0.70)
    allframes=[]
    for s,x in frames.items():
        z=x.copy(); z["symbol_code"]=0 if s=="EURUSD" else 1; allframes.append(z)
    base=pd.concat(allframes,ignore_index=True).sort_values(["date","symbol"]).reset_index(drop=True)
    labelmaps={}
    for sm,rr in model_grid:
        pieces=[]
        for s,x in frames.items():
            q=pd.DataFrame({"date":x.date,"symbol":s,"y":barrier_label(x,sm,rr)})
            pieces.append(q)
        labelmaps[(sm,rr)]=pd.concat(pieces,ignore_index=True)
    mlrows=[]; cache={}; test_count=0
    for sm,rr in model_grid:
        lab=labelmaps[(sm,rr)]
        z=base.merge(lab,on=["date","symbol"],how="left")
        feats=FEATURES+["symbol_code"]
        preds=np.full(len(z),np.nan)
        for year in range(2013,2026):
            tr=(z.date.dt.year<=year-1)&(z.date.dt.year>=2005)&z[feats].notna().all(axis=1)&z.y.ne(0)
            te=(z.date.dt.year==year)&z[feats].notna().all(axis=1)
            if tr.sum()<5000 or te.sum()==0: continue
            X=z.loc[tr,feats]; y=(z.loc[tr,"y"]>0).astype(int)
            model=LGBMClassifier(
                n_estimators=120,learning_rate=.04,num_leaves=15,max_depth=5,
                min_child_samples=200,subsample=.8,colsample_bytree=.8,reg_lambda=1.0,
                random_state=SEED,n_jobs=2,verbosity=-1
            )
            model.fit(X,y)
            preds[te]=model.predict_proba(z.loc[te,feats])[:,1]
        z["p_long"]=preds
        for th in thresholds:
            test_count+=1; ts=[]
            for s,df in frames.items():
                q=z[z.symbol==s][["date","p_long"]].dropna()
                pmap=pd.Series(q.p_long.to_numpy(),index=q.date)
                pvals=df.date.map(pmap).to_numpy(float)
                d=np.where(pvals>=th,1,np.where(pvals<=1-th,-1,0)).astype(np.int8)
                d=to_events(d)
                b=simulate_config(df,d,sm,rr,BASE_COST[s])
                if b.empty:continue
                b["symbol"]=s
                b["stress_r"]=b.gross_r-(STRESS_COST[s]*PIP)/(sm*b.atr)
                ts.append(b)
            if not ts:continue
            t=pd.concat(ts,ignore_index=True).sort_values("signal_time")
            pre=metrics(t[t.year<=2022]); ok,detail=prehold_pass(t)
            name=f"ML_LGBM_sm{sm:g}_rr{rr:g}_p{th:g}"
            row={"kind":"ml","name":name,"family":"ml_meta","stop_atr":sm,"rr":rr,"threshold":th,
                 **{f"pre_{k}":v for k,v in pre.items()},
                 "pre_stress_mean_r":detail["stress_mean_r"],"pre_positive_years_2017_22":detail["positive_2017_22"],
                 "pre_max_year_share":detail["max_year_share"],"pre_pass":ok,
                 "robust_score":robustness_score(t) if ok else -999.0}
            mlrows.append(row)
            if ok:cache[(name,sm,rr,th)]=t
        print(f"ML barrier {sm} ATR / {rr}R complete",flush=True)
    rank=pd.DataFrame(mlrows).sort_values(["pre_pass","robust_score","pre_mean_r"],ascending=[False,False,False])
    rank.to_csv(outdir/"v36_ml_grid.csv",index=False)
    return rank,cache,test_count

def holdout_gate(t:pd.DataFrame):
    h=t[t.year>=2023]; m=metrics(h)
    pair={s:metrics(g) for s,g in h.groupby("symbol")}
    yr=h.groupby("year").net_r.mean()
    stress=float(h.stress_r.mean()) if len(h) else np.nan
    ci=block_boot_ci(h,1500,SEED+9)
    monthly=h.groupby("month").net_r.sum()
    concentration=float(monthly.max()/m["sum_r"]) if m["sum_r"]>0 and len(monthly) else np.nan
    base=(m["n"]>=120 and all(s in pair and pair[s]["n"]>=40 for s in ("EURUSD","GBPUSD")) and
          m["mean_r"]>=.05 and m["pf"]>=1.10 and m["win_rate"]>=.52 and
          all(pair[s]["mean_r"]>0 for s in ("EURUSD","GBPUSD")) and int((yr>0).sum())>=2 and
          stress>=0 and ci[0]>-.02 and (not np.isfinite(concentration) or concentration<.50))
    strong=base and m["mean_r"]>=.10 and m["pf"]>=1.20 and ci[0]>0
    return ("PROMOTE" if strong else "WATCHLIST" if base else "REJECT"),{"metrics":m,"pair":pair,"positive_years":int((yr>0).sum()),"stress_mean_r":stress,"bootstrap95":ci,"max_month_share":concentration}

def neighborhood_check(rank:pd.DataFrame,row:pd.Series):
    q=rank[(rank["kind"]==row["kind"])]
    if row["kind"]=="rule":
        q=q[q.name==row["name"]]
    else:
        q=q[q.family=="ml_meta"]
    q=q[(q.stop_atr.sub(row.stop_atr).abs()<=.26)&(q.rr.sub(row.rr).abs()<=.26)]
    if q.empty:return {"n":0,"positive_share":np.nan}
    return {"n":int(len(q)),"positive_share":float((q.pre_mean_r>0).mean())}

def save_summary(outdir,rule_rank,ml_rank,rule_cache,ml_cache,nrules,rule_tests,ml_tests):
    ranks=pd.concat([rule_rank,ml_rank],ignore_index=True,sort=False).sort_values(["pre_pass","robust_score","pre_mean_r"],ascending=[False,False,False])
    ranks.to_csv(outdir/"v36_all_candidates.csv",index=False)
    survivors=ranks[ranks.pre_pass==True].copy()
    result={"protocol":"V3.6 zero-base frozen","base_rule_count":int(nrules),"rule_exit_configs_tested":int(rule_tests),"ml_configs_tested":int(ml_tests),"total_configs_tested":int(rule_tests+ml_tests),"prehold_survivors":int(len(survivors))}
    if survivors.empty:
        result.update({"selected":None,"holdout_status":"REJECT","reason":"No pre-2023 candidate cleared the preregistered robustness gate; final holdout not used for rescue."})
    else:
        sel=survivors.iloc[0]
        if sel.kind=="rule": t=rule_cache[(sel["name"],float(sel.stop_atr),float(sel.rr))]
        else: t=ml_cache[(sel["name"],float(sel.stop_atr),float(sel.rr),float(sel.threshold))]
        status,gate=holdout_gate(t)
        neigh=neighborhood_check(ranks,sel)
        t.to_csv(outdir/"v36_selected_trades.csv",index=False)
        result.update({"selected":{k:(v.item() if hasattr(v,"item") else v) for k,v in sel.dropna().to_dict().items()},
                       "holdout_status":status,"holdout_gate":gate,"parameter_neighborhood":neigh})
        if status=="PROMOTE" and (not np.isfinite(neigh["positive_share"]) or neigh["positive_share"]<.50):
            result["holdout_status"]="WATCHLIST"
            result["reason"]="Holdout passed strong metrics but parameter-neighborhood stability was insufficient."
    (outdir/"v36_summary.json").write_text(json.dumps(result,indent=2,default=str))
    return result,ranks

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-dir",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    frames={}
    for s in ("EURUSD","GBPUSD"):
        p=args.data_dir/f"{s.lower()}-m15.json"
        frames[s]=enrich_single(load_duka(p,s))
        frames[s]=frames[s][frames[s].date.dt.year.between(2005,2025)].reset_index(drop=True)
        print(s,len(frames[s]),frames[s].date.min(),frames[s].date.max(),flush=True)
    frames=add_cross_features(frames)
    rr,rc,nrules,rule_tests=evaluate_rules(frames,args.out)
    mr,mc,ml_tests=ml_walkforward(frames,args.out)
    result,ranks=save_summary(args.out,rr,mr,rc,mc,nrules,rule_tests,ml_tests)
    print(json.dumps(result,indent=2,default=str))
    print("\nTOP 25 PRE-HOLDOUT CANDIDATES")
    cols=[c for c in ["kind","name","family","stop_atr","rr","threshold","pre_n","pre_win_rate","pre_mean_r","pre_pf","pre_stress_mean_r","pre_pass","robust_score"] if c in ranks.columns]
    print(ranks[cols].head(25).to_string(index=False))

if __name__=="__main__": main()
