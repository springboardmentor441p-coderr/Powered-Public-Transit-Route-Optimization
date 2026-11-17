
import pandas as pd

INPUT_FILE = "data/demand_forecasting_predictions_v2.csv"
OUTPUT_FILE = "data/evening_prediction_errors_by_route.csv"

df = pd.read_csv(INPUT_FILE)

df["timestamp"] = pd.to_datetime(df["timestamp"])
df["hour"] = df["timestamp"].dt.hour

# Calculate prediction errors.
df["absolute_error"] = (
    df["actual_passengers"] - df["predicted_passengers"]
).abs()

df["signed_error"] = (
    df["predicted_passengers"] - df["actual_passengers"]
)

# Focus on the evening peak: 4 PM, 5 PM and 6 PM.
evening = df[df["hour"].isin([16, 17, 18])].copy()

# Calculate error metrics for each route and hour.
results = (
    evening.groupby(["bus_route", "hour"])
    .agg(
        records=("actual_passengers", "count"),
        MAE=("absolute_error", "mean"),
        mean_error=("signed_error", "mean")
    )
    .reset_index()
)

results["MAE"] = results["MAE"].round(2)
results["mean_error"] = results["mean_error"].round(2)

results.to_csv(OUTPUT_FILE, index=False)

print("EVENING-HOUR PREDICTION ERROR ANALYSIS")
print("--------------------------------------")

print("\nMAE by route and hour:")
print(results.to_string(index=False))

print("\nOverall evening-hour performance:")
print(
    evening.groupby("hour")["absolute_error"]
    .mean()
    .round(2)
    .to_string()
)

print("\nTotal evening test records:", len(evening))
print("Results saved to:", OUTPUT_FILE)
