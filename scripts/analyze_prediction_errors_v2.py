
import pandas as pd
import numpy as np

INPUT_FILE = "data/demand_forecasting_predictions_v2.csv"

OVERALL_OUTPUT = "data/prediction_error_summary_v2.csv"
ROUTE_OUTPUT = "data/prediction_errors_by_route_v2.csv"
LARGEST_ERRORS_OUTPUT = "data/largest_prediction_errors_v2.csv"
HOURLY_OUTPUT = "data/prediction_errors_by_hour_v2.csv"

# Load model predictions
df = pd.read_csv(INPUT_FILE)

# Calculate prediction errors
df["model_error"] = (
    df["predicted_passengers"] - df["actual_passengers"]
)

df["absolute_error"] = df["model_error"].abs()

df["baseline_error"] = (
    df["baseline_predictions"] - df["actual_passengers"]
)

df["baseline_absolute_error"] = df["baseline_error"].abs()

# 1. Overall prediction error summary
overall = pd.DataFrame([{
    "records": len(df),
    "mae": df["absolute_error"].mean(),
    "rmse": np.sqrt((df["model_error"] ** 2).mean()),
    "mean_error": df["model_error"].mean(),
    "overpredictions": (df["model_error"] > 0).sum(),
    "underpredictions": (df["model_error"] < 0).sum(),
    "exact_predictions": (df["model_error"] == 0).sum(),
    "baseline_mae": df["baseline_absolute_error"].mean()
}])

overall.to_csv(OVERALL_OUTPUT, index=False)

# 2. Route-wise prediction errors
route_summary = (
    df.groupby("bus_route")
    .agg(
        test_records=("actual_passengers", "count"),
        model_mae=("absolute_error", "mean"),
        model_rmse=("model_error",
                    lambda x: np.sqrt((x ** 2).mean())),
        mean_error=("model_error", "mean"),
        baseline_mae=("baseline_absolute_error", "mean")
    )
    .reset_index()
)

route_summary["mae_improvement_percent"] = (
    (route_summary["baseline_mae"] - route_summary["model_mae"])
    / route_summary["baseline_mae"] * 100
)

route_summary = route_summary.sort_values(
    "model_mae", ascending=False
)

route_summary.to_csv(ROUTE_OUTPUT, index=False)

# 3. Largest individual prediction errors
largest_errors = df.nlargest(
    50, "absolute_error"
).copy()

largest_errors.to_csv(
    LARGEST_ERRORS_OUTPUT, index=False
)

# 4. Prediction errors by hour of day
df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

hourly_summary = (
    df.groupby("hour")
    .agg(
        test_records=("actual_passengers", "count"),
        mean_absolute_error=("absolute_error", "mean"),
        mean_actual_passengers=("actual_passengers", "mean")
    )
    .reset_index()
)

hourly_summary.to_csv(HOURLY_OUTPUT, index=False)

# Display results
print("\nOVERALL PREDICTION ERROR SUMMARY")
print(overall.round(2).to_string(index=False))

print("\nROUTE-WISE PREDICTION ERRORS")
print(route_summary.round(2).to_string(index=False))

print("\nTOP 10 LARGEST PREDICTION ERRORS")
print(
    largest_errors[
        ["timestamp", "bus_route", "actual_passengers",
         "predicted_passengers", "model_error", "absolute_error"]
    ].head(10).round(2).to_string(index=False)
)

print("\nPREDICTION ERRORS BY HOUR")
print(hourly_summary.round(2).to_string(index=False))

print("\nAnalysis completed successfully.")
print("Generated files:")
print(OVERALL_OUTPUT)
print(ROUTE_OUTPUT)
print(LARGEST_ERRORS_OUTPUT)
print(HOURLY_OUTPUT)
