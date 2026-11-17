
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

PREDICTIONS_FILE = "data/demand_forecasting_predictions_v2.csv"
AUDIT_FILE = "data/cross_route_anomaly_audit.csv"
OUTPUT_FILE = "data/anomaly_impact_evaluation_v2.csv"

predictions = pd.read_csv(PREDICTIONS_FILE)
audit = pd.read_csv(AUDIT_FILE)

# Identify flagged timestamp and routes.
flagged = audit[["timestamp", "bus_route"]].drop_duplicates()

# Match timestamp formats before identifying flagged predictions.
predictions["timestamp"] = pd.to_datetime(predictions["timestamp"])
flagged["timestamp"] = pd.to_datetime(flagged["timestamp"])

# Exclude only the eight audited records in the second evaluation.
comparison = predictions.merge(
    flagged.assign(is_flagged=True),
    on=["timestamp", "bus_route"],
    how="left"
)

def calculate_metrics(data, label):
    actual = data["actual_passengers"]
    predicted = data["predicted_passengers"]

    return {
        "evaluation": label,
        "records": len(data),
        "MAE": mean_absolute_error(actual, predicted),
        "RMSE": np.sqrt(mean_squared_error(actual, predicted)),
        "WAPE_percent": (
            np.abs(actual - predicted).sum() / actual.sum() * 100
        ),
        "R2": r2_score(actual, predicted)
    }

original_results = calculate_metrics(
    comparison,
    "All test records"
)

filtered_results = calculate_metrics(
    comparison[comparison["is_flagged"].isna()],
    "Excluding flagged anomaly"
)

results = pd.DataFrame([original_results, filtered_results])

results.to_csv(OUTPUT_FILE, index=False)

print("ANOMALY IMPACT EVALUATION")
print("------------------------")
print(results.to_string(index=False))
print("\nFlagged prediction records:", comparison["is_flagged"].notna().sum())
print("Evaluation saved to:", OUTPUT_FILE)
print("Original V2 predictions modified: No")
