# Supply-Side Anomaly Detection Model Architecture (v2)

**Project:** Chennai MTC RouteRanker  
**Scope:** 3,934 Active MTC Transit Routes  
**Status:** Architecture Specification & Implementation Plan  
**Target File:** `reports/supply_side_anomaly_model_architecture_v2.md`  

---

## 1. Executive Summary & Model Objective

The objective of this machine learning system is to design and validate an **unsupervised Supply-Side Anomaly Detection Model** using **Isolation Forest** across the 3,934 verified active Chennai MTC transit routes. 

### What This Model Is
- A systematic method to detect **atypical supply-side operational configurations** in scheduled transit service (e.g., extremely sparse stop spacing, disproportionately high or low service volume per stop, unusual headway extremes, and structural schedule profiles).
- An objective diagnostic tool providing quantitative anomaly scores and interpretable feature contribution profiles for planning review.

### What This Model Is NOT
- **Not a passenger demand, crowding, or revenue predictor:** It assesses scheduled GTFS operational characteristics only, without passenger ticketing or ridership inputs.
- **Not a defect or failure detector:** An "anomaly" in this context represents a statistically rare scheduled operational pattern (e.g., long-distance regional express shuttles, feeder loops, or high-frequency trunk corridors). Routes flagged as anomalous are **not** labeled as defective, broken, or operationally deficient without independent operational validation.
- **Not a duplicate of existing modules:**
  - **Task 06 (Route Clustering):** Groups routes into broad behavioral archetypes (e.g., K-Means/Agglomerative $k=3..5$ or DBSCAN core clusters). It does not score the degree of abnormality or isolate sparse, boundary-defining configurations.
  - **Task 07 (Explainable Route Ranking):** Computes a composite priority rank combining supply metrics and demand surrogates. It produces a linear ordering, not an outlier boundary.
  - **Task 08 (Bus Frequency Analysis):** Aggregates static policy-level headway brackets and service spans across predefined time windows. It evaluates policy compliance, not multidimensional joint distribution outliers.

---

## 2. Investigation of Underlying GTFS Data & Feature Redundancy

A rigorous inspection of `routes.txt`, `trips.txt`, `calendar.txt`, `route_cluster_assignments.csv`, and `bus_frequency_analysis.csv` was conducted to establish empirical ground truth before feature definition.

### 2.1 Empirical Finding: Weekday vs. Weekend Equivalence
- In `route_cluster_assignments.csv` across all 3,934 active routes:
  - `(weekday_trip_count == weekend_trip_count).sum() = 3,934` (100.0% identical).
  - `(weekday_headway_min == weekend_headway_min).sum() = 3,065` (100.0% of non-missing values are identical).
- **Root Cause in GTFS Source Data:**
  - In `trips.txt`, out of 47,047 total trips, **46,973 trips (99.84%)** are assigned to `service_id = 'Regular'`.
  - In `calendar.txt`, service `Regular` is defined with `monday=1, tuesday=1, wednesday=1, thursday=1, friday=1, saturday=1, sunday=1`.
  - The remaining 74 trips (0.16%) belong to `service_id = 'HSC'` which operates Monday–Saturday (`sunday=0`). These 74 trips span only 10 routes, but in the Task 06 data pipeline, daily trips were computed on the active scheduled calendar without day-of-week stratification.
- **Architectural Consequence:**
  - Treating `weekend_trip_count` and `weekend_headway_min` as independent features creates exact multicollinearity (correlation $r = 1.0$) and false dimensionality.
  - Formulas such as `weekday_trip_count - weekend_trip_count` evaluate to **0 for all 3,934 active routes**.
  - Formulas such as `abs(weekday_headway_min - weekend_headway_min)` evaluate to **0 for all 3,065 non-missing routes**.
  - Formulas adding weekday + weekend trips arbitrarily inflate trip volume by a factor of 2.

---

## 3. Verified Feature Engineering & Preprocessing Pipeline

To eliminate redundancy while capturing operational transit structure, the feature set is engineered directly from verified primary attributes.

