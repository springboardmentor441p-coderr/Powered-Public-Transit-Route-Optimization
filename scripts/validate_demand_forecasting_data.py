
import pandas as pd

FILE = "data/demand_forecasting_features.csv"

print("Validating demand forecasting dataset...")

df = pd.read_csv(FILE)

required_columns = [
    "timestamp",
    "bus_route",
    "total_passengers",
    "hour",
    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend",
    "demand_previous_hour",
    "demand_previous_day",
    "demand_previous_week"
]

print("\nDATASET OVERVIEW")
print("=" * 50)

print("Total records:", len(df))
print("Total columns:", len(df.columns))
print("Routes:", sorted(df["bus_route"].unique()))

# Check required columns
missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

print("\n1. Required columns present:",
      "PASS" if not missing_columns else "FAIL")

if missing_columns:
    print("Missing columns:", missing_columns)

# Check missing values
missing_values = df[required_columns].isnull().sum()

print("\n2. Missing values:")
print(missing_values)

print(
    "Missing-value check:",
    "PASS" if missing_values.sum() == 0 else "FAIL"
)

# Check duplicate route-hour records
df["timestamp"] = pd.to_datetime(df["timestamp"])

duplicates = df.duplicated(
    subset=["timestamp", "bus_route"]
).sum()

print("\n3. Duplicate route-hour records:", duplicates)
print("Duplicate check:", "PASS" if duplicates == 0 else "FAIL")

# Check negative values
numeric_columns = [
    "total_passengers",
    "demand_previous_hour",
    "demand_previous_day",
    "demand_previous_week"
]

negative_counts = (
    df[numeric_columns] < 0
).sum()

print("\n4. Negative values:")
print(negative_counts)

print(
    "Negative-value check:",
    "PASS" if negative_counts.sum() == 0 else "FAIL"
)

# Check time feature ranges
valid_ranges = {
    "hour": (0, 23),
    "day_of_week": (0, 6),
    "day_of_month": (1, 31),
    "month": (1, 12),
    "is_weekend": (0, 1)
}

print("\n5. Time feature range checks:")

range_pass = True

for column, (minimum, maximum) in valid_ranges.items():
    valid = df[column].between(minimum, maximum).all()

    print(
        f"{column}:",
        "PASS" if valid else "FAIL"
    )

    if not valid:
        range_pass = False

# Check route count
route_count = df["bus_route"].nunique()

print("\n6. Route count:", route_count)
print("Route check:", "PASS" if route_count == 8 else "FAIL")

# Final result
checks = [
    not missing_columns,
    missing_values.sum() == 0,
    duplicates == 0,
    negative_counts.sum() == 0,
    range_pass,
    route_count == 8
]

print("\nFINAL VALIDATION RESULT")
print("=" * 50)

if all(checks):
    print("ALL VALIDATION CHECKS PASSED")
else:
    print("SOME VALIDATION CHECKS FAILED")

print("\nValidation completed.")
