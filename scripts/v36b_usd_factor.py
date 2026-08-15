from __future__ import annotations
import argparse,json,sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

UNIVERSE=("EURUSD","GBPUSD","AUDUSD","NZDUSD","USDJPY","USDCHF","USDCAD")
TARGETS=("EURUSD","GBPUSD")
# +1 means raw quote return rises when USD strengthens; -1 means invert raw return.
USD_SIGN={"EURUSD":-1,"GBPUSD":-1,"AUDUSD":-1,"NZDUSD":-1,"USDJPY":1,"USDCHF":1,"USDCAD":1}

@dataclass(frozen=True)
class FRule:
    name:str; family:str; fn:Callable[[pd.DataFrame,str],np.ndarray]; lb:int

def load_all(d:Path):
    out={}
    for s in UNIVERSE:
        p=d/f"{s.lower()}-m15.json"
        x=q.enrich_single(q.load_duka(p,s))
        x=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
        out[s]=x
        print(s,len(x),x.date.min(),x.date.max(),flush=True)
    return out

def factor_table(frames):
    # Intersection prevents a stale component from silently carrying forward.
    z=None
    for s,x in frames.items():
        y=x[["date","close"]].copy().rename(columns={"close":f"{s}_close"})
        z=y if z is None else z.merge(y,on="date",how="inner")
    z=z.sort_values("date").reset_index(drop=True)
    for s in UNIVERSE:
        c=z[f"{s}_close"]
        z[f"{s}_usd1"]=USD_SIGN[s]*c.pct_change()
        for lb in (4,8,16,32,64,96): z[f"{s}_usd{lb}"]=USD_SIGN[s]*c.pct_change(lb)
    for target in TARGETS:
        comps=[s for s in UNIVERSE if s!=target]
        one=z[[f"{s}_usd1" for s in comps]]
        z[f"{target}_factor1"]=one.mean(axis=1)
        vol=z[f"{target}_factor1"].rolling(96,min_periods=48).std()
        for lb in (4,8,16,32,64,96):
            mat=z[[f"{s}_usd{lb}" for s in comps]]
            f=mat.mean(axis=1)
            z[f"{target}_fac{lb}"]=f
            z[f"{target}_breadth{lb}"]=(np.sign(mat).eq(np.sign(f),axis=0)).mean(axis=1)
            z[f"{target}_disp{lb}"]=mat.std(axis=1)
            z[f"{target}_mag{lb}"]=f/(vol*np.sqrt(lb)).replace(0,np.nan)
            z[f"{target}_resid{lb}"]=z[f"{target}_usd{lb}"]-f
            # trailing, causal regime percentiles
            z[f"{target}_disp_pct{lb}"]=z[f"{target}_disp{lb}"].rolling(96*20,min_periods=300).rank(pct=True)
            z[f"{target}_vol_pct{lb}"]=vol.rolling(96*20,min_periods=300).rank(pct=True)
    return z

def attach_factor(frames,f):
    out={}
    cols=[c for c in f.columns if c=="date" or c.startswith("EURUSD_") or c.startswith("GBPUSD_")]
    for s in TARGETS:
        out[s]=frames[s].merge(f[cols],on="date",how="inner").sort_values("date").reset_index(drop=True)
    return out

def d_from_usd(f):
    # positive USD factor -> short EURUSD/GBPUSD
    return np.where(f>0,-1,np.where(f<0,1,0)).astype(np.int8)

def build_rules():
    R=[]
    lbs=(4,8,16,32,64,96); brs=(.57,.71,.86); mags=(0,.5,1.0)
    for lb in lbs:
        for br in brs:
            for mag in mags:
                def fn(x,s,lb=lb,br=br,mag=mag):
                    f=x[f"{s}_fac{lb}"]; ok=(x[f"{s}_breadth{lb}"]>=br)&(x[f"{s}_mag{lb}"].abs()>=mag)
                    return np.where(ok,d_from_usd(f),0)
                R.append(FRule(f"FAC_CONT_lb{lb}_b{br:.2f}_m{mag:g}","factor_continuation",fn,lb))
                def rev(x,s,lb=lb,br=br,mag=mag):
                    f=x[f"{s}_fac{lb}"]; ok=(x[f"{s}_breadth{lb}"]>=br)&(x[f"{s}_mag{lb}"].abs()>=mag)
                    return np.where(ok,-d_from_usd(f),0)
                R.append(FRule(f"FAC_REV_lb{lb}_b{br:.2f}_m{mag:g}","factor_reversal_control",rev,lb))
    for lb in (4,8,16,32):
        for longlb in (32,64,96):
            if longlb<=lb:continue
            for br in (.57,.71):
                def fn(x,s,lb=lb,longlb=longlb,br=br):
                    a=x[f"{s}_fac{lb}"]; b=x[f"{s}_fac{longlb}"]; ok=(x[f"{s}_breadth{lb}"]>=br)&(np.sign(a)==np.sign(b))
                    return np.where(ok,d_from_usd(a),0)
                R.append(FRule(f"FAC_PERSIST_{lb}_{longlb}_b{br:.2f}","factor_persistence",fn,lb))
    for lb in lbs:
        for br in (.57,.71):
            def fn(x,s,lb=lb,br=br):
                f=x[f"{s}_fac{lb}"]; own=x[f"{s}_usd{lb}"]; ok=(x[f"{s}_breadth{lb}"]>=br)&(np.sign(f)==np.sign(own))
                return np.where(ok,d_from_usd(f),0)
            R.append(FRule(f"FAC_CONFIRM_lb{lb}_b{br:.2f}","target_confirmation",fn,lb))
    for lb in (8,16,32,64):
        for br in (.57,.71):
            for th in (.5,1.0):
                def fn(x,s,lb=lb,br=br,th=th):
                    f=x[f"{s}_fac{lb}"]; resid=x[f"{s}_resid{lb}"]; scale=x.atrp*np.sqrt(lb)
                    catch=(np.sign(f)*resid)<(-th*scale)
                    ok=(x[f"{s}_breadth{lb}"]>=br)&catch
                    return np.where(ok,d_from_usd(f),0)
                R.append(FRule(f"FAC_CATCHUP_lb{lb}_b{br:.2f}_r{th:g}","residual_catchup",fn,lb))
    for lb in (8,16,32,64):
        for regime,name in [((0,.333),"low"),((.333,.667),"mid"),((.667,1.01),"high")]:
            lo,hi=regime
            for kind in ("disp","vol"):
                def fn(x,s,lb=lb,lo=lo,hi=hi,kind=kind):
                    f=x[f"{s}_fac{lb}"]; pct=x[f"{s}_{kind}_pct{lb}"]; ok=(x[f"{s}_breadth{lb}"]>=.71)&pct.ge(lo)&pct.lt(hi)
                    return np.where(ok,d_from_usd(f),0)
                R.append(FRule(f"FAC_{kind.upper()}_{name}_lb{lb}",f"{kind}_regime",fn,lb))
    sessions={"asia":(0,7),"london":(7,12),"overlap":(12,16),"newyork":(16,21)}
    for lb in (8,16,32,64):
        for name,(a,b) in sessions.items():
            def fn(x,s,lb=lb,a=a,b=b):
                f=x[f"{s}_fac{lb}"]; ok=(x[f"{s}_breadth{lb}"]>=.71)&x.hour.ge(a)&x.hour.lt(b)
                return np.where(ok,d_from_usd(f),0)
            R.append(FRule(f"FAC_SESSION_{name}_lb{lb}","session_factor",fn,lb))
    return R