### 3.1 Primary Numeric Features
1. `stop_count`: Total sequence of distinct stops per route (integer, min: 2, median: 23, max: 80).
2. `route_length_km`: Total one-way path distance in kilometers (float, min: 0.40 km, median: 15.43 km, max: 83.42 km).
3. `scheduled_trip_count`: Daily scheduled one-way trips per route (integer, min: 1, median: 4, max: 210).
4. `scheduled_headway_min`: Scheduled service interval in minutes for routes with multiple trips (float, min: 5.0 min, median: 65.0 min, max: 1305.0 min; 869 missing).

### 3.2 Engineered Domain Ratios
5. `trips_per_stop`: $\text{scheduled\_trip\_count} / \text{stop\_count}$.
   - Measures scheduled service intensity relative to route boarding opportunities. 
   - Avoids double-counting weekday and weekend trips.
6. `stop_spacing_km` (Route length per stop): $\text{route\_length\_km} / \text{stop\_count}$.
   - Represents average inter-stop distance. Atypical values expose express/non-stop trunk lines (high spacing) vs. dense circular local feeders (very low spacing).
7. `route_speed_proxy` (Length per trip): $\text{route\_length\_km} \times \text{scheduled\_trip\_count}$.
   - Reflects daily scheduled bus-kilometers supplied on the route.

### 3.3 Rigorous Handling of the 869 Missing Headway Routes
- **Domain Reality:** The 869 active routes with missing headway values correspond to routes operating **exactly 1 trip per day** ($N=869$), where an operational headway between consecutive trips is mathematically undefined.
- **Rule against data fabrication:** Missing headway values **must never be filled with fabricated or assumed operational headways** (e.g. assigning arbitrary 0 min or mean values without indicators).
- **Two-Part Mathematical Formulation:**
  1. `headway_missing_indicator`: A strict binary feature ($1$ if headway is undefined/missing due to single-trip operation, $0$ if multi-trip operation).
  2. `imputed_headway_min`: For tree-based matrix processing, missing values are imputed strictly using the **median of the training split** (learned inside validation folds, never leaked across test folds), with the explicit indicator preserved. Tree partitions in Isolation Forest isolate the combination of `headway_missing_indicator = 1` and imputed value without distorting multi-trip routes.

### 3.4 Skewness, Outliers, and Scaling Strategy
- **Empirical Skewness:**
  - `stop_count`: $0.46$ (moderate)
  - `route_length_km`: $0.81$ (moderate)
  - `scheduled_trip_count`: $4.14$ (highly right-skewed; 75th percentile is 10, max is 210)
  - `scheduled_headway_min`: $1.98$ (right-skewed; 75th percentile is 180 min, max is 1305 min)
  - `trips_per_stop`: $>4.5$ (heavily right-skewed)
- **Transformation & Scaling:**
  - Isolation Forest is invariant to monotonic transformations on individual features because split selection relies on uniform random sampling between feature minima and maxima.
  - However, in heavily skewed features with extreme outliers (e.g. trip count of 210 vs median 4), linear random cuts between 1 and 210 predominantly cut empty space, artificially isolating points based purely on 1D scale rather than multi-attribute structure.
  - **Preprocessing Transformation:** Apply $\log_{1p}(x) = \ln(1 + x)$ to heavily skewed continuous attributes (`scheduled_trip_count`, `scheduled_headway_min`, `trips_per_stop`, and `route_speed_proxy`).
  - **Baseline Scaling:** For distance-based and density-based comparison models (`LocalOutlierFactor`, `OneClassSVM`), apply `RobustScaler` (scaling by median and interquartile range $IQR$) to prevent extreme values from distorting Euclidean or kernel metrics.

---

## 4. Model Selection & Alternative Benchmark

### 4.1 Primary Model: Isolation Forest (`sklearn.ensemble.IsolationForest`)
- **Mathematical Foundation:** Builds an ensemble of $T$ completely randomized isolation trees (`iTrees`). Isolating an observation $x$ requires fewer recursive random hyperplanes if $x$ lies in sparse, low-density regions of the attribute space.
- **Path Length Formulation:**
  $$s(x, n) = 2^{-\frac{E(h(x))}{c(n)}}$$
  where $E(h(x))$ is the average path length across all trees, $c(n) = 2\ln(n - 1) + 0.5772156649 - \frac{2(n - 1)}{n}$ is the average path length of unsuccessful searches in a Binary Search Tree, and $n$ is the subsampling size.
