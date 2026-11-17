import pandas as pd

CLEANED_FILE = "data/hourly_ridership_training_cleaned.csv"
AUDIT_FILE = "data/suspicious_ridership_records.csv"

SUSPICIOUS_DATES = [
    "2026-01-10",
    "2026-01-11",
    "2026-01-12",
    "2026-01-13",
    "2026-01-14",
    "2026-01-15"
]

EXPECTED_RECORDS = 115776
EXPECTED_EXCLUDED = 1152
EXPECTED_ROUTES = 8

print("VALIDATING CLEANED RIDERSHIP DATASET")
print("=" * 60)

df = pd.read_csv(CLEANED_FILE)
audit = pd.read_csv(AUDIT_FILE)

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
audit["timestamp"] = pd.to_datetime(audit["timestamp"], errors="coerce")

duplicates = df.duplicated(
    subset=["timestamp", "bus_route"]
).sum()

remaining_suspicious = df[
    df["timestamp"].dt.strftime("%Y-%m-%d").isin(SUSPICIOUS_DATES)
]

missing_values = df.isnull().sum().sum()
negative_counts = (df["total_passengers"] < 0).sum()

print("\n1. BASIC DATASET INFORMATION")
print("-" * 60)
print("Cleaned records:", len(df))
print("Audit records:", len(audit))
print("Unique routes:", df["bus_route"].nunique())
print("Date range:", df["timestamp"].min(), "to", df["timestamp"].max())

print("\n2. DATA QUALITY")
print("-" * 60)
print("Missing values:", missing_values)
print("Invalid timestamps:", df["timestamp"].isna().sum())
print("Duplicate route-hour records:", duplicates)
print("Negative passenger counts:", negative_counts)
print("Zero passenger records:", (df["total_passengers"] == 0).sum())
print("Non-zero passenger records:", (df["total_passengers"] > 0).sum())

print("\n3. EXCLUSION AUDIT")
print("-" * 60)
print("Records from excluded dates still present:", len(remaining_suspicious))
print("Audit file records:", len(audit))

print("\n4. RECORDS PER ROUTE")
print("-" * 60)
print(df["bus_route"].value_counts().sort_index())

checks = {
    "Expected cleaned record count": len(df) == EXPECTED_RECORDS,
    "Expected audit record count": len(audit) == EXPECTED_EXCLUDED,
    "Eight routes retained": df["bus_route"].nunique() == EXPECTED_ROUTES,
    "No missing values": missing_values == 0,
    "No invalid timestamps": df["timestamp"].isna().sum() == 0,
    "No duplicate route-hour records": duplicates == 0,
    "No negative passenger counts": negative_counts == 0,
    "Suspicious dates excluded": len(remaining_suspicious) == 0,
    "Audit timestamps valid": audit["timestamp"].isna().sum() == 0
}

print("\n5. FINAL VALIDATION STATUS")
print("-" * 60)

for check, passed in checks.items():
    print(f"{check}: {'PASS' if passed else 'FAIL'}")

if all(checks.values()):
    print("\nALL VALIDATION CHECKS PASSED.")
else:
    print("\nVALIDATION NEEDS ATTENTION.")