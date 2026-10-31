"""Inventory immutable inputs, load GTFS and inspect original records.

No cleaning, model features, clustering, training, predictions, scenarios or application services.
"""
from pathlib import Path
from datetime import datetime,timezone
import gc,hashlib,json,zipfile
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/new_york'
REPORT=ROOT/'reports/week1'
ESSENTIAL=['routes','trips','stop_times','stops','calendar']

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')

def columns(frame,table):
    n=len(frame)
    return pd.DataFrame({'table':table,'column':frame.columns,'loaded_dtype':frame.dtypes.astype(str).values,
        'rows':n,'missing_count':frame.isna().sum().values,
        'missing_percent':frame.isna().mean().mul(100).values,
        'distinct_nonmissing':frame.nunique().values,
        'memory_bytes':[frame[c].memory_usage(index=False,deep=True) for c in frame]})

def inventory():
    rows=[]
    for p in sorted(RAW.rglob('*.receipt.json')):
        receipt=json.loads(p.read_text());target=ROOT/receipt['local_path']
        with target.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=receipt['sha256']:raise ValueError(f'Source fingerprint changed: {target}')
        rows.append({**receipt,'sha256_verified':True})
    if not rows:raise FileNotFoundError('Collect the source data first.')
    pd.DataFrame(rows).to_csv(REPORT/'source_inventory.csv',index=False)
    return rows

def inspect_gtfs(path):
    feed=path.parent.name+'_'+path.stem;folder=REPORT/'gtfs'/feed;folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError(f'ZIP integrity failed: {path}')
        tables={name[:-4]:pd.read_csv(z.open(name),dtype='string') for name in z.namelist() if name.endswith('.txt') and '/' not in name}
    missing=[t for t in ESSENTIAL if t not in tables]
    if missing:raise ValueError(f'Missing essential tables: {feed}: {missing}')
    # Keep IDs/text as strings. Numeric/date validation uses temporary values, never repairs input.
    profile=pd.concat([columns(frame,name) for name,frame in tables.items()],ignore_index=True)
    profile.to_csv(folder/'column_inspection.csv',index=False)
    summary=[]
    for name,frame in tables.items():
        summary.append({'table':name,'rows':len(frame),'columns':len(frame.columns),
            'duplicate_full_rows':int(frame.duplicated().sum()),
            'missing_cells':int(frame.isna().sum().sum()),'memory_bytes':int(frame.memory_usage(deep=True).sum())})
    pd.DataFrame(summary).to_csv(folder/'table_inspection.csv',index=False)
    r,t,st,s,c=[tables[name] for name in ESSENTIAL]
    checks=[]
    def add(name,count,scope):checks.append({'check':name,'count':int(count),'scope':scope})
    for name,keys in [('routes',['route_id']),('trips',['trip_id']),('stops',['stop_id']),('stop_times',['trip_id','stop_sequence']),('calendar',['service_id'])]:
        add(name+'_duplicate_keys',tables[name].duplicated(keys).sum(),'Duplicate key rows, not duplicate display names')
    service=set(c.service_id)
    exc=tables.get('calendar_dates')
    if exc is not None:
        service|=set(exc.service_id)
        add('duplicate_service_date_exceptions',exc.duplicated(['service_id','date']).sum(),'Calendar exception keys')
        add('invalid_exception_dates',pd.to_datetime(exc.date,format='%Y%m%d',errors='coerce').isna().sum(),'Calendar exception date parse')
        add('invalid_exception_types',(~exc.exception_type.isin(['1','2'])).sum(),'Expected addition/removal flags')
    add('unknown_trip_routes',(~t.route_id.isin(r.route_id)).sum(),'Trip route foreign keys')
    add('unknown_trip_services',(~t.service_id.isin(service)).sum(),'Calendar plus exception service IDs')
    add('unknown_stop_time_trips',(~st.trip_id.isin(t.trip_id)).sum(),'Stop-time trip foreign keys')
    add('unknown_stop_time_stops',(~st.stop_id.isin(s.stop_id)).sum(),'Stop-time stop foreign keys')
    add('trips_without_stop_times',(~t.trip_id.isin(st.trip_id)).sum(),'Trip timing coverage')
    add('catalogue_routes_without_trip_templates',(~r.route_id.isin(t.route_id)).sum(),'May be shared catalogues; not automatically an error')
    for coord,low,high in [('stop_lat',-90,90),('stop_lon',-180,180)]:
        v=pd.to_numeric(s[coord],errors='coerce');add('invalid_or_missing_'+coord,(v.isna()|~v.between(low,high)).sum(),'Basic coordinate ranges only')
    for field in ['arrival_time','departure_time']:
        valid=st[field].str.fullmatch(r'\d+:[0-5]\d:[0-5]\d',na=False)
        add('missing_or_malformed_'+field,(~valid).sum(),'GTFS format permits hours beyond 23; no time feature built')
    begin=pd.to_datetime(c.start_date,format='%Y%m%d',errors='coerce');end=pd.to_datetime(c.end_date,format='%Y%m%d',errors='coerce')
    add('invalid_calendar_date_rows',(begin.isna()|end.isna()|begin.gt(end)).sum(),'Parse and start/end order')
    days=c[['monday','tuesday','wednesday','thursday','friday','saturday','sunday']]
    add('invalid_weekday_flag_rows',(~days.isin(['0','1'])).any(axis=1).sum(),'Expected binary flags')
    if 'shapes' in tables:
        shape=tables['shapes'];add('duplicate_shape_sequence_keys',shape.duplicated(['shape_id','shape_pt_sequence']).sum(),'Optional shape point keys')
        add('unknown_or_missing_trip_shapes',(~t.shape_id.isin(shape.shape_id)).sum(),'Optional shape references')
    pd.DataFrame(checks).to_csv(folder/'key_and_field_checks.csv',index=False)
    value={'feed':feed,'essential_tables_loaded':ESSENTIAL,'table_counts':{k:len(v) for k,v in tables.items()},
        'catalogue_route_rows':len(r),'routes_referenced_by_trips':int(t.route_id.nunique()),
        'calendar_start':str(begin.min().date()),'calendar_end':str(end.max().date()),
        'load_policy':'Read directly from original ZIP into pandas. GTFS columns deliberately loaded as strings to preserve identifiers; temporary format checks do not clean or overwrite source.',
        'scope':'Initial schemas, missingness, duplicates, relationships and basic field validity only. No service features, demand matching or advanced spatial analysis.'}
    write_json(folder/'inspection.json',value)
    print('Inspected',feed,flush=True)
    del tables;gc.collect();return value

