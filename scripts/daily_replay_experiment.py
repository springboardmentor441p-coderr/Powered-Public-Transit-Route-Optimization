"""Frozen daily forecasting experiment with exact-date, release-aware predictors."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np,joblib
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
sys.path.insert(0,str(Path(__file__).parent))
from forecasting import load_inputs
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed/new_york/daily_replay_experiment'
FEATURES=['day_of_week','month','is_weekend','lag_1','lag_7','lag_14','lag_21','lag_28','lag_35','lag_42','seasonal_count','seasonal_mean']
def examples(daily):
 x=daily[['bus_route','payment_date','analysis_boardings']].copy().rename(columns={'analysis_boardings':'actual'})
 lookup=x.set_index(['bus_route','payment_date']).actual
 x['available_through']=x.payment_date-pd.Timedelta(days=15)
 for lag in [1,7,14,21,28,35,42]:
  dates=x.payment_date-pd.Timedelta(days=lag)
  x[f'lag_{lag}']=lookup.reindex(pd.MultiIndex.from_arrays([x.bus_route,dates])).to_numpy()
  x.loc[dates.gt(x.available_through),f'lag_{lag}']=np.nan
 cols=['lag_21','lag_28','lag_35','lag_42']
 x['seasonal_count']=x[cols].notna().sum(axis=1)
 x['seasonal_mean']=x[cols].mean(axis=1).where(x.seasonal_count.ge(2))
 x['day_of_week']=x.payment_date.dt.dayofweek;x['month']=x.payment_date.dt.month;x['is_weekend']=x.day_of_week.ge(5).astype(int)
 return x

def metrics(x):
 e=x.prediction-x.actual
 return {'rows':len(x),'MAE':float(e.abs().mean()),'RMSE':float(np.sqrt((e**2).mean())),'WAPE':float(e.abs().sum()/x.actual.sum()) if x.actual.sum()>0 else None}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 daily,routes=load_inputs(ROOT);x=examples(daily)
 # All fitting outcomes are released by the fixed June 1 issue date.
 train=x.loc[x.payment_date.le('2026-03-31')&x.actual.notna()&x.seasonal_count.ge(2)]
 val=x.loc[x.payment_date.between('2026-04-01','2026-05-17')&x.actual.notna()&x.seasonal_count.ge(2)]
 test=x.loc[x.payment_date.between('2026-06-01','2026-07-31')&x.actual.notna()&x.seasonal_count.ge(2)]
 predictions=[];models={}
 for name,est in [('ridge',Ridge(alpha=100)),('random_forest',RandomForestRegressor(n_estimators=100,min_samples_leaf=10,max_depth=16,random_state=42,n_jobs=2))]:
  prep=ColumnTransformer([('route',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['bus_route']),('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler()),FEATURES)])
  model=make_pipeline(prep,est);model.fit(train[['bus_route']+FEATURES],train.actual);models[name]=model
  for split,rows in [('validation',val),('test',test)]:
   p=rows[['bus_route','payment_date','actual']].copy();p['prediction']=np.maximum(0,model.predict(rows[['bus_route']+FEATURES]));p['model']=name;p['split']=split;predictions.append(p)
 for split,rows in [('validation',val),('test',test)]:
  for name,col in [('seasonal_mean4','seasonal_mean'),('seasonal_latest','lag_21')]:
   p=rows[['bus_route','payment_date','actual']].copy();p['prediction']=rows[col];p['model']=name;p['split']=split;predictions.append(p)
 p=pd.concat(predictions,ignore_index=True)
 # Compare every candidate on the same rows with predictions from all candidates.
 keys=['bus_route','payment_date','split'];counts=p.loc[p.prediction.notna()].groupby(keys).model.nunique();valid=counts[counts.eq(4)].reset_index()[keys];p=p.merge(valid,on=keys,validate='many_to_one')
 scores=[dict(split=s,model=m,**metrics(g)) for (s,m),g in p.groupby(['split','model'])]
 score=pd.DataFrame(scores);selected=score.loc[score.split.eq('validation')].sort_values(['MAE','model']).iloc[0].model
 p.to_csv(OUT/'predictions.csv',index=False);score.to_csv(OUT/'metrics.csv',index=False)
 slices=[dict(split=s,model=m,route=r,**metrics(g)) for (s,m,r),g in p.groupby(['split','model','bus_route'])];pd.DataFrame(slices).to_csv(OUT/'route_errors.csv',index=False)
 x.to_csv(OUT/'features.csv',index=False)
 for n,m in models.items():joblib.dump(m,OUT/f'{n}.joblib')
 manifest={'version':'daily_replay_experiment_v1','selected_by_validation':selected,'train_end':'2026-03-31','validation_end':'2026-05-17','frozen_before':'2026-06-01','test_start':'2026-06-01','test_end':'2026-07-31','reporting_delay_complete_days':14,'counts':{'train':len(train),'validation':len(val),'test':len(test)},'features':FEATURES,'unavailable_lags':[1,7,14],'schedule_features_status':'withheld pending issue-time schedule feature audit','status':'retrospective_evaluation_not_operational_acceptance','metrics':scores,'products':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.iterdir() if f.is_file() and f.name!='manifest.json'}}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
