
import pandas as pd

FILE_PATH = "data/hourly_ridership_training.csv"

df = pd.read_csv(FILE_PATH)
df["timestamp"] = pd.to_datetime(df["timestamp"])

df = df[
    (df["timestamp"] >= "2026-01-01") &
    (df["timestamp"] < "2026-02-01")
].copy()

df["date"] = df["timestamp"].dt.date
df["is_zero"] = df["total_passengers"] == 0

print("JANUARY 2026 — DAILY ZERO INVESTIGATION")
print("=" * 60)

daily = df.groupby(["bus_route", "date"]).agg(
    total_hours=("timestamp", "count"),
    zero_hours=("is_zero", "sum")
).reset_index()

print("\n1. DATES WITH 24 ZERO HOURS")
print("-" * 60)

full_zero_days = daily[daily["zero_hours"] == 24]

if full_zero_days.empty:
    print("No route has a complete day of zero records.")
else:
    print(full_zero_days.to_string(index=False))

print("\n2. DAILY ZERO COUNTS FOR EACH ROUTE")
print("-" * 60)

for route in sorted(df["bus_route"].unique()):
    route_daily = daily[daily["bus_route"] == route]

    print(f"\n{route}")
    print(
        route_daily[
            route_daily["zero_hours"] > 0
        ].to_string(index=False)
    )

print("\n3. DATES WHEN ALL EIGHT ROUTES HAVE ZERO RIDERS")
print("-" * 60)

date_route_zeros = df.groupby("date").agg(
    zero_route_hours=("is_zero", "sum"),
    route_hour_records=("bus_route", "count")
)

print(
    date_route_zeros[
        date_route_zeros["zero_route_hours"] == 8
    ].to_string()
)

print("\nINVESTIGATION COMPLETED.")
