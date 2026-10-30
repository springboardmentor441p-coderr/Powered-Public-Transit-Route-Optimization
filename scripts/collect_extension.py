"""Immutable daily history plus dated Manhattan schedule archives; preserves pilot inputs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from urllib.parse import urlencode
import pandas as pd
from collect_new_york import ROOT, RAW, BASE, download

ARCHIVES = {
    'manhattan_20251230': '202512300036',
    'manhattan_20260327': '202603270138',
    'manhattan_20260409': '202604090120',
    'manhattan_20260624': '202606240130',
}

def quarter(period):
    start,end=period
    where=f"transit_timestamp >= '{start}T00:00:00' AND transit_timestamp < '{end}T00:00:00'"
    folder=RAW/'history_daily'
    params={'$select':'date_trunc_ymd(transit_timestamp) as service_date,bus_route,sum(ridership) as published_boardings,sum(transfers) as published_transfers,count(distinct transit_timestamp) as reported_hours,count(*) as source_rows',
            '$where':where,'$group':'service_date,bus_route','$order':'service_date,bus_route','$limit':100000}
    a=download(BASE+'.csv?'+urlencode(params),folder/f'{start}_route_day.csv','csv')
    frame=pd.read_csv(ROOT/a['local_path'])
    assert len(frame)<100000,'Truncated history query'
    params={'$select':'date_trunc_ymd(transit_timestamp) as service_date,sum(ridership) as published_boardings,sum(transfers) as published_transfers,count(*) as source_rows',
            '$where':where,'$group':'service_date','$order':'service_date','$limit':1000}
    b=download(BASE+'.csv?'+urlencode(params),folder/f'{start}_denominator.csv','csv')
    print('Daily history',start,end,len(frame),flush=True)
    return [a,b]

def main():
    windows=[]
    for year in [2025,2026]:
        for month in [1,4,7,10]:
            start=date(year,month,1)
            end=date(year+1,1,1) if month==10 else date(year,month+3,1)
            if start>=date(2026,10,1):continue
            windows.append((start,end))
    receipts=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for batch in pool.map(quarter,windows):receipts.extend(batch)
    for name,stamp in ARCHIVES.items():
        url=f'https://files.mobilitydatabase.org/mdb-513/mdb-513-{stamp}/mdb-513-{stamp}.zip'
        receipts.append(download(url,RAW/f'gtfs/archive/{name}.zip','zip'))
        print('Archived schedule',name,flush=True)
    report=ROOT/'reports/week1/collection/daily_history';report.mkdir(parents=True,exist_ok=True)
    (report/'collection_manifest.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    print('Extension collection complete:',len(receipts),'receipts',flush=True)

if __name__=='__main__':main()
