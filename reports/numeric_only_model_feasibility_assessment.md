# Numeric‑Only Model Feasibility Assessment

## 1. Data inspection
- Total rows in `route_cluster_assignments.csv` (original): **4611**
- Active routes (as defined by `bus_frequency_analysis.csv`): **3934**
- Inactive rows: **677**

### Missingness in the six numeric attributes (active dataset)
| Attribute | Missing values (active) | Non‑missing values |
|-----------|------------------------|--------------------|
| stop_count | 0 | 3934 |
| route_length_km | 0 | 3934 |
| weekday_trip_count | 0 | 3934 |
| weekend_trip_count | 0 | 3934 |
| weekday_headway_min | 869 | 3065 |
| weekend_headway_min | 869 | 3065 |

### Basic statistics for non‑missing values
| Attribute | Mean | Median | Std | Min | Max | Non‑missing count |
|-----------|------|--------|-----|-----|-----|-------------------|
| stop_count | 24.41 | 23.00 | 13.68 | 2.0 | 80.0 | 3934 |
| route_length_km | 17.28 | 15.43 | 11.42 | 0.4034018055043247 | 83.4235627416667 | 3934 |
| weekday_trip_count | 11.96 | 4.00 | 23.63 | 1 | 210 | 3934 |
| weekend_trip_count | 11.96 | 4.00 | 23.63 | 1 | 210 | 3934 |
| weekday_headway_min | 143.93 | 65.00 | 179.21 | 5.0 | 1305.0 | 3065 |
| weekend_headway_min | 143.93 | 65.00 | 179.21 | 5.0 | 1305.0 | 3065 |

## 2. Potential numeric‑only modelling ideas
1. **Supervised regression for missing headway imputation** – predict `weekday_headway_min` and `weekend_headway_min` from the other five attributes.
2. **Anomaly / outlier detection** (IsolationForest, OneClassSVM) on the numeric space to flag unusual supply‑side routes.
3. **Classification of route typology** – train a lightweight classifier (e.g., LogisticRegression, RandomForest) to map numeric attributes to the cluster labels produced in Task 06, enabling fast inference without recomputing embeddings.
4. **Principal Component Analysis (PCA)** for dimensionality reduction and visualisation, offering an alternative to spectral embedding that is easier to compute.

## 3. Evaluation against existing tasks
- **Task 06 (Route Clustering)** already provides unsupervised groupings; a pure numeric clustering would duplicate effort unless a different, more interpretable grouping is required.
- **Task 07 (Explainable Route Ranking)** uses a blend of demand‑side and supply‑side features; accurate headway values improve the ranking’s reliability.
- **Task 08 (Bus Frequency Analysis)** relies on headway and trip counts; imputing missing headways with model predictions would yield a fuller frequency analysis.

## 4. Recommended approach
### Supervised regression to impute missing headways
- **Input:** For each active route, the five attributes `stop_count`, `route_length_km`, `weekday_trip_count`, `weekend_trip_count`, and the *other* headway (e.g., use weekend headway to predict weekday headway and vice‑versa) when available.
- **Model candidates (installed):** `RandomForestRegressor`, `GradientBoostingRegressor`, `LinearRegression` from scikit‑learn.
- **Output:** Predicted numeric values for the missing `weekday_headway_min` and `weekend_headway_min`. The original missing‑indicator columns (`weekday_headway_missing`, `weekend_headway_missing`) are retained to allow downstream models to treat imputed values differently if needed.
- **Interpretation:** Provides a data‑driven estimate of headways where none were recorded, reducing reliance on simple median imputation and improving the fidelity of downstream frequency and ranking analyses.
- **Limitations:** Only 869 routes have missing headways; model performance is bounded by the explanatory power of the remaining attributes. Over‑fitting must be guarded against via cross‑validation. The predictions are estimates, not measurements, and should be flagged as such.
- **Evaluation method:** Use k‑fold cross‑validation on the subset of routes that have *both* headway values; report Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE). Compare against baseline median imputation to demonstrate added value.

### Why other ideas are less compelling
- **Anomaly detection** duplicates the outlier identification already performed during the graph‑typology audit; it does not create new actionable insight for the supply‑side model.
- **Classification of clusters** would merely replicate Task 06 results for fast inference; unless a real‑time service is required, the extra step adds maintenance overhead without new knowledge.
- **PCA** is useful for visualisation but does not directly produce a predictive or decision‑support output beyond what the existing spectral embedding already offers.

## 5. Decision
- **Proceed with supervised regression for headway imputation** as it addresses a concrete data gap (869 missing headway values) and enhances Tasks 07 and 08 without duplicating existing clustering work.
- If the team decides that imputing headways is not desired, then **no further numeric‑only model** is recommended; the current data and analyses are sufficient.
