# AI_RouteRanker - Feature Engineering Architecture & Catalog Report

**Milestone 4: Exploratory Data Analysis & Feature Engineering**  
*Output Dataset:* `data/processed/features/model_ready_features.parquet`  
*Record Count:* **1,124,170 records** across 188 routes (2001-01-01 to 2026-08-31)  
*Total Engineered Features:* **43 columns** (1 target, 42 features & keys)  
*Compression / Storage:* Parquet (ZSTD Compressed, ~18 MB)  

---

## 1. Feature Engineering Architecture

The feature engineering pipeline is designed for high-throughput, leakage-free time-series modeling. It transforms raw boardings and GTFS schedule feeds into 4 distinct feature families:

```
[Clean Ridership & GTFS Sources]
            │
            ├──> 1. Temporal Feature Extractor   ──> Calendar, daytype, cyclical indicators
            ├──> 2. Route Historical Extractor  ──> Strictly causal expanding corridor statistics
            ├──> 3. GTFS Supply Extractor       ──> Matched trip counts, service spans, stop visits
            └──> 4. Demand / Lag Extractor       ──> Shifted lags, rolling windows, capacity ratios
                        │
                        ▼
    [Consolidated model_ready_features.parquet (1,124,170 rows x 43 cols)]
```

---

## 2. Feature Data Dictionary & Schema

| # | Feature Name | Data Type | Nullable | Category | Description & Mathematical Formula | Leakage Safeguard |
| :-: | :--- | :---: | :---: | :--- | :--- | :--- |
| 1 | `route` | `VARCHAR` | NO | Identifier | CTA route identifier (e.g. `'1'`, `'79'`, `'X4'`). | String preserved. |
| 2 | `date` | `DATE` | NO | Identifier | Service date (2001-01-01 to 2026-08-31). | Chronological sort key. |
| 3 | `daytype` | `VARCHAR` | NO | Temporal | CTA service classification (`'W'`, `'A'`, `'U'`). | Source preserved. |
| 4 | `target_rides` | `BIGINT` | NO | **TARGET** | Realized daily unlinked passenger boardings. | **Model prediction target.** |
| 5 | `year` | `BIGINT` | NO | Temporal | Calendar year (2001 - 2026). | Macro era signal. |
| 6 | `month` | `BIGINT` | NO | Temporal | Calendar month (1 - 12). | Seasonality signal. |
| 7 | `quarter` | `BIGINT` | NO | Temporal | Calendar quarter (1 - 4). | Quarterly trends. |
| 8 | `day` | `BIGINT` | NO | Temporal | Day of month (1 - 31). | Payday / billing cycles. |
| 9 | `day_of_week` | `VARCHAR` | NO | Temporal | Day name (`'Monday'` to `'Sunday'`). | Categorical day signal. |
| 10 | `day_of_week_int` | `BIGINT` | NO | Temporal | Day of week integer (0 = Sunday ... 6 = Saturday). | Numeric day cycle. |
| 11 | `day_of_year` | `BIGINT` | NO | Temporal | Day ordinal in year (1 - 366). | Annual cycle position. |
| 12 | `week_of_year` | `BIGINT` | NO | Temporal | ISO week of year (1 - 53). | Weekly macro cycle. |
| 13 | `is_weekend` | `BOOLEAN` | NO | Temporal | True if Saturday, Sunday, or Holiday `U`. | Weekend schedule dummy. |
| 14 | `is_month_start` | `BOOLEAN` | NO | Temporal | True if `day == 1`. | Monthly renewal spike. |
| 15 | `is_month_end` | `BOOLEAN` | NO | Temporal | True if last calendar day of month. | Monthly close. |
| 16 | `historical_mean_rides` | `DOUBLE` | YES | Route | $\text{Mean}(rides)$ strictly prior to date $t$. | `ROWS UNBOUNDED PRECEDING TO 1 PRECEDING`. |
| 17 | `historical_std_rides` | `DOUBLE` | YES | Route | $\text{Std}(rides)$ strictly prior to date $t$. | `ROWS UNBOUNDED PRECEDING TO 1 PRECEDING`. |
| 18 | `historical_max_rides` | `BIGINT` | YES | Route | $\text{Max}(rides)$ strictly prior to date $t$. | `ROWS UNBOUNDED PRECEDING TO 1 PRECEDING`. |
| 19 | `historical_min_rides` | `BIGINT` | YES | Route | $\text{Min}(rides)$ strictly prior to date $t$. | `ROWS UNBOUNDED PRECEDING TO 1 PRECEDING`. |
| 20 | `route_observation_count`| `BIGINT` | YES | Route | Cumulative active days prior to date $t$. | Route maturity index. |
| 21 | `rides_lag_1` | `BIGINT` | YES | Demand/Lag | Passenger rides on date $t-1$. | Strictly prior observation. |
| 22 | `rides_lag_7` | `BIGINT` | YES | Demand/Lag | Passenger rides on date $t-7$. | 1-week seasonal lag. |
| 23 | `rides_lag_14` | `BIGINT` | YES | Demand/Lag | Passenger rides on date $t-14$. | 2-week seasonal lag. |
| 24 | `rides_lag_28` | `BIGINT` | YES | Demand/Lag | Passenger rides on date $t-28$. | 4-week seasonal lag. |
| 25 | `rolling_mean_7` | `DOUBLE` | YES | Rolling | Mean rides across prior 7 observations. | Shifted window ($t-7$ to $t-1$). |
| 26 | `rolling_std_7` | `DOUBLE` | YES | Rolling | Std rides across prior 7 observations. | Shifted window ($t-7$ to $t-1$). |
| 27 | `rolling_mean_14` | `DOUBLE` | YES | Rolling | Mean rides across prior 14 observations. | Shifted window ($t-14$ to $t-1$). |
| 28 | `rolling_std_14` | `DOUBLE` | YES | Rolling | Std rides across prior 14 observations. | Shifted window ($t-14$ to $t-1$). |
| 29 | `rolling_mean_28` | `DOUBLE` | YES | Rolling | Mean rides across prior 28 observations. | Shifted window ($t-28$ to $t-1$). |
| 30 | `rolling_std_28` | `DOUBLE` | YES | Rolling | Std rides across prior 28 observations. | Shifted window ($t-28$ to $t-1$). |
| 31 | `ridership_daytype_average`| `DOUBLE` | YES | Route/Daytype | Expanding average for same route & daytype prior to $t$.| Daytype historical baseline. |
| 32 | `route_relative_demand`| `DOUBLE` | YES | Interaction | $\text{rides\_lag\_1} / \text{expanding\_historical\_mean}$. | Surge index (>1.0 = above baseline). |
| 33 | `snapshot_id` | `VARCHAR` | YES | GTFS Supply | Matched GTFS snapshot archive ID. | NULL outside coverage. |
| 34 | `scheduled_trips_count` | `BIGINT` | YES | GTFS Supply | Active scheduled trips on date $t$. | Evaluated via calendar rules. |
| 35 | `scheduled_stop_visits`| `BIGINT` | YES | GTFS Supply | Active scheduled stop calls across trips on date $t$. | Network intensity. |
| 36 | `service_span_seconds` | `BIGINT` | YES | GTFS Supply | Daily duration ($t_{\text{last}} - t_{\text{first}}$) in seconds. | Operating window. |
| 37 | `service_span_hours` | `DOUBLE` | YES | GTFS Supply | Daily duration in hours. | Hourly operating span. |
| 38 | `first_departure_seconds`| `BIGINT` | YES | GTFS Supply | Earliest departure in cumulative seconds past midnight.| Multi-hour normalized. |
| 39 | `last_departure_seconds` | `BIGINT` | YES | GTFS Supply | Latest departure in cumulative seconds past midnight. | Handles times $\ge 24:00:00$. |
| 40 | `service_active` | `BOOLEAN` | YES | GTFS Supply | True if scheduled trips > 0 on date $t$. | Active schedule status. |
| 41 | `schedule_coverage_status`| `VARCHAR` | NO | Audit | Matching status (`'matched'`, `'no_gtfs_coverage'`, etc.).| Traceability flag. |
| 42 | `rides_per_scheduled_trip`| `DOUBLE` | YES | Interaction | $\text{target\_rides} / \text{scheduled\_trips\_count}$. | NULL if no schedule or trips=0. |
| 43 | `scheduled_trips_per_service_hour`| `DOUBLE` | YES | Interaction | $\text{scheduled\_trips} / \text{service\_span\_hours}$. | Headway frequency density. |

