from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36b_usd_factor as b
q=b.q

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--grid',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    rank=pd.read_csv(a.grid);rank['pre_pass']=rank.pre_pass.astype(str).str.lower().eq('true');rank=rank.sort_values(['pre_pass','robust_score','pre_mean_r'],ascending=[False,False,False]).reset_index(drop=True);rank.to_csv(a.out/'v36b_factor_grid.csv',index=False)
    res={'protocol':'V3.6B systematic USD-factor frozen parallel','configs_tested':int(len(rank)),'prehold_survivors':int(rank.pre_pass.sum()),'holdout_opened':False}
    if not rank.pre_pass.any():
        res.update({'selected':None,'holdout_status':'REJECT','reason':'No pre-2023 factor candidate cleared the frozen gate; 2023-2025 was not used to rescue a rule.'})
    else:
        sel=rank[rank.pre_pass].iloc[0];raw=b.load_all(a.data_dir);fac=b.factor_table(raw);frames=b.attach_factor(raw,fac);rules={r.name:r for r in b.build_rules()};r=rules[str(sel['name'])];sm=float(sel.stop_atr);rr=float(sel.rr);ts=[]
        for s in b.TARGETS:
            x=frames[s];d=q.to_events(r.fn(x,s));t=q.simulate_config(x,d,sm,rr,q.BASE_COST[s]);
            if t.empty:continue
            t['symbol']=s;t['stress_r']=t.gross_r-(q.STRESS_COST[s]*q.PIP)/(sm*t.atr);ts.append(t)
        t=pd.concat(ts,ignore_index=True).sort_values('signal_time') if ts else pd.DataFrame();status,gate=q.holdout_gate(t);comp=b.target_only_comparator(frames,r,sm,rr);t.to_csv(a.out/'v36b_selected_trades.csv',index=False)
        res.update({'selected':{k:(v.item() if hasattr(v,'item') else v) for k,v in sel.dropna().to_dict().items()},'holdout_opened':True,'holdout_status':status,'holdout_gate':gate,'prehold_reconstructed':q.metrics(t[t.year<=2022]),'target_only_prehold':q.metrics(comp[comp.year<=2022]) if not comp.empty else None,'target_only_holdout':q.metrics(comp[comp.year>=2023]) if not comp.empty else None})
    (a.out/'v36b_summary.json').write_text(json.dumps(res,indent=2,default=str));print(json.dumps(res,indent=2,default=str));print(rank.head(30).to_string(index=False))
if __name__=='__main__':main()
