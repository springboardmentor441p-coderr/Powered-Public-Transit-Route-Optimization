"""
Download MTA Bus Hourly Ridership (data.ny.gov, dataset gxb3-akrn) for Manhattan routes.

The server sums ridership/transfers over payment_method and fare_class_category,
so we get one row per (transit_timestamp, bus_route). Routes are filtered to codes
starting with "M". Each month is saved to data/raw/ridership/YYYY-MM.csv.

Raw files are write-once: an existing month file is never overwritten.

Usage:
    python src/fetch_ridership.py 2026-01 2026-09      # inclusive month range
    python src/fetch_ridership.py 2026-03              # single month

Optional: set NY_APP_TOKEN (free from data.ny.gov) to avoid throttling.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

URL = "https://data.ny.gov/resource/gxb3-akrn.json"
PAGE = 50_000
TIMEOUT = 120
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "ridership"

HEADERS = {}
if os.getenv("NY_APP_TOKEN"):
    HEADERS["X-App-Token"] = os.environ["NY_APP_TOKEN"]


def _ts(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def fetch_range(start: datetime, end: datetime, retries: int = 3) -> pd.DataFrame:
    """Fetch aggregated rows for start <= transit_timestamp < end, paging by 50k."""
    rows, offset = [], 0
    while True:
        params = {
            "$select": "transit_timestamp, bus_route, "
                       "sum(ridership) AS ridership, sum(transfers) AS transfers",
            "$where": f"transit_timestamp >= '{_ts(start)}' AND transit_timestamp < '{_ts(end)}' "
                      f"AND starts_with(bus_route, 'M')",
            "$group": "transit_timestamp, bus_route",
            "$order": "transit_timestamp, bus_route",
            "$limit": PAGE,
            "$offset": offset,
        }
        for attempt in range(1, retries + 1):
            try:
                r = requests.get(URL, params=params, headers=HEADERS, timeout=TIMEOUT)
                r.raise_for_status()
                batch = r.json()
                break
            except (requests.Timeout, requests.ConnectionError):
                if attempt == retries:
                    raise
                time.sleep(5 * attempt)
            except requests.HTTPError:
                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(10 * attempt)
                    continue
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        if isinstance(batch, dict) and batch.get("error"):
            raise RuntimeError(batch.get("message"))
        if not batch:
            break
        rows += batch
        offset += PAGE
        if len(batch) < PAGE:
            break
    return pd.DataFrame(rows, columns=["transit_timestamp", "bus_route", "ridership", "transfers"])


def fetch_month(month: str) -> pd.DataFrame:
    """Fetch a whole month; fall back to week-sized chunks if the server times out."""
    start = datetime.strptime(month, "%Y-%m")
    end = (start + timedelta(days=32)).replace(day=1)
    try:
        return fetch_range(start, end)
    except (requests.Timeout, requests.ConnectionError) as e:
        print(f"  {month}: month request failed ({type(e).__name__}); fetching weekly")
    parts, cur = [], start
    while cur < end:
        nxt = min(cur + timedelta(days=7), end)
        print(f"    {cur:%Y-%m-%d} -> {nxt:%Y-%m-%d}")
        parts.append(fetch_range(cur, nxt))
        cur = nxt
    return pd.concat(parts, ignore_index=True)


def month_list(first: str, last: str) -> list[str]:
    cur, stop, out = datetime.strptime(first, "%Y-%m"), datetime.strptime(last, "%Y-%m"), []
    while cur <= stop:
        out.append(cur.strftime("%Y-%m"))
        cur = (cur + timedelta(days=32)).replace(day=1)
    return out


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    months = month_list(argv[0], argv[1] if len(argv) > 1 else argv[0])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"App token: {'yes' if HEADERS else 'no (may be throttled)'}")
    for m in months:
        path = OUT_DIR / f"{m}.csv"
        if path.exists():
            print(f"{m}: exists, skipping (raw files are never overwritten)")
            continue
        t0 = time.time()
        df = fetch_month(m)
        if df.empty:
            print(f"{m}: no rows returned, nothing saved")
            continue
        tmp = path.with_suffix(".csv.part")
        df.to_csv(tmp, index=False)
        tmp.rename(path)
        print(f"{m}: {len(df):,} rows, {df['bus_route'].nunique()} routes, "
              f"{df['transit_timestamp'].min()} .. {df['transit_timestamp'].max()} "
              f"({time.time() - t0:.0f}s) -> {path.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
