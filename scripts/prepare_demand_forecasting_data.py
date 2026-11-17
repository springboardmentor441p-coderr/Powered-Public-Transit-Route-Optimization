
import pandas as pd

INPUT_FILE = "data/hourly_ridership_training_cleaned.csv"
OUTPUT_FILE = "data/demand_forecasting_features.csv"

print("Preparing passenger-demand forecasting dataset...")

# Load cleaned ridership data
df = pd.read_csv(INPUT_FILE)

# Convert columns to appropriate data types
df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

df["total_passengers"] = pd.to_numeric(
    df["total_passengers"],
    errors="coerce"
)

df = df.dropna(
    subset=["timestamp", "bus_route", "total_passengers"]
)

# Sort records by route and timestamp
df = df.sort_values(
    ["bus_route", "timestamp"]
).reset_index(drop=True)

# Create time-based features
df["hour"] = df["timestamp"].dt.hour
df["day_of_week"] = df["timestamp"].dt.dayofweek
df["day_of_month"] = df["timestamp"].dt.day
df["month"] = df["timestamp"].dt.month

df["is_weekend"] = (
    df["day_of_week"] >= 5
).astype(int)

# Create historical demand features
history = df[
    ["bus_route", "timestamp", "total_passengers"]
].copy()

lag_features = [
    (1, "demand_previous_hour"),
    (24, "demand_previous_day"),
    (168, "demand_previous_week")
]

for lag, feature_name in lag_features:

    previous = history.copy()

    previous["timestamp"] = (
        previous["timestamp"]
        + pd.Timedelta(hours=lag)
    )

    previous = previous.rename(
        columns={
            "total_passengers": feature_name
        }
    )

    df = df.merge(
        previous,
        on=["bus_route", "timestamp"],
        how="left"
    )

# Remove records without all historical demand values
feature_columns = [
    "demand_previous_hour",
    "demand_previous_day",
    "demand_previous_week"
]

before = len(df)

df = df.dropna(
    subset=feature_columns
).reset_index(drop=True)

removed = before - len(df)

# Save the prepared dataset
df.to_csv(OUTPUT_FILE, index=False)

# Display summary
print("\nFORECASTING DATASET SUMMARY")
print("=" * 50)

print("Original cleaned records:", before)
print("Records removed due to unavailable history:", removed)
print("Final forecasting records:", len(df))

print("\nRoutes:")
print(sorted(df["bus_route"].unique()))

print("\nFeatures:")
print(df.columns.tolist())

print("\nDate range:")
print("Start:", df["timestamp"].min())
print("End:", df["timestamp"].max())

print("\nOutput saved to:", OUTPUT_FILE)

print("\nDataset preparation completed.")
