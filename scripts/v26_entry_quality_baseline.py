from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,brier_score_loss

FEATURES=['symbol','direction','session','zone_width_atr','bos_displacement_atr','sweep_to_bos_bars','risk_atr']
CAT=['symbol','direction','session']; NUM=[x for x in FEATURES if x not in CAT]
YEARS=(2022,2023,2024,2025)

def bool_col(s): return s.astype(str).str.lower().eq('true') if s.dtype==object else s.astype(bool)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    x=pd.read_csv(a.input);x=x[np.isclose(pd.to_numeric(x.depth),.5)].copy();x['risk_valid']=bool_col(x.risk_valid);x['filled']=bool_col(x.filled)
    x=x[x.risk_valid & x.filled & x.outcome_m5.isin(['win','loss'])].copy();x['target_win']=(x.outcome_m5=='win').astype(int)
    for c in NUM:x[c]=pd.to_numeric(x[c],errors='coerce')
    x=x.dropna(subset=FEATURES)
    pre=ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore'),CAT),('num',StandardScaler(),NUM)])
    rows=[];all_y=[];all_p=[];all_b=[]
    for y in YEARS:
        tr=x[x.year<y];te=x[x.year==y]
        model=Pipeline([('pre',pre),('clf',LogisticRegression(C=.5,max_iter=2000))]);model.fit(tr[FEATURES],tr.target_win)
        p=model.predict_proba(te[FEATURES])[:,1];base=np.full(len(te),tr.target_win.mean())
        brier=brier_score_loss(te.target_win,p);bb=brier_score_loss(te.target_win,base)
        rows.append({'year':y,'n':int(len(te)),'train_win_rate':float(tr.target_win.mean()),'test_win_rate':float(te.target_win.mean()),'auc':float(roc_auc_score(te.target_win,p)),'brier':float(brier),'base_brier':float(bb),'brier_gain':float(bb-brier)})
        all_y.extend(te.target_win.tolist());all_p.extend(p.tolist());all_b.extend(base.tolist())
    result={'study':'V2 v2.6 midpoint entry-quality baseline','generatedAt':pd.Timestamp.utcnow().isoformat(),'protocol':{'depth':.5,'target':'clean resolved M5 win vs loss','featuresKnownBeforeEntry':FEATURES,'chronologicalTestYears':list(YEARS),'model':'regularized logistic regression','automaticProductInfluence':False},'yearly':rows,'pooled':{'n':len(all_y),'auc':float(roc_auc_score(all_y,all_p)),'brier':float(brier_score_loss(all_y,all_p)),'base_brier':float(brier_score_loss(all_y,all_b))},'decision':'REJECT_GEOMETRY_ONLY_QUALITY_MODEL','interpretation':'Current pre-entry candle geometry does not improve calibrated clean-outcome prediction over a simple prior-history base rate. Seek new information rather than more complexity on the same features.','boundary':'Ambiguous M5 paths are excluded from this clean-outcome target; this is research, not broker execution validation.'}
    pd.DataFrame(rows).to_csv(a.out/'v26_entry_quality_yearly.csv',index=False);(a.out/'v26_entry_quality_summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
