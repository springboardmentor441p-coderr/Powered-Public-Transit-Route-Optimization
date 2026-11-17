
import pandas as pd

INPUT_FILE = "data/hourly_ridership_training.csv"
OUTPUT_FILE = "data/hourly_ridership_training_cleaned.csv"
AUDIT_FILE = "data/suspicious_ridership_records.csv"

# Dates containing a complete block of zero-ridership observations.
# These are treated as suspected reporting anomalies, not confirmed errors.
SUSPICIOUS_DATES = [
    "2026-01-10",
    "2026-01-11",
    "2026-01-12",
    "2026-01-13",
    "2026-01-14",
    "2026-01-15"
]

print("Cleaning hourly passenger ridership data...")
print("=" * 60)

df = pd.read_csv(INPUT_FILE)

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

if df["timestamp"].isna().any():
    raise ValueError("Invalid timestamps found in the original dataset.")

original_count = len(df)

date_values = df["timestamp"].dt.strftime("%Y-%m-%d")
suspicious_mask = date_values.isin(SUSPICIOUS_DATES)

# Preserve excluded observations for audit and reproducibility.
suspicious_records = df.loc[suspicious_mask].copy()
suspicious_records.to_csv(AUDIT_FILE, index=False)

# Create the cleaned dataset.
cleaned_df = df.loc[~suspicious_mask].copy()
cleaned_df.to_csv(OUTPUT_FILE, index=False)

print("\nCLEANING SUMMARY")
print("-" * 60)
print("Original records:", original_count)
print("Excluded records:", len(suspicious_records))
print("Remaining records:", len(cleaned_df))
print("Routes retained:", cleaned_df["bus_route"].nunique())

print("\nAudit file:", AUDIT_FILE)
print("Cleaned dataset:", OUTPUT_FILE)

print("\nCleaning completed successfully.")
