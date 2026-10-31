"""Download a bounded MTA bus pilot with exact queries and immutable source receipts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.parse import urlencode
import urllib.request
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/new_york'
REPORT = ROOT / 'reports/week1/collection'
START, END = date(2026, 7, 1), date(2026, 10, 1)
BASE = 'https://data.ny.gov/resource/gxb3-akrn'
FEEDS = {'bronx': 'bx', 'brooklyn': 'b', 'manhattan': 'm', 'queens': 'q',
         'staten_island': 'si', 'bus_company': 'busco'}
ARCHIVE = 'https://files.mobilitydatabase.org/mdb-513/mdb-513-202609030140/mdb-513-202609030140.zip'


def download(url, path, kind):
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = path.with_suffix(path.suffix + '.receipt.json')
    if path.exists() and receipt.exists():
        result = json.loads(receipt.read_text())
        if result['url'] != url or hashlib.sha256(path.read_bytes()).hexdigest() != result['sha256']:
            raise ValueError(f'Existing source receipt mismatch: {path}')
        return result
    if path.exists():
        raise ValueError(f'Unreceipted file exists; inspect before replacing: {path}')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'RouteRanker reproducible research'})
            with urllib.request.urlopen(req, timeout=120) as response:
                body = response.read(150 * 1024 * 1024 + 1)
                final_url = response.url
            if len(body) > 150 * 1024 * 1024:
                raise ValueError('Resource exceeds 150 MB bound')
            if kind == 'zip':
                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                    if archive.testzip() is not None:
                        raise ValueError('ZIP integrity check failed')
            if kind == 'json':
                json.loads(body)
            if kind == 'pdf' and not body.startswith(b'%PDF'):
                raise ValueError('Expected PDF')
            if kind == 'csv' and body.lstrip().startswith(b'<'):
                raise ValueError('Expected CSV, received markup')
            result = dict(url=url, final_url=final_url, local_path=path.relative_to(ROOT).as_posix(),
                          bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                          retrieved_utc=datetime.now(timezone.utc).isoformat(), kind=kind)
            path.write_bytes(body)
            receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
            return result
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 + attempt * 2)


def source_query(params, filename):
    return download(BASE + '.csv?' + urlencode(params), RAW / 'ridership' / filename, 'csv')


def collect_week(period):
    start, end = period
    where = f"transit_timestamp >= '{start.isoformat()}T00:00:00' AND transit_timestamp < '{end.isoformat()}T00:00:00'"
    params = {'$select': 'transit_timestamp,bus_route,sum(ridership) as ridership,sum(transfers) as transfers,count(*) as source_rows',
              '$where': where, '$group': 'transit_timestamp,bus_route',
              '$order': 'transit_timestamp,bus_route', '$limit': 100000}
    receipt = source_query(params, f'{start}_route_hour.csv')
    frame = pd.read_csv(ROOT / receipt['local_path'])
    if len(frame) >= 100000:
        raise ValueError('Query hit the row limit; split period further')
    # Independent grouping/query from publisher, not a denominator derived from local hourly rows.
    daily = source_query({'$select': 'date_trunc_ymd(transit_timestamp) as service_date,sum(ridership) as ridership,sum(transfers) as transfers,count(*) as source_rows',
                          '$where': where, '$group': 'service_date', '$order': 'service_date', '$limit': 100},
                         f'{start}_daily_denominator.csv')
    print(f'Demand {start} to {end}: {len(frame):,} route-hours', flush=True)
    return [receipt, daily]


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    receipts = []
    metadata = download('https://data.ny.gov/api/views/gxb3-akrn.json', RAW / 'sources/ridership_metadata.json', 'json')
    receipts.append(metadata)
    info = json.loads((ROOT / metadata['local_path']).read_text())
    for attachment in info.get('metadata', {}).get('attachments', []):
        try:
            url = 'https://data.ny.gov/api/views/gxb3-akrn/files/' + attachment['assetId'] + '?' + urlencode({'filename': attachment['filename']})
            receipts.append(download(url, RAW / 'sources' / attachment['filename'], 'pdf'))
        except Exception as exc:
            print('Attachment unavailable:', attachment['filename'], str(exc), flush=True)
    windows = []
    start = START
    while start < END:
        end = min(start + timedelta(days=7), END)
        windows.append((start, end)); start = end
    with ThreadPoolExecutor(max_workers=2) as pool:
        for weekly in pool.map(collect_week, windows):
            receipts.extend(weekly)
            (REPORT / 'manifest.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')
    receipts.append(source_query({'$where': f"transit_timestamp >= '{START}T00:00:00' AND transit_timestamp < '{END}T00:00:00'",
                                  '$order': 'transit_timestamp,bus_route,payment_method,fare_class_category', '$limit': 10000}, 'raw_fare_category_sample_10000.csv'))
    for name, code in FEEDS.items():
        receipt = download(f'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_{code}.zip', RAW / f'gtfs/current/{name}.zip', 'zip')
        receipts.append(receipt)
        (REPORT / 'manifest.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')
        print('Official GTFS:', name, receipt['bytes'], flush=True)
    try:
        receipts.append(download(ARCHIVE, RAW / 'gtfs/archive/manhattan_20260903.zip', 'zip'))
        print('Historical Manhattan feed archived', flush=True)
    except Exception as exc:
        (REPORT / 'archive_access_issue.txt').write_text(str(exc), encoding='utf-8')
        print('Archive unavailable:', exc, flush=True)
    (REPORT / 'manifest.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')
    coverage = {'pilot_start_inclusive': str(START), 'pilot_end_exclusive': str(END),
                'timezone': 'America/New_York', 'demand_kind': 'fare-derived boarding estimates; publisher-side route-hour aggregates',
                'source_dataset': 'gxb3-akrn', 'limitations': [
                    'Transfers are a subset of ridership, not additional riders.',
                    'No onboard loads, bus capacities or crowding labels.',
                    'No zero filling of absent observations.',
                    'Current GTFS is not a historical timetable.',
                    'Raw fare-category uniqueness/missingness checked only on the bounded 10,000-row sample.',
                    'Pilot supports inspection, not annual seasonality claims.']}
    (REPORT / 'coverage.json').write_text(json.dumps(coverage, indent=2), encoding='utf-8')
    print('Collection finished. Source receipts:', len(receipts), flush=True)


if __name__ == '__main__':
    main()
