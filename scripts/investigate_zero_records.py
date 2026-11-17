
import pandas as pd

FILE_PATH = "data/hourly_ridership_training.csv"

df = pd.read_csv(FILE_PATH)
df["timestamp"] = pd.to_datetime(df["timestamp"])

df["year_month"] = df["timestamp"].dt.to_period("M")
df["hour"] = df["timestamp"].dt.hour
df["is_zero"] = df["total_passengers"] == 0

print("INVESTIGATING ZERO-PASSENGER RECORDS")
print("=" * 55)

print("\n1. ZERO RECORDS BY ROUTE AND MONTH")
print("-" * 55)

monthly = (
    df[df["is_zero"]]
    .groupby(["bus_route", "year_month"])
    .size()
    .unstack(fill_value=0)
)

print(monthly.to_string())

print("\n2. JANUARY 2026 ZERO RECORDS BY ROUTE")
print("-" * 55)

jan = df[
    (df["year_month"] == "2026-01") &
    (df["is_zero"])
]

print(jan.groupby("bus_route").size())

print("\n3. JANUARY 2026 ZERO RECORDS BY ROUTE AND HOUR")
print("-" * 55)

print(
    jan.groupby(["bus_route", "hour"])
    .size()
    .to_string()
)

print("\n4. ZERO RECORDS ON SELECTED ROUTES")
print("-" * 55)

for route in ["M15+", "BX12+"]:
    route_data = df[
        (df["bus_route"] == route) &
        (df["is_zero"])
    ].sort_values("timestamp")

    print(f"\n{route}")
    print("Total zero records:", len(route_data))
    print("First 20 zero timestamps:")

    print(
        route_data["timestamp"]
        .head(20)
        .to_string(index=False)
    )

print("\nINVESTIGATION COMPLETED.")
