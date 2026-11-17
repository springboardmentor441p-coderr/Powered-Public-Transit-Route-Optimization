
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


INPUT_FILE = "data/demand_forecasting_features.csv"

VALIDATION_FILE = "data/model_validation_results_v2.csv"
PREDICTIONS_FILE = "data/demand_forecasting_predictions_v2.csv"
COMPARISON_FILE = "data/model_comparison_results_v2.csv"
ROUTE_RESULTS_FILE = "data/model_performance_by_route_v2.csv"

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
RANDOM_STATE = 42


def calculate_metrics(actual, predicted):

    mae = mean_absolute_error(actual, predicted)

    rmse = mean_squared_error(actual, predicted) ** 0.5

    total_actual = actual.sum()

    wape = (
        abs(actual - predicted).sum() / total_actual * 100
        if total_actual != 0 else 0
    )

    r2 = r2_score(actual, predicted)

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "wape_percent": round(wape, 2),
        "r2": round(r2, 4)
    }


def create_preprocessor():

    return ColumnTransformer(
        transformers=[
            (
                "route",
                OneHotEncoder(handle_unknown="ignore"),
                ["bus_route"]
            )
        ],
        remainder="passthrough"
    )


def create_models():

    return {
        "Random Forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            random_state=RANDOM_STATE,
            n_jobs=-1
        ),

        "Extra Trees": ExtraTreesRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            random_state=RANDOM_STATE,
            n_jobs=-1
        )
    }


print("PASSENGER-DEMAND MODEL TRAINING AND EVALUATION")
print("=" * 65)


# 1. Load dataset

df = pd.read_csv(INPUT_FILE)

df["timestamp"] = pd.to_datetime(df["timestamp"])

df = df.sort_values(
    ["timestamp", "bus_route"]
).reset_index(drop=True)


# 2. Chronological 70/15/15 split

timestamps = sorted(df["timestamp"].unique())

total_timestamps = len(timestamps)

train_end = int(total_timestamps * 0.70)

validation_end = int(total_timestamps * 0.85)

train_end_timestamp = timestamps[train_end]

validation_end_timestamp = timestamps[validation_end]


train = df[
    df["timestamp"] < train_end_timestamp
].copy()

validation = df[
    (df["timestamp"] >= train_end_timestamp) &
    (df["timestamp"] < validation_end_timestamp)
].copy()

test = df[
    df["timestamp"] >= validation_end_timestamp
].copy()


print("\nDATA SPLIT")
print("-" * 65)

for name, section in [
    ("Training", train),
    ("Validation", validation),
    ("Testing", test)
]:

    print(f"{name} records:", len(section))

    print(
        f"{name} dates:",
        section["timestamp"].min(),
        "to",
        section["timestamp"].max()
    )

print("\nUnique timestamps:", total_timestamps)


# 3. Prepare training and validation data

X_train = train[FEATURES]

y_train = train[TARGET]

X_validation = validation[FEATURES]

y_validation = validation[TARGET]


# 4. Train and compare candidate models

validation_results = []

trained_models = {}

for model_name, model in create_models().items():

    print(f"\nTraining {model_name}...")

    pipeline = Pipeline([
        ("preprocessor", create_preprocessor()),
        ("model", model)
    ])

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_validation)

    predictions = pd.Series(
        predictions,
        index=validation.index
    )

    metrics = calculate_metrics(
        y_validation,
        predictions
    )

    validation_results.append({
        "model": model_name,
        **metrics
    })

    trained_models[model_name] = model


# 5. Save validation comparison

validation_df = pd.DataFrame(validation_results)

validation_df = validation_df.sort_values(
    "mae"
).reset_index(drop=True)

validation_df.to_csv(
    VALIDATION_FILE,
    index=False
)

print("\nVALIDATION RESULTS")
print("-" * 65)

print(validation_df.to_string(index=False))


# 6. Select the best model

best_model_name = validation_df.loc[
    validation_df["mae"].idxmin(),
    "model"
]

print("\nSelected model:", best_model_name)

print("Selection criterion: Lowest validation MAE")


# 7. Combine training and validation data

combined_train = pd.concat(
    [train, validation],
    ignore_index=True
)

X_combined = combined_train[FEATURES]

y_combined = combined_train[TARGET]


print("\nRETRAINING SELECTED MODEL")
print("-" * 65)

print("Selected model:", best_model_name)

print("Combined training records:", len(combined_train))


# 8. Retrain selected model on combined data

final_model = Pipeline([
    ("preprocessor", create_preprocessor()),
    ("model", trained_models[best_model_name])
])

final_model.fit(
    X_combined,
    y_combined
)


# 9. Evaluate on untouched test data

X_test = test[FEATURES]

y_test = test[TARGET]

test_predictions = final_model.predict(X_test)

test_predictions = pd.Series(
    test_predictions,
    index=test.index
)

baseline_predictions = test["demand_previous_week"]

model_metrics = calculate_metrics(
    y_test,
    test_predictions
)

baseline_metrics = calculate_metrics(
    y_test,
    baseline_predictions
)


# 10. Overall test comparison

comparison_df = pd.DataFrame([

    {
        "model": best_model_name,
        **model_metrics
    },

    {
        "model": "Previous Week Baseline",
        **baseline_metrics
    }

])

comparison_df.to_csv(
    COMPARISON_FILE,
    index=False
)

print("\nFINAL TEST RESULTS")
print("-" * 65)

print(comparison_df.to_string(index=False))


# 11. Save test predictions

prediction_df = test[
    ["timestamp", "bus_route", TARGET]
].copy()

prediction_df = prediction_df.rename(
    columns={
        TARGET: "actual_passengers"
    }
)

prediction_df["selected_model"] = best_model_name

prediction_df["predicted_passengers"] = test_predictions

prediction_df["baseline_predictions"] = baseline_predictions

prediction_df.to_csv(
    PREDICTIONS_FILE,
    index=False
)


# 12. Route-wise test evaluation

route_results = []

for route, group in prediction_df.groupby("bus_route"):

    actual = group["actual_passengers"]

    predicted = group["predicted_passengers"]

    baseline = group["baseline_predictions"]

    model_route_metrics = calculate_metrics(
        actual,
        predicted
    )

    baseline_route_metrics = calculate_metrics(
        actual,
        baseline
    )

    route_results.append({

        "bus_route": route,

        "test_records": len(group),

        "selected_model": best_model_name,

        "model_mae": model_route_metrics["mae"],

        "model_rmse": model_route_metrics["rmse"],

        "model_wape_percent": model_route_metrics["wape_percent"],

        "model_r2": model_route_metrics["r2"],

        "baseline_mae": baseline_route_metrics["mae"],

        "baseline_rmse": baseline_route_metrics["rmse"],

        "baseline_wape_percent": baseline_route_metrics["wape_percent"]

    })


route_df = pd.DataFrame(route_results)

route_df = route_df.sort_values(
    "model_mae"
).reset_index(drop=True)


route_df.to_csv(
    ROUTE_RESULTS_FILE,
    index=False
)


print("\nROUTE-WISE TEST PERFORMANCE")
print("-" * 65)

print(route_df.to_string(index=False))


# 13. Output summary

print("\nOUTPUT FILES")
print("-" * 65)

print("Validation results:", VALIDATION_FILE)

print("Test predictions:", PREDICTIONS_FILE)

print("Model comparison:", COMPARISON_FILE)

print("Route-wise performance:", ROUTE_RESULTS_FILE)

print("\nMODEL TRAINING AND EVALUATION COMPLETED.")