def demand_family(files,refs,label,hourly):
    frame=pd.concat([pd.read_csv(p,dtype={'bus_route':'string'}) for p in files],ignore_index=True)
    profile=columns(frame,label);profile.to_csv(REPORT/f'{label}_column_inspection.csv',index=False)
    datecol='transit_timestamp' if hourly else 'service_date'
    stamp=pd.to_datetime(frame[datecol],errors='coerce')
    if stamp.isna().any():raise ValueError(f'Invalid source dates: {label}')
    if frame.duplicated(['bus_route',datecol]).any():raise ValueError(f'Duplicate source aggregate keys: {label}')
    values=['ridership','transfers','source_rows'] if hourly else ['published_boardings','published_transfers','source_rows']
    for name in values:
        v=pd.to_numeric(frame[name],errors='raise')
        if not(v.notna().all() and v.ge(0).all()):raise ValueError(f'Invalid numeric source field: {label}/{name}')
    if frame[values[1]].gt(frame[values[0]]).any():raise ValueError('Transfer subset exceeds published boardings')
    # Reconciliation is inspection of an extract, not construction of a modelling dataset.
    actual=frame[values].groupby(stamp.dt.strftime('%Y-%m-%d')).sum().rename_axis('service_date').reset_index()
    reference=pd.concat([pd.read_csv(p) for p in refs],ignore_index=True)
    reference['service_date']=pd.to_datetime(reference.service_date).dt.strftime('%Y-%m-%d')
    check=actual.merge(reference,on='service_date',how='outer',suffixes=('_extract','_query'),indicator=True,validate='one_to_one')
    if not check['_merge'].eq('both').all():raise ValueError('Incomplete reference dates')
    for name in values:
        check[name+'_difference']=check[name+'_extract']-check[name+'_query']
        if not check[name+'_difference'].eq(0).all():raise ValueError('Publisher-query totals disagree')
    check.to_csv(REPORT/f'{label}_reconciliation.csv',index=False)
    result={'rows':len(frame),'columns':len(frame.columns),'published_route_identifiers':int(frame.bus_route.nunique()),
        'dates':int(stamp.dt.normalize().nunique()),'first_date':str(stamp.min().date()),'last_date':str(stamp.max().date()),
        'duplicate_aggregate_keys':0,'missing_values':frame.isna().sum().astype(int).to_dict(),
        'resolution':'route/local clock hour' if hourly else 'route/local clock date',
        'reconciliation':'Passed against separate daily query of the same publisher; not independent passenger measurement'}
    if not hourly:
        v=pd.to_numeric(frame.reported_hours,errors='raise')
        if not v.between(1,24).all():raise ValueError('Unexpected reported-hour counts')
    write_json(REPORT/f'{label}_inspection.json',result)
    return result

