
import pandas as pd

FILE_PATH = "data/hourly_ridership_training.csv"

ROUTES = [
    "M15+", "M15", "B6", "Q58",
    "Q44+", "BX12+", "Q27", "M101"
]

print("VALIDATING HOURLY RIDERSHIP DATASET...\n")

df = pd.read_csv(FILE_PATH)

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

df["total_passengers"] = pd.to_numeric(
    df["total_passengers"],
    errors="coerce"
)

print("1. BASIC DATASET INFORMATION")
print("--------------------------------")
print("Total records:", len(df))
print("Unique routes:", df["bus_route"].nunique())
print("First timestamp:", df["timestamp"].min())
print("Last timestamp:", df["timestamp"].max())

print("\n2. RECORDS PER ROUTE")
print("--------------------------------")
print(df["bus_route"].value_counts().sort_index())

print("\n3. DATA QUALITY CHECKS")
print("--------------------------------")
print("Duplicate route-hour records:",
      df.duplicated(["timestamp", "bus_route"]).sum())

print("Missing timestamps:", df["timestamp"].isna().sum())
print("Missing route names:", df["bus_route"].isna().sum())
print("Missing passenger counts:",
      df["total_passengers"].isna().sum())

print("Negative passenger counts:",
      (df["total_passengers"] < 0).sum())

print("\n4. ROUTE VALIDATION")
print("--------------------------------")

actual_routes = set(df["bus_route"].dropna())
expected_routes = set(ROUTES)

print("Missing routes:", sorted(expected_routes - actual_routes))
print("Unexpected routes:", sorted(actual_routes - expected_routes))

print("\n5. HOURLY COVERAGE")
print("--------------------------------")

expected_hours = pd.date_range(
    start="2025-01-01 00:00:00",
    end="2026-09-01 23:00:00",
    freq="h"
)

expected_index = pd.MultiIndex.from_product(
    [expected_hours, ROUTES],
    names=["timestamp", "bus_route"]
)

actual_index = pd.MultiIndex.from_frame(
    df[["timestamp", "bus_route"]].dropna()
)

missing_records = expected_index.difference(actual_index)

print("Expected route-hour records:", len(expected_index))
print("Actual unique route-hour records:", len(actual_index))
print("Missing route-hour records:", len(missing_records))

if len(missing_records) > 0:
    print("\nFirst 20 missing records:")
    print(missing_records[:20].tolist())

print("\n6. PASSENGER COUNT SUMMARY")
print("--------------------------------")
print("Total passengers:", df["total_passengers"].sum())
print("Minimum passengers:", df["total_passengers"].min())
print("Maximum passengers:", df["total_passengers"].max())
print("Average passengers per route-hour:",
      round(df["total_passengers"].mean(), 2))

print("\nVALIDATION COMPLETED.")
