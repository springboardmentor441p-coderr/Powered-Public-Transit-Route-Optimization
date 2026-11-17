
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

INPUT_FILE = "data/hourly_ridership_training_cleaned.csv"

CHART_DIR = Path("charts")
DATA_DIR = Path("data")

CHART_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

print("ANALYZING PASSENGER DEMAND PATTERNS")
print("=" * 60)

df = pd.read_csv(INPUT_FILE)

df["timestamp"] = pd.to_datetime(df["timestamp"])

# Extract useful time information
df["hour"] = df["timestamp"].dt.hour
df["day_of_week"] = df["timestamp"].dt.dayofweek
df["day_name"] = df["timestamp"].dt.day_name()
df["month"] = df["timestamp"].dt.month
df["month_name"] = df["timestamp"].dt.strftime("%b %Y")
df["is_weekend"] = df["day_of_week"] >= 5

# 1. Average passenger demand by hour
hourly = (
    df.groupby("hour")["total_passengers"]
    .mean()
    .reset_index()
)

hourly.to_csv(DATA_DIR / "hourly_demand_patterns.csv", index=False)

print("\n1. AVERAGE DEMAND BY HOUR")
print("-" * 60)
print(hourly.round(2).to_string(index=False))

plt.figure(figsize=(10, 5))
plt.plot(hourly["hour"], hourly["total_passengers"], marker="o")
plt.title("Average Passenger Demand by Hour")
plt.xlabel("Hour of Day")
plt.ylabel("Average Passengers per Route-Hour")
plt.xticks(range(24))
plt.grid(True)
plt.tight_layout()
plt.savefig(CHART_DIR / "average_demand_by_hour.png")
plt.close()

# 2. Average demand by day of the week
weekday_order = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

weekday = (
    df.groupby("day_name")["total_passengers"]
    .mean()
    .reindex(weekday_order)
    .reset_index()
)

weekday.to_csv(DATA_DIR / "weekday_demand_patterns.csv", index=False)

print("\n2. AVERAGE DEMAND BY DAY OF WEEK")
print("-" * 60)
print(weekday.round(2).to_string(index=False))

plt.figure(figsize=(10, 5))
plt.bar(weekday["day_name"], weekday["total_passengers"])
plt.title("Average Passenger Demand by Day of Week")
plt.xlabel("Day")
plt.ylabel("Average Passengers per Route-Hour")
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(CHART_DIR / "average_demand_by_weekday.png")
plt.close()

# 3. Weekday versus weekend comparison
weekend = (
    df.groupby("is_weekend")["total_passengers"]
    .mean()
    .rename(index={False: "Weekday", True: "Weekend"})
    .reset_index()
)

weekend.to_csv(DATA_DIR / "weekday_weekend_comparison.csv", index=False)

print("\n3. WEEKDAY VS WEEKEND")
print("-" * 60)
print(weekend.round(2).to_string(index=False))

# 4. Average demand by month
monthly = (
    df.groupby("month_name")["total_passengers"]
    .mean()
    .reset_index()
)

monthly.to_csv(DATA_DIR / "monthly_demand_patterns.csv", index=False)

print("\n4. AVERAGE DEMAND BY MONTH")
print("-" * 60)
print(monthly.round(2).to_string(index=False))

plt.figure(figsize=(13, 5))
plt.plot(monthly["month_name"], monthly["total_passengers"], marker="o")
plt.title("Average Passenger Demand by Month")
plt.xlabel("Month")
plt.ylabel("Average Passengers per Route-Hour")
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()
plt.savefig(CHART_DIR / "average_demand_by_month.png")
plt.close()

# 5. Average demand by bus route
route = (
    df.groupby("bus_route")["total_passengers"]
    .mean()
    .sort_values(ascending=False)
    .reset_index()
)

route.to_csv(DATA_DIR / "route_demand_comparison.csv", index=False)

print("\n5. AVERAGE DEMAND BY ROUTE")
print("-" * 60)
print(route.round(2).to_string(index=False))

plt.figure(figsize=(10, 5))
plt.bar(route["bus_route"], route["total_passengers"])
plt.title("Average Passenger Demand by Bus Route")
plt.xlabel("Bus Route")
plt.ylabel("Average Passengers per Route-Hour")
plt.tight_layout()
plt.savefig(CHART_DIR / "average_demand_by_route.png")
plt.close()

print("\nANALYSIS COMPLETED")
print("-" * 60)
print("Summary CSV files saved in:", DATA_DIR)
print("Charts saved in:", CHART_DIR)
