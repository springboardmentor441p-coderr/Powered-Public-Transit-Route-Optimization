
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

INPUT_FILE = "data/demand_forecasting_predictions.csv"
OUTPUT_FILE = "data/model_performance_by_route.csv"

print("Evaluating forecasting performance by bus route...")

df = pd.read_csv(INPUT_FILE)

results = []

for route, group in df.groupby("bus_route"):

    actual = group["actual_passengers"]
    predicted = group["predicted_passengers"]
    baseline = group["baseline_predictions"]

    model_mae = mean_absolute_error(actual, predicted)
    model_rmse = mean_squared_error(actual, predicted) ** 0.5
    model_r2 = r2_score(actual, predicted)

    baseline_mae = mean_absolute_error(actual, baseline)
    baseline_rmse = mean_squared_error(actual, baseline) ** 0.5

    improvement = (
        (baseline_mae - model_mae) / baseline_mae * 100
        if baseline_mae != 0 else 0
    )

    results.append({
        "bus_route": route,
        "test_records": len(group),
        "random_forest_mae": round(model_mae, 2),
        "random_forest_rmse": round(model_rmse, 2),
        "random_forest_r2": round(model_r2, 4),
        "baseline_mae": round(baseline_mae, 2),
        "baseline_rmse": round(baseline_rmse, 2),
        "mae_improvement_percent": round(improvement, 2)
    })

result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    "random_forest_mae"
).reset_index(drop=True)

print("\nROUTE-WISE MODEL PERFORMANCE")
print("=" * 90)
print(result_df.to_string(index=False))

result_df.to_csv(OUTPUT_FILE, index=False)

print("\nPerformance report saved to:")
print(OUTPUT_FILE)

print("\nRoute-wise evaluation completed.")
