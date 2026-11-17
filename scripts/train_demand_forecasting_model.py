
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

INPUT_FILE = "data/demand_forecasting_features.csv"
OUTPUT_FILE = "data/demand_forecasting_predictions.csv"

print("Starting passenger-demand model training...")

df = pd.read_csv(INPUT_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

df = df.sort_values(
    ["timestamp", "bus_route"]
).reset_index(drop=True)

feature_columns = [
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

target_column = "total_passengers"

# Split by unique timestamps, keeping all routes
# from the same hour in the same dataset.
unique_timestamps = (
    df["timestamp"].drop_duplicates().sort_values()
)

split_index = int(len(unique_timestamps) * 0.80)
split_timestamp = unique_timestamps.iloc[split_index]

train_df = df[df["timestamp"] < split_timestamp].copy()
test_df = df[df["timestamp"] >= split_timestamp].copy()

X_train = train_df[feature_columns]
X_test = test_df[feature_columns]

y_train = train_df[target_column]
y_test = test_df[target_column]

print("\nDATA SPLIT")
print("=" * 50)

print("Training records:", len(X_train))
print("Testing records:", len(X_test))

print("Training period:")
print(train_df["timestamp"].min(), "to",
      train_df["timestamp"].max())

print("Testing period:")
print(test_df["timestamp"].min(), "to",
      test_df["timestamp"].max())

# Verify that no timestamp occurs in both sets
overlap = set(train_df["timestamp"]) & set(test_df["timestamp"])

print("Shared timestamps:", len(overlap))

# Encode bus route names
preprocessor = ColumnTransformer(
    transformers=[
        (
            "route_encoder",
            OneHotEncoder(handle_unknown="ignore"),
            ["bus_route"]
        )
    ],
    remainder="passthrough"
)

# Build Random Forest pipeline
model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "regressor",
            RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
        )
    ]
)

# Train
print("\nTraining Random Forest model...")
model.fit(X_train, y_train)

# Predict
predictions = model.predict(X_test)

# Evaluate
mae = mean_absolute_error(y_test, predictions)
rmse = mean_squared_error(y_test, predictions) ** 0.5
r2 = r2_score(y_test, predictions)

# Previous-week baseline
baseline_predictions = X_test["demand_previous_week"]

baseline_mae = mean_absolute_error(
    y_test,
    baseline_predictions
)

baseline_rmse = mean_squared_error(
    y_test,
    baseline_predictions
) ** 0.5

print("\nMODEL EVALUATION")
print("=" * 50)

print("Random Forest:")
print(f"MAE:  {mae:.2f}")
print(f"RMSE: {rmse:.2f}")
print(f"R2:   {r2:.4f}")

print("\nPrevious-week baseline:")
print(f"MAE:  {baseline_mae:.2f}")
print(f"RMSE: {baseline_rmse:.2f}")

print("\nMODEL COMPARISON")
print("=" * 50)

mae_improvement = (
    (baseline_mae - mae) / baseline_mae
) * 100

print(f"MAE improvement: {mae_improvement:.2f}%")

if mae < baseline_mae and rmse < baseline_rmse:
    print("Random Forest outperforms the baseline on both metrics.")
else:
    print("Random Forest does not outperform the baseline on both metrics.")

# Save predictions
results = test_df[
    ["timestamp", "bus_route"]
].copy()

results["actual_passengers"] = y_test.values
results["predicted_passengers"] = predictions
results["baseline_predictions"] = baseline_predictions.values

results.to_csv(OUTPUT_FILE, index=False)

print("\nPredictions saved to:", OUTPUT_FILE)

print("\nModel training and evaluation completed.")