def events(a): return q.to_events(a)

def evaluate(frames,outdir):
    rules=build_rules(); rows=[]; cache={}; tested=0
    for i,r in enumerate(rules,1):
        dm={s:events(r.fn(frames[s],s)) for s in TARGETS}
        for sm in q.STOP_GRID:
            for rr in q.RR_GRID:
                tested+=1; ts=[]
                for s in TARGETS:
                    b=q.simulate_config(frames[s],dm[s],sm,rr,q.BASE_COST[s])
                    if b.empty:continue
                    b["symbol"]=s; b["stress_r"]=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*b.atr); ts.append(b)
                if not ts:continue
                t=pd.concat(ts,ignore_index=True).sort_values("signal_time")
                pre=q.metrics(t[t.year<=2022]); ok,det=q.prehold_pass(t)
                row={"kind":"factor","name":r.name,"family":r.family,"lookback":r.lb,"stop_atr":sm,"rr":rr,
                     **{f"pre_{k}":v for k,v in pre.items()},"pre_stress_mean_r":det["stress_mean_r"],
                     "pre_positive_years_2017_22":det["positive_2017_22"],"pre_max_year_share":det["max_year_share"],
                     "pre_pass":ok,"robust_score":q.robustness_score(t) if ok else -999.0}
                rows.append(row)
                if ok:cache[(r.name,sm,rr)]=(t,r)
        if i%20==0:print(f"factor rules {i}/{len(rules)}",flush=True)
    rank=pd.DataFrame(rows).sort_values(["pre_pass","robust_score","pre_mean_r","pre_win_rate"],ascending=[False,False,False,False])
    rank.to_csv(outdir/"v36b_factor_grid.csv",index=False)
    return rank,cache,rules,tested

def target_only_comparator(frames,rule:FRule,sm,rr):
    ts=[]
    lb=rule.lb
    for s in TARGETS:
        x=frames[s]
        own=x[f"{s}_usd{lb}"]
        d=events(d_from_usd(own))
        b=q.simulate_config(x,d,sm,rr,q.BASE_COST[s])
        if b.empty:continue
        b["symbol"]=s;b["stress_r"]=b.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*b.atr);ts.append(b)
    return pd.concat(ts,ignore_index=True).sort_values("signal_time") if ts else pd.DataFrame()

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    raw=load_all(a.data_dir); fac=factor_table(raw); frames=attach_factor(raw,fac)
    rank,cache,rules,tested=evaluate(frames,a.out)
    surv=rank[rank.pre_pass==True]
    result={"protocol":"V3.6B systematic USD factor frozen","rule_templates":len(rules),"configs_tested":tested,"prehold_survivors":len(surv)}
    if surv.empty:
        result.update({"selected":None,"holdout_status":"REJECT","reason":"No pre-2023 systematic USD-factor candidate cleared the frozen gate."})
    else:
        sel=surv.iloc[0];t,rule=cache[(sel["name"],float(sel.stop_atr),float(sel.rr))]
        status,gate=q.holdout_gate(t);comp=target_only_comparator(frames,rule,float(sel.stop_atr),float(sel.rr))
        t.to_csv(a.out/"v36b_selected_trades.csv",index=False)
        result.update({"selected":{k:(v.item() if hasattr(v,"item") else v) for k,v in sel.dropna().to_dict().items()},"holdout_status":status,"holdout_gate":gate,
                       "target_only_prehold":q.metrics(comp[comp.year<=2022]) if not comp.empty else None,
                       "target_only_holdout":q.metrics(comp[comp.year>=2023]) if not comp.empty else None})
    (a.out/"v36b_summary.json").write_text(json.dumps(result,indent=2,default=str))
    print(json.dumps(result,indent=2,default=str));print(rank.head(25).to_string(index=False))

if __name__=="__main__":main()