- **Score Properties:**
  - As $E(h(x)) \to 0$, $s \to 1$ (high anomaly confidence).
  - When $E(h(x)) \to c(n)$, $s \to 0.5$ (typical instance).
  - When $E(h(x)) \to n - 1$, $s \to 0$ (dense cluster core).

### 4.2 Benchmark Alternative: Local Outlier Factor (`sklearn.neighbors.LocalOutlierFactor`)
- **Availability:** Fully supported in installed `scikit-learn` without external dependencies.
- **Mechanism:** Computes local reachability density ($lrd$) relative to $k$-nearest neighbors ($k=20$ by default with `novelty=True` for held-out scoring).
- **Purpose:** Compares tree-based global isolation against local density-based reachability.

---

## 5. Contamination Selection, Anomaly Ranking & Flagging

### 5.1 Contamination Strategy
- Rather than assuming an arbitrary fixed contamination rate, the architecture adopts a **dual-threshold reporting protocol**:
  1. **Continuous Anomaly Rank (Primary):** Every active route is assigned an exact continuous anomaly score $s \in [0, 1]$ and an empirical percentile rank $P \in [0, 100\%]$.
  2. **Tiered Operational Flags:**
     - **Tier 1 (Severe Supply Outlier):** Top 1.0% ($P \ge 99.0\%$, $\approx 39$ routes).
     - **Tier 2 (Moderate Supply Outlier):** Top 5.0% ($P \ge 95.0\%$, $\approx 197$ routes).
     - **Tier 3 (Nominal Supply Profile):** Bottom 95.0% ($P < 95.0\%$, typical transit operations).

### 5.2 Score Conversion & Normalization
Scikit-learn's `decision_function(X)` yields shifted scores where negative values indicate anomalies. We map this monotonically to a normalized Anomaly Score $S_{\text{norm}} \in [0, 1]$:
$$S_{\text{norm}}(x) = \frac{\max(\text{score}) - \text{score}(x)}{\max(\text{score}) - \min(\text{score})}$$
ensuring $1.0$ represents the most isolated route and $0.0$ represents the most standard route.

---

## 6. Interpretable Post-Hoc Explanation Mechanism

### 6.1 Package Verification Reality
- Verification check executed in the active workspace confirmed:
  - `sklearn`: **AVAILABLE**
  - `scipy`: **AVAILABLE**
  - `numpy`: **AVAILABLE**
  - `pandas`: **AVAILABLE**
  - `shap`: **NOT AVAILABLE**
  - `lime`: **NOT AVAILABLE**
- **Design Rule:** The explanation architecture **must not assume or require SHAP or LIME**.

### 6.2 Interpretable Deviation Profiling (Counterfactual Local Profiling)
To explain *why* an anomaly is isolated without black-box add-ons:
1. **Empirical Robust Quantile Bounds:** For every feature $j$, compute the active population median $Q_2(j)$ and Interquartile Range $IQR(j) = Q_3(j) - Q_1(j)$.
2. **Robust Relative Discrepancy:**
   $$R_j(x) = \frac{x_j - Q_2(j)}{IQR(j)}$$
   This avoids the distorting effects of mean/standard deviation in heavily skewed distributions.
3. **Primary Anomaly Drivers:** For each flagged route, identify the top two features exhibiting the highest absolute robust discrepancy $|R_j(x)|$.
4. **Structured Explanation Syntax:** Generate deterministic, audit-ready operational descriptions, e.g.:
   - `"High service intensity: trips_per_stop is 8.4x IQR above median (4.2 trips/stop vs median 0.17); scheduled_trip_count is 12.1x IQR above median (180 trips vs median 4)."`
   - `"Single-trip extended express: headway_missing_indicator=1 (single daily trip); stop_spacing_km is 4.8x IQR above median (2.45 km/stop vs median 0.67 km/stop)."`

---

## 7. Rigorous Validation & Stability Framework

To prevent model hallucination and ensure stability without ground-truth labels:

### 7.1 Cross-Fold Held-Out Validation (No Data Leakage)
- Implement a **5-fold cross-validation scheme** across the 3,934 active routes.
- In each fold $k$:
  - Calculate imputation medians and scaler statistics **strictly on the 4/5 training split**.
  - Fit the Isolation Forest and alternative benchmark on the training split.
  - Transform and score the held-out 1/5 test split.
