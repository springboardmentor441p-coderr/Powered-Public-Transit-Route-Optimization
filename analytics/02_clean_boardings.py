"""
Step 2: Validate boarding observations.
- Retains route IDs as normalized strings (preserving prefixes like N, X).
- Parses US dates explicitly.
- Strips thousands separators, preserves genuine zeros, quarantines route/date conflicts.
"""
import os
import glob
import pandas as pd

RAW_RIDERSHIP_DIR = "data/raw/ridership"
PROCESSED_DIR = "data/processed"

def run():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    csv_files = sorted(glob.glob(os.path.join(RAW_RIDERSHIP_DIR, "*.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No ridership CSV files found in {RAW_RIDERSHIP_DIR}")

    raw_df = pd.read_csv(csv_files[-1], dtype={"route": str, "date": str, "daytype": str, "rides": str})
    raw_df["route"] = raw_df["route"].str.strip()
    raw_df["daytype"] = raw_df["daytype"].str.strip().str.upper()
    raw_df["date"] = pd.to_datetime(raw_df["date"].str.strip(), format="mixed").dt.date
    raw_df["rides"] = (
        raw_df["rides"].astype(str).str.replace(",", "", regex=False).str.strip().astype(int)
    )

    # Validate non-negative and valid daytypes
    valid_mask = (
        raw_df["route"].notna()
        & (raw_df["route"] != "")
        & raw_df["date"].notna()
        & raw_df["daytype"].isin(["W", "A", "U"])
        & (raw_df["rides"] >= 0)
    )
    df = raw_df[valid_mask].copy()

    # Deduplicate exact copies
    df = df.drop_duplicates(subset=["route", "date", "daytype", "rides"])

    # Quarantine conflicting duplicate route/date rows rather than summing/averaging
    dup_keys = df.duplicated(subset=["route", "date"], keep=False)
    conflicts = df[dup_keys].copy()
    clean = df[~dup_keys].sort_values(["route", "date"]).reset_index(drop=True)
    clean["dataset_id"] = os.path.basename(csv_files[-1])

    clean.to_parquet(os.path.join(PROCESSED_DIR, "boardings_clean.parquet"), index=False)
    conflicts.to_parquet(os.path.join(PROCESSED_DIR, "boardings_conflicts.parquet"), index=False)
    zero_count = int((clean["rides"] == 0).sum())
    print(f"[02_clean_boardings] Clean rows: {len(clean)} | Conflicts quarantined: {len(conflicts)} | Genuine zeros: {zero_count}")

if __name__ == "__main__":
    run()
