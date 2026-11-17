
import pandas as pd

FILE_PATH = "data/hourly_ridership_training.csv"

df = pd.read_csv(FILE_PATH)
df["timestamp"] = pd.to_datetime(df["timestamp"])

df["year"] = df["timestamp"].dt.year
df["month"] = df["timestamp"].dt.month
df["hour"] = df["timestamp"].dt.hour

df["is_zero"] = df["total_passengers"] == 0

print("ZERO-PASSENGER ANALYSIS")
print("=" * 50)

print("\n1. OVERALL ZERO-PASSENGER RECORDS")
print("--------------------------------")
zero_count = df["is_zero"].sum()
total_count = len(df)

print("Zero records:", zero_count)
print("Non-zero records:", total_count - zero_count)
print("Zero percentage:", round(zero_count / total_count * 100, 2), "%")

print("\n2. ZERO RECORDS BY ROUTE")
print("--------------------------------")
route_summary = df.groupby("bus_route").agg(
    total_records=("total_passengers", "size"),
    zero_records=("is_zero", "sum")
)

route_summary["zero_percentage"] = (
    route_summary["zero_records"] /
    route_summary["total_records"] * 100
).round(2)

print(route_summary)

print("\n3. ZERO RECORDS BY YEAR")
print("--------------------------------")
print(
    df.groupby("year")["is_zero"]
    .agg(["sum", "count"])
)

print("\n4. ZERO RECORDS BY HOUR")
print("--------------------------------")
print(
    df.groupby("hour")["is_zero"]
    .agg(["sum", "count"])
)

print("\n5. ZERO RECORDS BY MONTH")
print("--------------------------------")
print(
    df.groupby(["year", "month"])["is_zero"]
    .sum()
)

print("\nZERO-PASSENGER ANALYSIS COMPLETED.")
