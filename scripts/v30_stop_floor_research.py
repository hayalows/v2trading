from __future__ import annotations

"""V2 v3.0 stop-floor research.

Research question: does a minimum pip breathing-room floor improve V2's current
50% POI midpoint + structural sweep stop + 2.5R policy without changing entry?

The structural stop is never tightened. Candidate risk distance is:
    max(existing structural risk, candidate pip floor)
Position-risk percentage is outside this study and remains unchanged.

M5 OHLC is used to reduce path ambiguity. Same-M5 entry/exit ordering remains
ambiguous and is reported with primary/pessimistic/optimistic bounds.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from public_data_v2_proxy import load_market

SYMBOLS = ("EURUSD", "GBPUSD")
COMPLETED_YEARS = (2022, 2023, 2024, 2025)
FLOORS_PIPS = (0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0)
REWARD_R = 2.5
MIN_RISK_ATR = 0.08
MAX_RISK_ATR = 1.60
ENTRY_WAIT_M5_BARS = 576
POST_ENTRY_M5_BARS = 144
BOOT_REPS = 3000
BOOT_SEED = 3001
PIP = 0.0001


def ts_utc(v: Any) -> pd.Timestamp:
    x = pd.Timestamp(v)
    return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")


def hit_entry(row: pd.Series, entry: float) -> bool:
    return float(row.low) <= entry <= float(row.high)


def simulate_path(m5: pd.DataFrame, fill_idx: int, direction: str, entry: float, risk: float) -> dict[str, Any]:
    stop = entry - risk if direction == "long" else entry + risk
    target = entry + REWARD_R * risk if direction == "long" else entry - REWARD_R * risk
    q = m5.loc[fill_idx:].iloc[:POST_ENTRY_M5_BARS]
    if q.empty:
        return {"status":"missing","gross_primary":0.0,"gross_pess":-1.0,"gross_opt":REWARD_R,"stop":stop,"target":target,"mae_pips":None,"mfe_pips":None,"bars_held":0}
    max_fav = 0.0
    max_adv = 0.0
    for k, (_, r) in enumerate(q.iterrows()):
        hi, lo = float(r.high), float(r.low)
        if direction == "long":
            hs, ht = lo <= stop, hi >= target
            max_fav = max(max_fav, (hi-entry)/PIP)
            max_adv = max(max_adv, (entry-lo)/PIP)
        else:
            hs, ht = hi >= stop, lo <= target
            max_fav = max(max_fav, (entry-lo)/PIP)
            max_adv = max(max_adv, (hi-entry)/PIP)
        if k == 0 and (hs or ht):
            return {"status":"ambiguous_entry","gross_primary":0.0,"gross_pess":-1.0,"gross_opt":REWARD_R,"stop":stop,"target":target,"mae_pips":max_adv,"mfe_pips":max_fav,"bars_held":1}
        if hs and ht:
            return {"status":"ambiguous_exit","gross_primary":0.0,"gross_pess":-1.0,"gross_opt":REWARD_R,"stop":stop,"target":target,"mae_pips":max_adv,"mfe_pips":max_fav,"bars_held":k+1}
        if hs:
            return {"status":"loss","gross_primary":-1.0,"gross_pess":-1.0,"gross_opt":-1.0,"stop":stop,"target":target,"mae_pips":max_adv,"mfe_pips":max_fav,"bars_held":k+1}
        if ht:
            return {"status":"win","gross_primary":REWARD_R,"gross_pess":REWARD_R,"gross_opt":REWARD_R,"stop":stop,"target":target,"mae_pips":max_adv,"mfe_pips":max_fav,"bars_held":k+1}
    last = float(q.iloc[-1].close)
    mtm = ((last-entry)/risk) if direction == "long" else ((entry-last)/risk)
    mtm = float(np.clip(mtm, -1.0, REWARD_R))
    return {"status":"timeout","gross_primary":mtm,"gross_pess":mtm,"gross_opt":mtm,"stop":stop,"target":target,"mae_pips":max_adv,"mfe_pips":max_fav,"bars_held":int(len(q))}


def build_rows(setups: pd.DataFrame, m5_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    out: list[dict[str, Any]] = []
    for _, s in setups.iterrows():
        symbol = str(s.symbol)
        if symbol not in SYMBOLS:
            continue
        direction = str(s.direction)
        lo, hi = float(s.poi_low), float(s.poi_high)
        entry = (lo + hi) / 2.0
        structural_stop = float(s.stop)
        atr = float(s.atr)
        base_risk = (entry-structural_stop) if direction == "long" else (structural_stop-entry)
        base_risk_atr = base_risk/atr if atr > 0 else np.nan
        if not (np.isfinite(base_risk_atr) and base_risk > 0 and MIN_RISK_ATR <= base_risk_atr <= MAX_RISK_ATR):
            continue
        m5 = m5_by_symbol[symbol]
        start = ts_utc(s.bos_time) + pd.Timedelta(minutes=15)
        start_pos = int(m5.date.searchsorted(start, side="left"))
        entry_window = m5.iloc[start_pos:start_pos + ENTRY_WAIT_M5_BARS]
        fill_idx = None
        for idx, r in entry_window.iterrows():
            if hit_entry(r, entry):
                fill_idx = int(idx)
                break
        for floor in FLOORS_PIPS:
            risk = max(base_risk, floor*PIP)
            risk_pips = risk/PIP
            risk_atr = risk/atr if atr > 0 else np.nan
            eligible = bool(np.isfinite(risk_atr) and MIN_RISK_ATR <= risk_atr <= MAX_RISK_ATR)
            rec = {"setup_id":str(s.setup_id),"symbol":symbol,"direction":direction,"year":int(s.year),"session":str(s.session),"bos_time":str(s.bos_time),"floor_pips":float(floor),"entry":entry,"base_risk_pips":base_risk/PIP,"candidate_risk_pips":risk_pips,"atr_pips":atr/PIP,"candidate_risk_atr":risk_atr,"eligible":eligible,"filled":fill_idx is not None}
            if not eligible:
                rec.update(status="skipped_risk_gate",gross_primary=0.0,gross_pess=0.0,gross_opt=0.0,stop=np.nan,target=np.nan,mae_pips=np.nan,mfe_pips=np.nan,bars_held=0)
            elif fill_idx is None:
                rec.update(status="not_filled",gross_primary=0.0,gross_pess=0.0,gross_opt=0.0,stop=(entry-risk if direction=="long" else entry+risk),target=(entry+REWARD_R*risk if direction=="long" else entry-REWARD_R*risk),mae_pips=np.nan,mfe_pips=np.nan,bars_held=0)
            else:
                rec.update(simulate_path(m5, fill_idx, direction, entry, risk))
            out.append(rec)
    return pd.DataFrame(out)


def summary_group(g: pd.DataFrame) -> dict[str, Any]:
    status = g.status.astype(str)
    resolved = g[status.isin(["win","loss"])]
    amb = status.str.startswith("ambiguous")
    return {"n":int(len(g)),"eligible_rate":float(g.eligible.mean()) if len(g) else None,"fill_rate":float(g.filled.mean()) if len(g) else None,"wins":int((status=="win").sum()),"losses":int((status=="loss").sum()),"timeouts":int((status=="timeout").sum()),"ambiguous":int(amb.sum()),"not_filled":int((status=="not_filled").sum()),"skipped":int((status=="skipped_risk_gate").sum()),"resolved_win_rate":float((resolved.status=="win").mean()) if len(resolved) else None,"ambiguity_rate_filled":float(amb.sum()/max(1,g.filled.sum())),"mean_r_primary":float(g.gross_primary.mean()) if len(g) else None,"mean_r_pess":float(g.gross_pess.mean()) if len(g) else None,"mean_r_opt":float(g.gross_opt.mean()) if len(g) else None,"median_risk_pips":float(g.loc[g.eligible,"candidate_risk_pips"].median()) if g.eligible.any() else None,"p90_risk_pips":float(g.loc[g.eligible,"candidate_risk_pips"].quantile(.90)) if g.eligible.any() else None}


def make_table(rows: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    records=[]
    for keys,g in rows.groupby(by,sort=True):
        keys=keys if isinstance(keys,tuple) else (keys,)
        rec={k:v for k,v in zip(by,keys)}; rec.update(summary_group(g)); records.append(rec)
    return pd.DataFrame(records)


def bootstrap_delta(x: np.ndarray) -> dict[str, Any]:
    x=np.asarray(x,float)
    if not len(x): return {"n":0,"point":None,"low95":None,"high95":None}
    rng=np.random.default_rng(BOOT_SEED); vals=np.empty(BOOT_REPS)
    for i in range(BOOT_REPS): vals[i]=x[rng.integers(0,len(x),len(x))].mean()
    return {"n":int(len(x)),"point":float(x.mean()),"low95":float(np.quantile(vals,.025)),"high95":float(np.quantile(vals,.975)),"reps":BOOT_REPS,"seed":BOOT_SEED}


def choose_floor(train: pd.DataFrame, symbol: str) -> float:
    q=train[train.symbol.eq(symbol)]; tab=make_table(q,["floor_pips"]); tab=tab[tab.eligible_rate>=.85].copy()
    if tab.empty: return 0.0
    best=tab.mean_r_pess.max()
    return float(tab[np.isclose(tab.mean_r_pess,best,atol=1e-12)].sort_values("floor_pips").iloc[0].floor_pips)


def walkforward(rows: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    yearly=[]; paired=[]
    for year in COMPLETED_YEARS:
        train=rows[rows.year<year]; test=rows[rows.year==year]
        if train.empty or test.empty: continue
        for symbol in SYMBOLS:
            floor=choose_floor(train,symbol)
            c=test[(test.symbol==symbol)&np.isclose(test.floor_pips,floor)].set_index("setup_id")
            b=test[(test.symbol==symbol)&np.isclose(test.floor_pips,0.0)].set_index("setup_id")
            ids=c.index.intersection(b.index)
            if not len(ids): continue
            delta=c.loc[ids,"gross_pess"].to_numpy(float)-b.loc[ids,"gross_pess"].to_numpy(float)
            yearly.append({"year":year,"symbol":symbol,"chosen_floor_pips":floor,"n":int(len(ids)),"candidate_pess_r":float(c.loc[ids,"gross_pess"].mean()),"baseline_pess_r":float(b.loc[ids,"gross_pess"].mean()),"delta_pess_r":float(delta.mean())})
            for sid,dv in zip(ids,delta): paired.append({"year":year,"symbol":symbol,"setup_id":sid,"chosen_floor_pips":floor,"delta_pess_r":float(dv)})
    return pd.DataFrame(yearly),pd.DataFrame(paired)


def winner_mae(rows: pd.DataFrame) -> list[dict[str, Any]]:
    b=rows[np.isclose(rows.floor_pips,0.0)&rows.status.eq("win")&rows.mae_pips.notna()]; out=[]
    for symbol,g in b.groupby("symbol"):
        out.append({"symbol":symbol,"n_wins":int(len(g)),"mae_median_pips":float(g.mae_pips.median()),"mae_p80_pips":float(g.mae_pips.quantile(.80)),"mae_p90_pips":float(g.mae_pips.quantile(.90)),"mae_p95_pips":float(g.mae_pips.quantile(.95))})
    return out


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('--data-dir',type=Path,required=True); ap.add_argument('--setups',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True); setups=pd.read_csv(a.setups)
    m5_by_symbol={}
    for symbol in SYMBOLS:
        x=load_market(a.data_dir/f'{symbol}-5m.feather',symbol).reset_index(drop=True); x['date']=pd.to_datetime(x.date,utc=True); m5_by_symbol[symbol]=x
    rows=build_rows(setups,m5_by_symbol); completed=rows[rows.year.isin(COMPLETED_YEARS)].copy()
    overall=make_table(completed,['symbol','floor_pips']); yearly=make_table(completed,['year','symbol','floor_pips']); pooled=make_table(completed,['floor_pips'])
    wf,wfp=walkforward(rows[rows.year<=2025].copy()); boot=bootstrap_delta(wfp.delta_pess_r.to_numpy(float) if len(wfp) else np.array([])); winmae=winner_mae(completed)
    leaders={}
    for symbol in SYMBOLS:
        q=overall[(overall.symbol==symbol)&(overall.eligible_rate>=.85)].sort_values(['mean_r_pess','floor_pips'],ascending=[False,True]); leaders[symbol]=q.iloc[0].to_dict() if len(q) else None
    year_consistency={}
    for symbol in SYMBOLS:
        base=yearly[(yearly.symbol==symbol)&np.isclose(yearly.floor_pips,0.0)].set_index('year'); vals=[]
        for floor in FLOORS_PIPS:
            q=yearly[(yearly.symbol==symbol)&np.isclose(yearly.floor_pips,floor)].set_index('year'); common=q.index.intersection(base.index); deltas=(q.loc[common,'mean_r_pess']-base.loc[common,'mean_r_pess']) if len(common) else pd.Series(dtype=float)
            vals.append({'floor_pips':floor,'years':int(len(common)),'noninferior_years':int((deltas>=0).sum()),'positive_years':int((deltas>0).sum()),'mean_year_delta_pess_r':float(deltas.mean()) if len(deltas) else None})
        year_consistency[symbol]=vals
    summary={'study':'V2 v3.0 structural-stop breathing-room floor','method':'50% midpoint unchanged; stop never tightened; candidate risk=max(sweep stop + 0.03 ATR distance, pip floor); 2.5R target recomputed; 48h entry wait; 48 M15 bars post-entry; M5 sequencing.','completed_years':list(COMPLETED_YEARS),'floors_pips':list(FLOORS_PIPS),'rows':int(len(rows)),'independent_setups_completed':int(completed.setup_id.nunique()),'static_conservative_leaders':leaders,'winner_mae':winmae,'year_consistency':year_consistency,'walkforward':wf.to_dict(orient='records'),'walkforward_bootstrap_candidate_minus_baseline_pess_r':boot,'boundary':'Public M5 OHLC can still be ambiguous inside one 5-minute bar. No broker spread/slippage/fill claim; no automatic strategy promotion.'}
    rows.to_csv(a.out/'v30_stop_floor_rows.csv',index=False); overall.to_csv(a.out/'v30_stop_floor_pair_table.csv',index=False); yearly.to_csv(a.out/'v30_stop_floor_year_pair_table.csv',index=False); pooled.to_csv(a.out/'v30_stop_floor_pooled_table.csv',index=False); wf.to_csv(a.out/'v30_stop_floor_walkforward.csv',index=False); wfp.to_csv(a.out/'v30_stop_floor_walkforward_paired.csv',index=False); (a.out/'v30_stop_floor_summary.json').write_text(json.dumps(summary,indent=2,default=str)); print(json.dumps(summary,indent=2,default=str))

if __name__=='__main__': main()
