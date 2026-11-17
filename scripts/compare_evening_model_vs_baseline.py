
import pandas as pd

INPUT_FILE = "data/demand_forecasting_predictions_v2.csv"
OUTPUT_FILE = "data/evening_model_vs_baseline.csv"

df = pd.read_csv(INPUT_FILE)

df["timestamp"] = pd.to_datetime(df["timestamp"])
df["hour"] = df["timestamp"].dt.hour

# Calculate absolute errors for both prediction methods.
df["model_error"] = (
    df["actual_passengers"] - df["predicted_passengers"]
).abs()

df["baseline_error"] = (
    df["actual_passengers"] - df["baseline_predictions"]
).abs()

# Select evening peak hours: 4 PM, 5 PM and 6 PM.
evening = df[df["hour"].isin([16, 17, 18])].copy()

# Compare both methods for every route and hour.
results = (
    evening.groupby(["bus_route", "hour"])
    .agg(
        records=("actual_passengers", "count"),
        model_MAE=("model_error", "mean"),
        baseline_MAE=("baseline_error", "mean")
    )
    .reset_index()
)

# Positive improvement means Extra Trees has lower MAE.
results["improvement_percent"] = (
    (results["baseline_MAE"] - results["model_MAE"])
    / results["baseline_MAE"] * 100
)

results = results.round(2)

results.to_csv(OUTPUT_FILE, index=False)

print("EVENING MODEL VS BASELINE COMPARISON")
print("-----------------------------------")
print(results.to_string(index=False))

print("\nOVERALL EVENING COMPARISON")

overall = evening[["model_error", "baseline_error"]].mean()

print("Extra Trees MAE:", round(overall["model_error"], 2))
print("Baseline MAE:", round(overall["baseline_error"], 2))

improvement = (
    (overall["baseline_error"] - overall["model_error"])
    / overall["baseline_error"] * 100
)

print("MAE improvement:", round(improvement, 2), "%")

print("\nTotal evening records:", len(evening))
print("Results saved to:", OUTPUT_FILE)
