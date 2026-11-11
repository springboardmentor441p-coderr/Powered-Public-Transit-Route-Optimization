"""Common-row retrospective comparison of demand-only and scheduled-supply predictors."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from daily_replay_experiment import ROOT,FEATURES,examples,metrics
from forecasting import load_inputs

def schedule_gate(frame):
 out=frame.copy();dates=pd.to_datetime(out.payment_date)
 ok=out.schedule_comparison_eligible.astype('string').str.lower().eq('true')
 for key in ['source_snapshot','prior_source_snapshot']:
  captures=pd.to_datetime(out[key].astype('string').str.extract(r'(\d{8})$',expand=False),format='%Y%m%d',errors='coerce')
  ok &= captures.notna() & captures.lt(dates)
 for key in ['scheduled_departures','scheduled_service_hours']:
  values=pd.to_numeric(out[key],errors='coerce');ok &= np.isfinite(values)&values.gt(0)
 return ok.fillna(False)

def main():
 folder=ROOT/'data/processed/new_york/service_feature_experiment';folder.mkdir(parents=True,exist_ok=True)
 daily,_=load_inputs(ROOT);demand=examples(daily)
 path=ROOT/'data/processed/new_york/matched_daily_features.csv';supply=pd.read_csv(path,dtype={'bus_route':'string'},parse_dates=['payment_date'],low_memory=False)
 supply['issue_time_schedule_eligible']=schedule_gate(supply)
 audit=supply[['bus_route','payment_date','source_snapshot','prior_source_snapshot','schedule_comparison_eligible','issue_time_schedule_eligible']].copy();audit.to_csv(folder/'schedule_availability.csv',index=False)
 joined=demand.merge(supply[['bus_route','payment_date','scheduled_departures','scheduled_service_hours','issue_time_schedule_eligible']],on=['bus_route','payment_date'],validate='one_to_one')
 valid=joined.actual.notna()&joined.seasonal_count.ge(2)&joined.issue_time_schedule_eligible
 splits={name:joined.loc[valid&joined.payment_date.between(a,b)].copy() for name,a,b in [('train','2026-01-01','2026-03-31'),('validation','2026-04-01','2026-05-17'),('test','2026-06-01','2026-07-31')]}
 if any(x.empty for x in splits.values()):raise ValueError('Insufficient eligible chronological data')
 predictions=[]
 for kind in ['ridge','random_forest']:
  for include_service in [False,True]:
   numeric=FEATURES+(['scheduled_departures','scheduled_service_hours'] if include_service else [])
   prep=ColumnTransformer([('route',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['bus_route']),('numbers',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),numeric)])
   est=Ridge(alpha=100) if kind=='ridge' else RandomForestRegressor(n_estimators=100,min_samples_leaf=10,max_depth=16,random_state=42,n_jobs=2)
   model=make_pipeline(prep,est);cols=['bus_route']+numeric;model.fit(splits['train'][cols],splits['train'].actual)
   for split in ['validation','test']:
    x=splits[split];p=x[['bus_route','payment_date','actual']].copy();p['prediction']=np.maximum(0,model.predict(x[cols]));p['model']=kind+('_service' if include_service else '_demand');p['split']=split;predictions.append(p)
 for split in ['validation','test']:
  x=splits[split];p=x[['bus_route','payment_date','actual']].copy();p['prediction']=x.seasonal_mean;p['model']='seasonal_mean4';p['split']=split;predictions.append(p)
 p=pd.concat(predictions,ignore_index=True);assert p.groupby(['bus_route','payment_date','split']).model.nunique().eq(5).all()
 score=pd.DataFrame([dict(split=s,model=m,**metrics(g)) for (s,m),g in p.groupby(['split','model'])])
 score.to_csv(folder/'metrics.csv',index=False);p.to_csv(folder/'predictions.csv',index=False)
 pd.DataFrame([dict(split=s,model=m,route=r,**metrics(g)) for (s,m,r),g in p.groupby(['split','model','bus_route'])]).to_csv(folder/'route_errors.csv',index=False)
 p['day_type']=pd.to_datetime(p.payment_date).dt.dayofweek.map(lambda x:'Weekday' if x<5 else 'Saturday' if x==5 else 'Sunday')
 pd.DataFrame([dict(split=s,model=m,day_type=d,**metrics(g)) for (s,m,d),g in p.groupby(['split','model','day_type'])]).to_csv(folder/'day_type_errors.csv',index=False)
 selected=score[score.split.eq('validation')].sort_values(['MAE','model']).iloc[0].model
 report={'status':'retrospective_comparison_not_model_promotion','selected_on_validation':selected,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'counts':{k:len(v) for k,v in splits.items()},'train_end':'2026-03-31','validation_end':'2026-05-17','test_period':['2026-06-01','2026-07-31'],'issue_policy':'00:00 local; both contributing snapshot capture dates strictly before target; 14 complete-day observation delay','supply_semantics':'Clock-date scheduled departures and passenger-trip hours; quality gates retained','construction_limit':'Capture dates are archive availability proxies, not verified original agency publication times; experiment developed after historical outcomes','serving_decision':'Keep existing frozen replay bundle; this experiment does not promote a model or rewrite forecasts','metrics':score.to_dict('records')}
 (folder/'manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
