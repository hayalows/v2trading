from __future__ import annotations

"""V2 v2.6 conditional POI-depth research.

Research only. The policy is selected chronologically using information known at BOS:
symbol, session, POI width/ATR, BOS displacement/ATR and sweep-to-BOS speed.
It never uses future POI-touch state to choose entry depth.
"""

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

BASELINE = 0.50
CANDIDATES = np.array([0.20,0.30,0.40,0.50,0.60,0.65,0.75,0.85])
TEST_YEARS = (2022,2023,2024,2025)
MIN_COMMON = 120
MIN_CONTEXT_SETUPS = 90
MIN_DELTA_R = 0.005
MAX_TRAIN_AMBIGUITY = 0.45
BOOT_REPS = 3000
SEED = 2601


def neutral_r(r: pd.Series) -> float:
    if not bool(r.risk_valid): return 0.0
    if str(r.outcome_m5) == 'win': return 2.5
    if str(r.outcome_m5) == 'loss': return -1.0
    return 0.0


def pessimistic_r(r: pd.Series) -> float:
    if not bool(r.risk_valid): return 0.0
    o=str(r.outcome_m5)
    if o=='win': return 2.5
    if o=='loss': return -1.0
    if bool(r.filled): return -1.0
    return 0.0


def prep(x: pd.DataFrame) -> pd.DataFrame:
    x=x.copy()
    x['depth']=pd.to_numeric(x.depth,errors='coerce').round(2)
    x['year']=pd.to_numeric(x.year,errors='coerce').astype('Int64')
    x['risk_valid']=x.risk_valid.astype(str).str.lower().eq('true') if x.risk_valid.dtype==object else x.risk_valid.astype(bool)
    x['filled']=x.filled.astype(str).str.lower().eq('true') if x.filled.dtype==object else x.filled.astype(bool)
    for c in ['zone_width_atr','bos_displacement_atr','sweep_to_bos_bars']:
        x[c]=pd.to_numeric(x[c],errors='coerce')
    x['neutral_r']=x.apply(neutral_r,axis=1)
    x['pess_r']=x.apply(pessimistic_r,axis=1)
    return x


def thresholds(train: pd.DataFrame) -> dict:
    b=train[np.isclose(train.depth,BASELINE)].drop_duplicates('setup_id')
    def med(c,default):
        v=pd.to_numeric(b[c],errors='coerce').dropna()
        return float(v.median()) if len(v) else default
    return {'width':med('zone_width_atr',0.5),'bos':med('bos_displacement_atr',0.2),'speed':med('sweep_to_bos_bars',4)}


def add_bins(x: pd.DataFrame, th: dict) -> pd.DataFrame:
    z=x.copy()
    z['width_bin']=np.where(z.zone_width_atr<=th['width'],'narrow','wide')
    z['bos_bin']=np.where(z.bos_displacement_atr>=th['bos'],'strong_bos','soft_bos')
    z['speed_bin']=np.where(z.sweep_to_bos_bars<=th['speed'],'fast_bos','slow_bos')
    return z


def paired_depth(train: pd.DataFrame, depth: float) -> dict | None:
    a=train[np.isclose(train.depth,depth)].set_index('setup_id')
    b=train[np.isclose(train.depth,BASELINE)].set_index('setup_id')
    ids=a.index.intersection(b.index)
    if len(ids)<MIN_COMMON:return None
    aa=a.loc[ids];bb=b.loc[ids]
    # Compare opportunity per setup, including no-fill/invalid as zero. This avoids
    # rewarding a depth merely by changing the risk-valid denominator.
    d=(aa.neutral_r-bb.neutral_r).to_numpy(float)
    amb=(aa.risk_valid & aa.filled & ~aa.outcome_m5.isin(['win','loss'])).mean()
    mean=float(d.mean());se=float(d.std(ddof=1)/np.sqrt(len(d))) if len(d)>1 else np.inf
    return {'depth':float(depth),'n':int(len(d)),'delta':mean,'lower95':mean-1.96*se,'ambiguity':float(amb)}


def choose(train: pd.DataFrame) -> tuple[float,dict]:
    rows=[]
    for d in CANDIDATES:
        q=paired_depth(train,float(d))
        if q:rows.append(q)
    mid={'depth':BASELINE,'n':0,'delta':0.0,'lower95':0.0,'ambiguity':0.0}
    viable=[r for r in rows if r['depth']!=BASELINE and r['delta']>=MIN_DELTA_R and r['lower95']>=-0.01 and r['ambiguity']<=MAX_TRAIN_AMBIGUITY]
    if not viable:return BASELINE,{'decision':'fallback_midpoint','candidates':rows}
    viable.sort(key=lambda r:(r['delta'],r['lower95'],-abs(r['depth']-BASELINE)),reverse=True)
    best=viable[0]
    return float(best['depth']),{'decision':'conditional_depth','selected':best,'candidates':rows}


def subset_for_level(train: pd.DataFrame,row: pd.Series,level: str) -> pd.DataFrame:
    if level=='full':
        return train[(train.symbol==row.symbol)&(train.session==row.session)&(train.width_bin==row.width_bin)&(train.bos_bin==row.bos_bin)&(train.speed_bin==row.speed_bin)]
    if level=='symbol_session':return train[(train.symbol==row.symbol)&(train.session==row.session)]
    if level=='symbol':return train[train.symbol==row.symbol]
    return train