---

## 3. Strict Data Leakage Prevention Proofs

1. **Window Frame Isolation**:
   All dynamic route features and rolling aggregations enforce `ROWS BETWEEN ... PRECEDING AND 1 PRECEDING`. Under this constraint, date $t$'s realized demand is physically excluded from its own predictive features.
2. **First-Observation Null Integrity**:
   On the initial observation of any route, `route_observation_count` evaluates to `0`, and `rides_lag_1`, `rolling_mean_7`, and `historical_mean_rides` strictly evaluate to `NULL`.
3. **Lag Value Parity**:
   Every non-null `rides_lag_1` value was audited against the preceding chronological row's `target_rides`. 100% of rows matched with **zero divergences**.
4. **Preservation of Untracked Supply as NULL**:
   Transit operations prior to Nov 23, 2025 lack digitized GTFS snapshots in this project. All supply features (`scheduled_trips_count`, `service_span_seconds`, etc.) evaluate strictly to `NULL`, preventing catastrophic distortion from artificial zero imputation.

---

## 4. Missing Value Strategy for Machine Learning

| Feature Group | Missing Row Count | Root Cause | Recommended ML Imputation Strategy |
| :--- | :---: | :--- | :--- |
| `rides_lag_1` | 188 rows (0.017%) | Route startup / first observed date | Backfill with `historical_mean_rides` or route median. |
| `rides_lag_7` | 1,316 rows (0.117%) | First week of route operations | Impute with `rides_lag_1` or daytype average. |
| `rolling_mean_7` | 188 rows (0.017%) | Initial observation | Fallback to `historical_mean_rides`. |
| `scheduled_trips_count` | 1,095,372 rows (97.4%) | Pre-GTFS historical period (2001-2025) | Use tree-based algorithms with native missing value handling (e.g. LightGBM, XGBoost, Random Forest with surrogate splits), or train dual models (Full History vs. GTFS Era). |
| `rides_per_scheduled_trip` | 1,095,796 rows (97.5%) | Pre-GTFS period + unmatched routes | Keep as dedicated capacity feature for GTFS-era models. |

---

## 5. Artifact Summary

All engineered feature sets are persisted and verified under `data/processed/features/`:
1. `ridership_features.parquet` (1,124,170 rows, 14 cols)
2. `route_features.parquet` (1,124,170 rows, 7 cols)
3. `service_features.parquet` (1,124,170 rows, 11 cols)
4. `demand_service_features.parquet` (1,124,170 rows, 18 cols)
5. `model_ready_features.parquet` (1,124,170 rows, 43 cols)
