from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import v36_zero_base_quant_fast as fast
q=fast.q

def load_frames(data_dir):
    frames={}
    for s in ("EURUSD","GBPUSD"):
        x=q.enrich_single(q.load_duka(data_dir/f"{s.lower()}-m15.json",s))
        frames[s]=x[x.date.dt.year.between(2005,2025)].reset_index(drop=True)
    return q.add_cross_features(frames)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    f=load_frames(a.data_dir);rank,_,nr,nt=q.evaluate_rules(f,a.out)
    meta={"kind":"rule_prehold_only","rule_templates":nr,"configs_tested":nt,"prehold_survivors":int(rank.pre_pass.fillna(False).sum())}
    (a.out/"v36_rule_meta.json").write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2));print(rank.head(25).to_string(index=False))
if __name__=="__main__":main()