- Aggregate held-out anomaly scores across all out-of-fold predictions to verify that scoring generalizes out-of-sample.

### 7.2 Random-Seed Initialization Stability
- Run Isolation Forest across 5 distinct random seeds ($0, 24, 42, 100, 2026$).
- Evaluate stability using:
  - **Spearman Rank Correlation Coefficient ($\rho$)** on full continuous anomaly scores across all pairwise seed runs. Target: $\rho \ge 0.95$.
  - **Top-$K$ Jaccard Similarity Index:**
    $$J_K(A, B) = \frac{|Top_K(A) \cap Top_K(B)|}{|Top_K(A) \cup Top_K(B)|}$$
    for $K \in \{39, 197\}$ (1% and 5% flags). Target: $J_{197} \ge 0.85$.

### 7.3 Benchmark Method Agreement
- Fit `LocalOutlierFactor(novelty=True)` and evaluate the concordance between Isolation Forest and LOF top-5% anomaly flags.
- Report the mutual overlap count, Jaccard index, and isolate specific routes where tree-based isolation and local density disagree for diagnostic review.

### 7.4 Hyperparameter Sensitivity Audit
- Evaluate tree ensemble size $n_{\text{estimators}} \in \{100, 200, 300\}$ and subsample size $\text{max\_samples} \in \{128, 256, 512, \text{'auto'}\}$.
- Record runtime, score variance, and convergence stability.

---

## 8. Final Deliverables & Artifact Specification

The implementation will generate the following reproducible outputs:

1. **`reports/mtc_supply_side_anomaly_detection_report.md`:**
   - Full methodology, empirical parameter justification, validation metrics, seed stability tables, and benchmark agreement tables.
   - Comprehensive analysis of Top-1% and Top-5% anomalies with operational explanations.
2. **`reports/route_anomaly_scores.csv`:**
   - 3,934 rows covering all active routes with exact columns:
     - `route_id`: MTC route identifier.
     - `route_short_name`: Short route designation.
     - `canonical_route`: Canonical line name.
     - `stop_count`: Total stops.
     - `route_length_km`: Total distance.
     - `scheduled_trip_count`: Total scheduled trips.
     - `scheduled_headway_min`: Raw scheduled headway (NaN preserved where single-trip).
     - `headway_missing_indicator`: Binary missing flag.
     - `trips_per_stop`: Service intensity ratio.
     - `stop_spacing_km`: Average stop spacing in km.
     - `anomaly_score_raw`: Scikit-learn raw decision function value.
     - `anomaly_score_norm`: Normalized $[0, 1]$ anomaly score.
     - `anomaly_percentile`: Percentile rank ($0.0 - 100.0\%$).
     - `is_anomaly_top1pct`: Boolean flag ($P \ge 99\%$).
     - `is_anomaly_top5pct`: Boolean flag ($P \ge 95\%$).
     - `primary_driver`: Name of the highest robust discrepancy feature.
     - `secondary_driver`: Name of the second highest robust discrepancy feature.
     - `anomaly_explanation`: Human-readable operational explanation.
3. **Reproducible Script:** `scratch/run_supply_side_anomaly_model.py`.

---

## 9. Planned Implementation Sequence

Upon user approval, execution will proceed through these controlled steps:
1. **Phase 1: Feature Matrix Preparation**
   - Extract the 3,934 active routes from `route_cluster_assignments.csv` and `bus_frequency_analysis.csv`.
   - Compute engineered ratios and missing indicators; verify zero leakage and zero NaNs in input matrices.
2. **Phase 2: Model Training & Benchmark Execution**
   - Execute 5-fold cross-validation with `IsolationForest` and `LocalOutlierFactor`.
   - Measure 5-seed stability ($\rho$, Jaccard) and parameter sensitivity.
3. **Phase 3: Explanation & Output Generation**
   - Compute robust quantile discrepancies for all routes.
   - Synthesize operational explanation strings and compile `route_anomaly_scores.csv`.
4. **Phase 4: Synthesis & Final Reporting**
   - Compile comprehensive diagnostic report in `reports/mtc_supply_side_anomaly_detection_report.md`.
