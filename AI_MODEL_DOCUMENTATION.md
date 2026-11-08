# MetroFlow AI Machine Learning Model Documentation
*Project: MetroFlow AI Platform for Metro Crowd Management & Scheduling*
*Document Reference: ML-DOC-01*

---

## 1. Machine Learning Architecture & Objective
The MetroFlow AI module predicts **passenger density percentage**, **station footfall demand**, and **crowd congestion risk tiers** across public transit networks to support proactive dispatching, platform crowd metering, and headway adjustments.

---

## 2. Models & Algorithms
The platform deploys two specialized ensemble regressors:

1. **Crowd Density Regressor (`GradientBoostingRegressor`)**:
   - **Target:** Continuous passenger density percentage (`0.0% - 100.0%`).
   - **Algorithm:** Gradient Boosting with deviance loss.
   - **Hyperparameters:** `n_estimators=80`, `max_depth=4`, `learning_rate=0.1`, `random_state=42`.
   - **Primary Use:** Detecting platform overcrowding and triggering station safety thresholds.

2. **Passenger Footfall Demand Forecaster (`RandomForestRegressor`)**:
   - **Target:** Expected passenger demand (passengers/hour).
   - **Algorithm:** Random Forest ensemble averaging 80 de-correlated decision trees.
   - **Hyperparameters:** `n_estimators=80`, `max_depth=5`, `random_state=42`.
   - **Primary Use:** Sizing rolling stock requirements and frequency adjustments.

---

## 3. Training Features & Engineering

| Feature Name | Type | Domain | Description |
|---|---|---|---|
| `hour` | Integer | `0 - 23` | Hour of the day reflecting diurnal commuting peaks |
| `day_of_week` | Integer | `0 - 6` | Day index (`0` = Monday, `6` = Sunday) |
| `is_peak` | Binary | `0` or `1` | Commuter peak window flag (`07:00-10:00` or `17:00-20:00`) |
| `stop_sequence` | Integer | `1 - 35` | Topological station position (central core vs. terminal stops) |
| `route_type` | Integer | `0 - 3` | Mode index (GTFS standard `3` for bus transit) |
| `scheduled_frequency` | Integer | `4 - 20` | Scheduled headway interval in minutes |

---

## 4. Congestion Risk Classification & Automated Actions

| Density Range | Risk Tier | Recommended Operational Action |
|---|---|---|
| **< 45.0%** | `LOW` | Off-peak lull. Energy conservation mode; maintain standard 10–15 min headway. |
| **45.0% - 69.9%** | `MODERATE` | Normal transit conditions. Maintain standard 6–8 min scheduled headway. |
| **70.0% - 84.9%** | `HIGH` | Heavy commuter inflow. Compress headway down to 3.5–4.5 min. |
| **>= 85.0%** | `CRITICAL` | Hazardous platform overcrowding. Enforce dynamic gate metering and inject relief trains immediately. |

---

## 5. Persistence & Inference Pipeline
- Model artifacts are serialized with `joblib` in [`backend/app/ml/saved_models/`](file:///C:/Users/tdsri/Powered-Public-Transit-Route-Optimization/backend/app/ml/saved_models).
- Singletons load into memory upon FastAPI startup for sub-10ms real-time inference latency.
- Accessible via REST endpoints:
  - `POST /predict/crowd`
  - `GET /predict/demand`
  - `GET /predict/recommendations`

