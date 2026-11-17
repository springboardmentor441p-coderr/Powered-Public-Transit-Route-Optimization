
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

INPUT_FILE = "data/demand_forecasting_features.csv"
OUTPUT_FILE = "data/extra_trees_performance_by_route.csv"

FEATURES = [
    "bus_route",
    "hour",
    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend",
    "demand_previous_hour",
    "demand_previous_day",
    "demand_previous_week"
]

TARGET = "total_passengers"

print("Evaluating Extra Trees performance by bus route...")

df = pd.read_csv(INPUT_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

df = df.sort_values(
    ["timestamp", "bus_route"]
).reset_index(drop=True)

# Same chronological split as the previous experiments
timestamps = sorted(df["timestamp"].unique())
split_index = int(len(timestamps) * 0.8)
split_timestamp = timestamps[split_index]

train = df[df["timestamp"] < split_timestamp]
test = df[df["timestamp"] >= split_timestamp]

X_train = train[FEATURES]
X_test = test[FEATURES]

y_train = train[TARGET]
y_test = test[TARGET]

preprocessor = ColumnTransformer(
    transformers=[
        ("route", OneHotEncoder(handle_unknown="ignore"), ["bus_route"])
    ],
    remainder="passthrough"
)

pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("model", ExtraTreesRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    ))
])

print("\nTraining Extra Trees model...")
pipeline.fit(X_train, y_train)

predictions = pipeline.predict(X_test)

results = []

for route in sorted(test["bus_route"].unique()):

    mask = test["bus_route"].values == route

    actual = y_test.iloc[mask]
    predicted = predictions[mask]
    baseline = test.loc[mask, "demand_previous_week"]

    model_mae = mean_absolute_error(actual, predicted)
    model_rmse = mean_squared_error(actual, predicted) ** 0.5
    model_r2 = r2_score(actual, predicted)

    baseline_mae = mean_absolute_error(actual, baseline)

    improvement = (
        (baseline_mae - model_mae) / baseline_mae * 100
        if baseline_mae != 0 else 0
    )

    results.append({
        "bus_route": route,
        "test_records": len(actual),
        "extra_trees_mae": round(model_mae, 2),
        "extra_trees_rmse": round(model_rmse, 2),
        "extra_trees_r2": round(model_r2, 4),
        "baseline_mae": round(baseline_mae, 2),
        "mae_improvement_percent": round(improvement, 2)
    })

result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    "extra_trees_mae"
).reset_index(drop=True)

print("\nEXTRA TREES ROUTE-WISE PERFORMANCE")
print("=" * 90)
print(result_df.to_string(index=False))

result_df.to_csv(OUTPUT_FILE, index=False)

print("\nResults saved to:")
print(OUTPUT_FILE)

print("\nRoute-wise evaluation completed.")
