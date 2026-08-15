from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--results-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    ps=sorted(a.results_dir.glob('v36c_sm*_rr*.csv'));rank=pd.concat([pd.read_csv(p) for p in ps],ignore_index=True);rank['pre_pass']=rank.pre_pass.astype(str).str.lower().eq('true');rank=rank.sort_values(['pre_pass','pre_stress_mean_r','pre_mean_r','pre_pf','pre_win_rate','pre_n'],ascending=[False,False,False,False,False,False]).reset_index(drop=True);rank.to_csv(a.out/'v36c_all_candidates.csv',index=False)
    branch=rank[rank.pre_pass].copy()
    eligible=branch[(branch.pre_n>=300)&(branch.pre_mean_r>=.04)&(branch.pre_pf>=1.10)&(branch.pre_stress_mean_r>=0)&(branch.pre_positive_years_2017_22>=4)&((branch.pre_win_rate>=.55)|(branch.pre_mean_r>=.10))&(branch.eur_mean_r>0)&(branch.gbp_mean_r>0)]
    selected=None if eligible.empty else eligible.sort_values(['pre_stress_mean_r','pre_mean_r','pre_pf','pre_win_rate','pre_n'],ascending=False).iloc[0]
    res={'protocol':'V3.6C cost-aware ML frozen + global holdout lock','configs_tested':int(len(rank)),'branch_prehold_survivors':int(len(branch)),'global_eligible_survivors':int(len(eligible)),'holdout_opened':False,'selected_for_global_competition':None if selected is None else {k:(v.item() if hasattr(v,'item') else v) for k,v in selected.dropna().to_dict().items()},'note':'2023-2025 is intentionally not evaluated here. V3.6C finalists must compete with V3.6B under V36_GLOBAL_HOLDOUT_LOCK.md.'}
    (a.out/'v36c_prehold_summary.json').write_text(json.dumps(res,indent=2,default=str));print(json.dumps(res,indent=2,default=str));print(rank.head(30).to_string(index=False))
if __name__=='__main__':main()