def policy_for_setup(train: pd.DataFrame,row: pd.Series) -> tuple[float,str,dict]:
    for level in ['full','symbol_session','symbol','global']:
        q=subset_for_level(train,row,level)
        setups=q.setup_id.nunique()
        if setups<MIN_CONTEXT_SETUPS:continue
        d,meta=choose(q)
        if d!=BASELINE:return d,level,{'trainSetups':int(setups),**meta}
        # A sufficiently sampled full context that does not clear the gate should
        # explicitly fall back to midpoint rather than shopping broader contexts.
        if level in ('full','symbol_session'):
            return BASELINE,level,{'trainSetups':int(setups),**meta}
    return BASELINE,'global_fallback',{'trainSetups':int(train.setup_id.nunique()),'decision':'fallback_midpoint'}


def eval_year(all_rows: pd.DataFrame,year: int) -> tuple[pd.DataFrame,dict]:
    train0=all_rows[all_rows.year<year].copy();test0=all_rows[all_rows.year==year].copy()
    th=thresholds(train0);train=add_bins(train0,th);test=add_bins(test0,th)
    base=test[np.isclose(test.depth,BASELINE)].drop_duplicates('setup_id').set_index('setup_id')
    decisions=[]
    for sid,row in base.iterrows():
        d,level,meta=policy_for_setup(train,row)
        candidate=test[(test.setup_id==sid)&np.isclose(test.depth,d)]
        if candidate.empty: candidate=test[(test.setup_id==sid)&np.isclose(test.depth,BASELINE)]
        c=candidate.iloc[0]
        decisions.append({'year':year,'setup_id':sid,'symbol':row.symbol,'session':row.session,'width_bin':row.width_bin,'bos_bin':row.bos_bin,'speed_bin':row.speed_bin,'selected_depth':float(d),'level':level,'candidate_r':float(c.neutral_r),'baseline_r':float(row.neutral_r),'candidate_pess_r':float(c.pess_r),'baseline_pess_r':float(row.pess_r),'delta_r':float(c.neutral_r-row.neutral_r),'delta_pess_r':float(c.pess_r-row.pess_r),'candidate_filled':bool(c.filled),'baseline_filled':bool(row.filled),'candidate_outcome':str(c.outcome_m5),'baseline_outcome':str(row.outcome_m5),'meta':json.dumps(meta,separators=(',',':'))})
    d=pd.DataFrame(decisions)
    depths=d.selected_depth.value_counts(normalize=True).sort_index().to_dict() if len(d) else {}
    s={'year':year,'n':int(len(d)),'meanCandidateR':float(d.candidate_r.mean()) if len(d) else None,'meanMidpointR':float(d.baseline_r.mean()) if len(d) else None,'deltaR':float(d.delta_r.mean()) if len(d) else None,'pessimisticDeltaR':float(d.delta_pess_r.mean()) if len(d) else None,'candidateFillRate':float(d.candidate_filled.mean()) if len(d) else None,'midpointFillRate':float(d.baseline_filled.mean()) if len(d) else None,'depthMix':{str(k):float(v) for k,v in depths.items()},'thresholds':th}
    return d,s


def bootstrap(x: np.ndarray) -> dict:
    if not len(x):return {'n':0,'mean':None,'low95':None,'high95':None}
    rng=np.random.default_rng(SEED);vals=np.empty(BOOT_REPS)
    for i in range(BOOT_REPS):vals[i]=x[rng.integers(0,len(x),len(x))].mean()
    return {'n':int(len(x)),'mean':float(x.mean()),'low95':float(np.quantile(vals,.025)),'high95':float(np.quantile(vals,.975)),'reps':BOOT_REPS,'seed':SEED}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    x=prep(pd.read_csv(a.input));x=x[x.year.notna()].copy();all_dec=[];years=[]
    for y in TEST_YEARS:
        d,s=eval_year(x,y)
        if len(d):all_dec.append(d);years.append(s)
    dec=pd.concat(all_dec,ignore_index=True) if all_dec else pd.DataFrame();neutral=bootstrap(dec.delta_r.to_numpy(float) if len(dec) else np.array([]));pess=bootstrap(dec.delta_pess_r.to_numpy(float) if len(dec) else np.array([]))
    noninferior=sum(1 for y in years if y['deltaR'] is not None and y['deltaR']>=-0.01)
    robust=bool(neutral['low95'] is not None and neutral['low95']>0 and pess['mean'] is not None and pess['mean']>=0 and noninferior>=3)
    result={'study':'V2 v2.6 conditional POI depth','generatedAt':pd.Timestamp.utcnow().isoformat(),'protocol':{'baselineDepth':BASELINE,'candidateDepths':CANDIDATES.tolist(),'featuresKnownAtBos':['symbol','session','zone_width_atr','bos_displacement_atr','sweep_to_bos_bars'],'testYears':list(TEST_YEARS),'chronological':True,'minCommonForDepthComparison':MIN_COMMON,'minContextSetups':MIN_CONTEXT_SETUPS,'automaticPromotion':False},'yearly':years,'pooledNeutral':neutral,'pooledPessimistic':pess,'noninferiorYears':noninferior,'robustPromotionGate':robust,'decision':'CONDITIONAL_DEPTH_CHALLENGER_PASSES_RESEARCH_GATE' if robust else 'KEEP_50_MIDPOINT_BASELINE','boundary':'Public M5 OHLC still cannot prove broker execution or eliminate same-M5 ordering ambiguity.'}
    dec.to_csv(a.out/'v26_conditional_poi_depth_decisions.csv',index=False)
    (a.out/'v26_conditional_poi_depth_summary.json').write_text(json.dumps(result,indent=2,default=str))
    print(json.dumps(result,indent=2,default=str))

if __name__=='__main__':main()
