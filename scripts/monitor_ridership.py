"""Capture immutable publisher evidence and route/date observations for vintage monitoring."""
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
from collect_new_york import download

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://data.ny.gov/resource/gxb3-akrn'


def run():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT/'data/raw/new_york_monitoring'/stamp
    out.mkdir(parents=True, exist_ok=False)
    receipts = []
    errors = []

    def fetch(url, filename, kind):
        try:
            receipt = download(url,out/filename,kind)
            receipts.append(receipt)
            (out/'manifest.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
            return out/filename
        except Exception as exc:
            errors.append({'url':url,'file':filename,'error':str(exc)})
            (out/'errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
            print('Unavailable:',filename,str(exc),flush=True)
            return None

    metadata_path = fetch('https://data.ny.gov/api/views/gxb3-akrn.json','metadata.json','json')
    routes = sorted(pd.read_csv(ROOT/'data/processed/new_york/route_crosswalk.csv',dtype='string').bus_route.unique())
    route_filter = ','.join("'"+route.replace("'","''")+"'" for route in routes)
    # Bounded overlap for revision comparison plus all later published dates before this poll.
    end = datetime.now(timezone.utc).date().isoformat()
    where = (f"transit_timestamp >= '2026-09-01T00:00:00' AND transit_timestamp < '{end}T00:00:00' "
             f'AND bus_route in ({route_filter})')
    query = {'$select':'date_trunc_ymd(transit_timestamp) as payment_date,bus_route,sum(ridership) as published_boardings,sum(transfers) as published_transfers,count(distinct transit_timestamp) as reported_hours',
             '$where':where,'$group':'payment_date,bus_route','$order':'payment_date,bus_route','$limit':50000}
    days_path = fetch(BASE+'.csv?'+urlencode(query),'route_days.csv','csv')
    denom_path = fetch(BASE+'.csv?'+urlencode({'$select':'date_trunc_ymd(transit_timestamp) as payment_date,sum(ridership) as published_boardings,sum(transfers) as published_transfers',
             '$where':where,'$group':'payment_date','$order':'payment_date','$limit':1000}),
             'daily_denominator.csv','csv')
    # Public read attempt only. An error documents access, not proof that publisher archives do not exist.
    history_path = fetch('https://data.ny.gov/api/views/gxb3-akrn/revisions.json','public_revisions.json','json')
    result = {'snapshot':out.relative_to(ROOT).as_posix(),'observed_utc':datetime.now(timezone.utc).isoformat(),
              'query_end_exclusive':end,'metadata_available':metadata_path is not None,
              'history_read_available':history_path is not None,'rows':None,'errors':errors}
    if metadata_path:
        metadata=json.loads(metadata_path.read_text())
        result['posting_frequency']=metadata.get('metadata',{}).get('custom_fields',{}).get('Dataset Summary',{}).get('Posting Frequency')
        result['publisher_rows_updated_at']=metadata.get('rowsUpdatedAt')
    if days_path and denom_path:
        days=pd.read_csv(days_path,dtype={'bus_route':'string'},parse_dates=['payment_date'])
        denom=pd.read_csv(denom_path,parse_dates=['payment_date'])
        assert len(days)<50000 and len(denom)<1000
        assert not days.duplicated(['bus_route','payment_date']).any()
        if len(days):
            grouped=days.groupby('payment_date')[['published_boardings','published_transfers']].sum()
            pd.testing.assert_frame_equal(grouped,denom.set_index('payment_date')[grouped.columns],check_dtype=False)
            assert days.published_boardings.ge(0).all()
            assert days.reported_hours.between(1,25).all()
            frozen=pd.read_csv(ROOT/'data/processed/new_york/daily_clean.csv',dtype={'bus_route':'string'},parse_dates=['payment_date'])
            overlap=days.merge(frozen[['payment_date','bus_route','published_boardings']],on=['payment_date','bus_route'],suffixes=('_now','_frozen'),validate='one_to_one')
            overlap['changed']=overlap.published_boardings_now.ne(overlap.published_boardings_frozen)
            overlap.to_csv(out/'revision_comparison.csv',index=False)
            result.update(rows=len(days),first_date=str(days.payment_date.min().date()),
                last_date=str(days.payment_date.max().date()),overlap_rows=len(overlap),
                changed_overlap_rows=int(overlap.changed.sum()),
                later_route_dates=int(days.payment_date.gt(frozen.payment_date.max()).sum()),
                denominator_checks_passed=True)
        else:
            result.update(rows=0,later_route_dates=0,denominator_checks_passed=denom.empty)
    (out/'poll_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    report=ROOT/'reports/forecasting'
    report.mkdir(parents=True,exist_ok=True)
    (report/'latest_source_poll.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    return result


if __name__=='__main__':
    run()