def run():
    REPORT.mkdir(parents=True,exist_ok=True)
    sources=inventory()
    hourly_files=sorted((RAW/'ridership').glob('*_route_hour.csv'));hourly_refs=sorted((RAW/'ridership').glob('*_daily_denominator.csv'))
    daily_files=sorted((RAW/'history_daily').glob('*_route_day.csv'));daily_refs=sorted((RAW/'history_daily').glob('*_denominator.csv'))
    if len(hourly_files)!=14 or len(hourly_refs)!=14 or len(daily_files)!=7 or len(daily_refs)!=7:raise ValueError('Collection incomplete')
    hourly=demand_family(hourly_files,hourly_refs,'hourly_source',True)
    daily=demand_family(daily_files,daily_refs,'daily_source',False)
    sample=pd.read_csv(RAW/'ridership/raw_fare_category_sample_10000.csv',dtype={'bus_route':'string'})
    columns(sample,'bounded_fare_category_sample').to_csv(REPORT/'raw_sample_column_inspection.csv',index=False)
    sample_summary={'rows':len(sample),'duplicate_full_rows':int(sample.duplicated().sum()),'missing_values':sample.isna().sum().astype(int).to_dict(),'scope':'Bounded 10,000-row sample only, not an audit of every original fare-category row.'}
    gtfs=[inspect_gtfs(path) for path in sorted((RAW/'gtfs').glob('*/*.zip'))]
    pd.DataFrame([{'feed':q['feed'],**q['table_counts'],'routes_referenced_by_trips':q['routes_referenced_by_trips'],'calendar_start':q['calendar_start'],'calendar_end':q['calendar_end']} for q in gtfs]).to_csv(REPORT/'gtfs_inventory.csv',index=False)
    result={'inspected_utc':datetime.now(timezone.utc).isoformat(),'active_stage':'Source inspection','verified_source_receipts':len(sources),'gtfs_snapshots':len(gtfs),'current_gtfs_snapshots':len(list((RAW/'gtfs/current').glob('*.zip'))),'historical_gtfs_snapshots':len(list((RAW/'gtfs/archive').glob('*.zip'))),
        'hourly_source':hourly,'daily_source':daily,'bounded_raw_sample':sample_summary,'gtfs':gtfs,
        'completion':'Collection, loading and initial inspection completed for the selected New York sources.',
        'deferred':'Downstream cleaning, feature engineering and EDA are documented in separate notebooks; modelling and application development are outside this inspection module.'}
    write_json(REPORT/'inspection_summary.json',result)
    return result

if __name__=='__main__':
    result=run();print(json.dumps({k:v for k,v in result.items() if k not in ['gtfs','hourly_source','daily_source','bounded_raw_sample']},indent=2))
