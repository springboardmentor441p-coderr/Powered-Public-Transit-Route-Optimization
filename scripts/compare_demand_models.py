
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

INPUT_FILE = "data/demand_forecasting_features.csv"
OUTPUT_FILE = "data/model_comparison_results.csv"

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

print("Comparing passenger-demand forecasting models...")

df = pd.read_csv(INPUT_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

df = df.sort_values(
    ["timestamp", "bus_route"]
).reset_index(drop=True)

# Chronological split using unique timestamps
timestamps = sorted(df["timestamp"].unique())
split_index = int(len(timestamps) * 0.8)
split_timestamp = timestamps[split_index]

train = df[df["timestamp"] < split_timestamp]
test = df[df["timestamp"] >= split_timestamp]

X_train = train[FEATURES]
X_test = test[FEATURES]

y_train = train[TARGET]
y_test = test[TARGET]

print("\nDATA SPLIT")
print("=" * 60)
print("Training records:", len(train))
print("Testing records:", len(test))
print("Training ends:", train["timestamp"].max())
print("Testing starts:", test["timestamp"].min())

# Shared preprocessing
preprocessor = ColumnTransformer(
    transformers=[
        ("route", OneHotEncoder(handle_unknown="ignore"), ["bus_route"])
    ],
    remainder="passthrough"
)

models = {
    "Random Forest": RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    ),
    "Extra Trees": ExtraTreesRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
}

results = []

for model_name, model in models.items():

    print(f"\nTraining {model_name}...")

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("model", model)
    ])

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = mean_squared_error(y_test, predictions) ** 0.5
    r2 = r2_score(y_test, predictions)

    results.append({
        "model": model_name,
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(r2, 4)
    })

# Previous-week baseline
baseline = test["demand_previous_week"]

baseline_mae = mean_absolute_error(y_test, baseline)
baseline_rmse = mean_squared_error(y_test, baseline) ** 0.5

results.append({
    "model": "Previous Week Baseline",
    "mae": round(baseline_mae, 2),
    "rmse": round(baseline_rmse, 2),
    "r2": None
})

result_df = pd.DataFrame(results)

print("\nMODEL COMPARISON")
print("=" * 60)
print(result_df.to_string(index=False))

result_df.to_csv(OUTPUT_FILE, index=False)

print("\nComparison report saved to:")
print(OUTPUT_FILE)

print("\nModel comparison completed.")
