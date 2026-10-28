"""
analytics/02_clean_boardings.py
RouteRanker Data Pipeline - Step 2: Clean Daily Boardings

Reads CTA daily ridership CSV, cleans string-formatted numbers, enforces strict string
route IDs, validates date formats and daytypes, preserves valid zero boardings, and writes
data/processed/boardings_clean.parquet.
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def clean_boardings():
    print("=" * 60)
    print("ROUTERANKER PIPELINE: STEP 2 - CLEAN DAILY BOARDINGS")
    print("=" * 60)

    # Locate ridership CSV dynamically
    csv_files = list(DATA_DIR.glob("*Ridership*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No ridership CSV found in {DATA_DIR}")
    csv_path = csv_files[0]
    print(f"[LOADING] {csv_path.name}...")

    # Load enforcing route as string
    df = pd.read_csv(csv_path, dtype={"route": str, "daytype": str, "rides": str})
    raw_row_count = len(df)
    print(f"  Raw row count: {raw_row_count:,}")

    # 1. Clean route strings
    df["route"] = df["route"].astype(str).str.strip()

    # 2. Clean dates
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")
    invalid_dates = df["date"].isna().sum()
    if invalid_dates > 0:
        print(f"  [WARNING] Dropping {invalid_dates} rows with unparseable dates")
        df = df.dropna(subset=["date"])

    # 3. Clean rides numbers (strip commas, whitespace, convert to numeric)
    rides_cleaned = df["rides"].astype(str).str.replace(",", "", regex=False).str.strip()
    df["rides"] = pd.to_numeric(rides_cleaned, errors="coerce")
    invalid_rides = df["rides"].isna().sum()
    if invalid_rides > 0:
        print(f"  [WARNING] Dropping {invalid_rides} unparseable rides values")
        df = df.dropna(subset=["rides"])

    df["rides"] = df["rides"].astype(np.int64)

    # 4. Clean daytype
    df["daytype"] = df["daytype"].astype(str).str.strip().str.upper()
    valid_daytypes = {"W", "A", "U"}
    invalid_dt = (~df["daytype"].isin(valid_daytypes)).sum()
    if invalid_dt > 0:
        print(f"  [WARNING] Found {invalid_dt} unexpected daytype values; filtering to {valid_daytypes}")
        df = df[df["daytype"].isin(valid_daytypes)]

    # 5. Check duplicate keys (route, date)
    key_dupes = df.duplicated(subset=["route", "date"], keep="first").sum()
    if key_dupes > 0:
        print(f"  [DEDUP] Quarantining/dropping {key_dupes} duplicate (route, date) observations")
        df = df.drop_duplicates(subset=["route", "date"], keep="first")
    else:
        print("  [INTEGRITY] 0 duplicate (route, date) records found. Key is strictly unique.")

    # 6. Check genuine zeros
    zero_rides = (df["rides"] == 0).sum()
    print(f"  [PRESERVED] Preserved {zero_rides} valid zero-boarding observations.")

    # 7. Sort chronologically by route and date
    df = df.sort_values(["route", "date"]).reset_index(drop=True)

    # Summary
    min_date = df["date"].min().strftime("%Y-%m-%d")
    max_date = df["date"].max().strftime("%Y-%m-%d")
    n_routes = df["route"].nunique()
    print(f"\n[SUMMARY] Cleaned Dataset:")
    print(f"  Observations: {len(df):,}")
    print(f"  Unique Routes: {n_routes}")
    print(f"  Date Span: {min_date} to {max_date}")
    print(f"  Mean Boardings: {df['rides'].mean():.2f}")
    print(f"  Median Boardings: {df['rides'].median():.2f}")

    # Export to Parquet
    out_path = PROCESSED_DIR / "boardings_clean.parquet"
    df.to_parquet(out_path, engine="pyarrow", index=False)
    print(f"[EXPORTED] {out_path.relative_to(WORKSPACE_ROOT)} ({out_path.stat().st_size / (1024*1024):.2f} MB)")
    return df

if __name__ == "__main__":
    clean_boardings()
