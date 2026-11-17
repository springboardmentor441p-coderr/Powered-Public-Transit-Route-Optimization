# Powered Public Transit Route Optimization

An AI-based public transportation analysis project focused on understanding passenger demand, evaluating bus travel speeds, identifying potential bottlenecks, and developing predictive insights for New York City (NYC) bus routes.

## 1. Project Overview

Public transportation systems experience variations in passenger demand and road travel conditions throughout the day. Understanding these patterns can help identify areas where service planning and resource allocation may be improved.

This project focuses on NYC bus transportation by combining passenger ridership analysis, bus-speed analysis, data quality checks, and machine learning-based demand forecasting.

The project aims to build a data-driven foundation for identifying demand patterns, examining potential slow-moving bus segments, and supporting future route optimization decisions.

### Current Project Scope

- City: New York City, USA
- Transport mode: Bus
- Analysis focus: Passenger demand and bus travel speed
- Predictive focus: Hourly passenger-demand forecasting
- Current stage: Data analysis, forecasting, and model evaluation

## 2. Project Objectives

- Analyze hourly passenger demand across NYC bus routes.
- Identify peak travel hours and demand variations.
- Examine bus travel-speed patterns across boroughs and routes.
- Identify potentially slow-moving bus segments.
- Investigate data quality issues and unusual ridership observations.
- Develop machine learning models to forecast hourly passenger demand.
- Compare forecasting performance against a historical baseline.
- Establish a foundation for future route optimization and service-planning recommendations.

## 3. Data Sources

### 3.1 MTA Bus Hourly Ridership

**Source:** NYC Open Data – MTA Bus Hourly Ridership Beginning 2025

Dataset: [MTA Bus Hourly Ridership Beginning 2025](https://data.ny.gov/)

This dataset provides hourly passenger ridership information for NYC bus routes.

Fields used in the project include:

- Timestamp
- Bus route
- Total passengers

The ridership field is used as provided by the dataset. Transfer counts are not added separately.

### 3.2 MTA Bus Speeds

**Source:** NYC Open Data – MTA Bus Speeds

The bus-speed dataset provides information such as:

- Timestamp
- Route ID
- Borough
- Average travel time
- Average road speed
- Bus trip count

This dataset is used to examine travel-speed patterns and identify potentially slow-moving segments.

The raw bus-speed export is large and is excluded from Git version control.

### 3.3 MTA Developer Resources

**Source:** [MTA Developer Resources](https://www.mta.info/developers)

MTA developer resources and GTFS feeds are relevant for future route and service information integration.

## 4. Passenger Demand Analysis

Passenger ridership data was processed to understand demand patterns across bus routes and time periods.

The analysis includes:

- Hourly passenger-demand patterns
- Monthly demand patterns
- Weekday demand patterns
- Weekday versus weekend comparisons
- Route-wise demand comparisons
- Identification of peak demand hours and routes

### Key Findings

The earlier ridership analysis identified the following high-demand routes based on cumulative passenger counts:

| Bus Route | Cumulative Passengers |
|---|---:|
| M15+ | 12,891,630 |
| Q25 | 9,469,397 |
| B6 | 9,377,700 |
| Q58 | 9,234,004 |
| Q44+ | 8,847,952 |

The busiest hours identified in the analysis include:

- 7 AM
- 8 AM
- 5 PM
- 4 PM
- 3 PM

These findings describe the analyzed dataset and should not be interpreted as live passenger-demand measurements.

## 5. Bus Speed Analysis

Bus-speed data was examined to understand travel-speed variations across routes and boroughs.

The analysis includes:

- Route-wise speed comparisons
- Borough-wise speed patterns
- Identification of potentially slow-moving segments
- Filtering and evaluation of reliable segment observations
- Comparison of passenger-demand and bus-speed patterns

### Dataset Inspection

The inspected bus-speed dataset contained:

- 1,250,851 records
- 304 unique bus routes
- Data ranging from January 1, 2025, to September 1, 2026
- Records across the Bronx, Brooklyn, Manhattan, Queens, Staten Island, and Other

The dataset also contained missing values and inconsistencies in the reported day-of-week field. Timestamp information was used as the more reliable reference for date-related analysis.

The bus-speed dataset contains irregular observations and should not be treated as a continuous record of every bus journey.

## 6. Potential Bottleneck Identification

Potentially slow-moving bus segments were identified using the available bus-speed observations.

The following segments were among the slowest identified in the analysis:

| Route | Segment | Average Speed |
|---|---|---:|
| M15 | 2 AV / E 50 ST → 2 AV / E 33 ST | 4.94 mph |
| Q58 | CORONA AV / JUNCTION BLVD → GRAND AV / QUEENS BLVD | 5.05 mph |
| M101 | 3 AV / E 42 ST → 3 AV / E 67 ST | 5.36 mph |
| M101 | 3 AV / E 67 ST → 3 AV / E 97 ST | 6.58 mph |
| M101 | 3 AV / E 99 ST → E 125 ST / 3 AV | 6.96 mph |

These are potential slow-speed segments based on the available observations. Low average speed alone does not establish the cause of a delay or prove traffic congestion.

## 7. Passenger Demand Forecasting

A machine learning-based passenger-demand forecasting experiment was developed using hourly ridership data.

The objective was to predict hourly passenger counts for selected NYC bus routes using historical demand and time-related features.

### 7.1 Data Preparation and Cleaning

The original hourly ridership training dataset contained:

- 116,928 records
- 8 bus routes
- Hourly observations from January 1, 2025, to September 1, 2026

During data-quality investigation, six dates from January 10 to January 15, 2026, were identified with complete blocks of zero-ridership observations across the selected routes.

These 1,152 records were separated for auditing as suspected reporting anomalies. They were not treated as confirmed errors or silently deleted.

After separating these records:

- Cleaned records: 115,776
- Routes: 8
- Missing values: 0
- Duplicate records: 0
- Negative passenger counts: 0

### 7.2 Feature Engineering

Historical and time-based features were created to support forecasting.

Features include:

- Bus route
- Hour
- Day of week
- Day of month
- Month
- Weekend indicator
- Previous-hour passenger count
- Previous-day passenger count
- Previous-week passenger count

After creating historical lag features, the forecasting dataset contained 113,088 records.

### 7.3 Model Training and Evaluation

Two tree-based machine learning models were compared:

1. Random Forest Regressor
2. Extra Trees Regressor

The data was divided chronologically to avoid using future observations to predict earlier observations.

| Dataset Split | Percentage |
|---|---:|
| Training | 70% |
| Validation | 15% |
| Testing | 15% |

The validation dataset was used for model selection. The final test dataset was kept separate for evaluating the selected model.

### 7.4 Model Performance

Extra Trees achieved the better validation performance and was selected for final evaluation.

Final test results:

| Metric | Extra Trees | Previous-Week Baseline |
|---|---:|---:|
| MAE | 43.12 | 66.57 |
| RMSE | 65.23 | 111.45 |
| WAPE | 8.08% | 12.47% |
| R² | 0.9771 | 0.9331 |

The Extra Trees model achieved a **35.23% reduction in MAE** compared with the previous-week baseline on the test dataset.

MAE represents the average absolute prediction error in passenger counts. RMSE gives greater weight to larger errors, while WAPE expresses the total absolute error relative to actual passenger volume.

These are retrospective test results, not evidence of live forecasting performance or actual operational improvements.

### 7.5 Route-wise Model Evaluation

The selected model was also evaluated separately across the eight bus routes.

The evaluation includes:

- Route-wise MAE
- Route-wise RMSE
- Route-wise WAPE
- Route-wise R²
- Comparison against the previous-week baseline

The results are available in:

`data/model_performance_by_route_v2.csv`

### 7.6 Evening-Hour Evaluation

Additional evaluation was performed for the evening peak period, covering 4 PM to 6 PM.

The results showed:

- Extra Trees evening MAE: 68.33 passengers
- Previous-week baseline evening MAE: 107.75 passengers
- MAE improvement: 36.58%

Extra Trees achieved lower MAE than the baseline across all 24 evaluated route-hour combinations in this period.

Evening-hour evaluation helps examine model performance during a higher-demand period, but does not establish that the model will perform equally well in live operations.

## 8. Data Quality and Anomaly Investigation

Data quality checks were performed before and during model development.

The investigation included:

- Missing-value checks
- Duplicate-record checks
- Negative passenger-count checks
- Unusual zero-ridership observations
- Cross-route anomaly investigation
- Model sensitivity evaluation

### Cross-Route Anomaly Investigation

An unusual observation was identified at:

`2026-08-16 21:00:00`

All eight selected routes had unusually low passenger counts at this timestamp, with a combined count of 11 passengers.

The observation was flagged for investigation because the reduction appeared across multiple routes simultaneously.

The original records were not automatically removed.

### Anomaly Impact Evaluation

A sensitivity evaluation compared model performance using all test records against performance after excluding the eight flagged prediction records.

| Evaluation | MAE | RMSE | WAPE |
|---|---:|---:|---:|
| All test records | 43.12 | 65.23 | 8.08% |
| Excluding flagged records | 43.03 | 65.00 | 8.06% |

The aggregate metrics changed only slightly.

This sensitivity analysis indicates that the flagged observations had limited influence on the overall test metrics. It does not establish the underlying cause of the unusual ridership values.

## 9. Visualizations

The project includes visualizations to communicate passenger-demand and bus-speed patterns.

### Passenger Demand Charts

- Average demand by hour
- Average demand by month
- Average demand by route
- Average demand by weekday

### Bus Speed and Bottleneck Charts

- Hourly speed comparison
- Route speed comparison
- Passenger demand versus speed
- Top potential bottleneck segments

The charts are stored in the `charts/` directory.

## 10. Model Diagnostics Report

A detailed model diagnostics report is available at:

`reports/model_diagnostics_report.md`

The report covers:

- Dataset and feature details
- Model training methodology
- Overall model performance
- Route-wise performance
- Prediction error analysis
- Cross-route anomaly investigation
- Sensitivity evaluation
- Evening-hour diagnostics
- Key findings and limitations

## 11. Current Project Structure

```text
Powered-Public-Transit-Route-Optimization/
│
├── charts/
│   ├── average_demand_by_hour.png
│   ├── average_demand_by_month.png
│   ├── average_demand_by_route.png
│   ├── average_demand_by_weekday.png
│   ├── hourly_speed_comparison.png
│   ├── passenger_demand_vs_speed.png
│   ├── route_speed_comparison.png
│   └── top_bottleneck_segments.png
│
├── data/
│   ├── anomaly_impact_evaluation_v2.csv
│   ├── borough_hourly_speed_findings.txt
│   ├── cross_route_anomaly_audit.csv
│   ├── evening_model_vs_baseline.csv
│   ├── evening_prediction_errors_by_route.csv
│   ├── extra_trees_performance_by_route.csv
│   ├── final_bottleneck_ranking.csv
│   ├── hourly_demand_patterns.csv
│   ├── hourly_ridership_training.csv
│   ├── largest_prediction_errors_v2.csv
│   ├── model_comparison_results.csv
│   ├── model_comparison_results_v2.csv
│   ├── model_performance_by_route.csv
│   ├── model_performance_by_route_v2.csv
│   ├── model_validation_results_v2.csv
│   ├── monthly_demand_patterns.csv
│   ├── peak_hourly_demand.txt
│   ├── peak_routes_comparison.txt
│   ├── prediction_error_summary_v2.csv
│   ├── prediction_errors_by_hour_v2.csv
│   ├── prediction_errors_by_route_v2.csv
│   ├── reliable_slow_segments.csv
│   ├── route_demand_comparison.csv
│   ├── slow_segments_analysis.csv
│   ├── suspicious_ridership_records.csv
│   ├── top_bus_routes.txt
│   ├── weekday_demand_patterns.csv
│   └── weekday_weekend_comparison.csv
│
├── reports/
│   └── model_diagnostics_report.md
│
├── scripts/
│   ├── analyze_demand_patterns.py
│   ├── analyze_evening_prediction_errors.py
│   ├── analyze_prediction_errors_v2.py
│   ├── analyze_slow_segments.py
│   ├── analyze_zero_ridership.py
│   ├── audit_cross_route_anomalies.py
│   ├── check_date_coverage.py
│   ├── check_hourly_data_overlap.py
│   ├── check_ridership_coverage.py
│   ├── check_ridership_quality.py
│   ├── check_route_coverage_comparison.py
│   ├── check_route_matches.py
│   ├── check_suspicious_dates.py
│   ├── check_trip_column.py
│   ├── clean_ridership_training_data.py
│   ├── compare_demand_models.py
│   ├── compare_demand_speed.py
│   ├── compare_evening_model_vs_baseline.py
│   ├── create_visualizations.py
│   ├── evaluate_anomaly_impact_v2.py
│   ├── evaluate_extra_trees_by_route.py
│   ├── evaluate_model_by_route.py
│   ├── filter_reliable_segments.py
│   ├── final_bottleneck_ranking.py
│   ├── inspect_bus_speeds.py
│   ├── inspect_exact_speed_dates.py
│   ├── inspect_fare_ridership.py
│   ├── inspect_peak_hours.py
│   ├── inspect_peak_routes.py
│   ├── inspect_recent_ridership.py
│   ├── inspect_ridership.py
│   ├── inspect_ridership_columns.py
│   ├── inspect_ridership_patterns.py
│   ├── inspect_speed_date_coverage.py
│   ├── investigate_zero_records.py
│   ├── prepare_demand_forecasting_data.py
│   ├── prepare_ridership_dataset.py
│   ├── test_hourly_aggregation.py
│   ├── train_and_evaluate_demand_models_v2.py
│   ├── train_demand_forecasting_model.py
│   ├── validate_cleaned_ridership.py
│   ├── validate_demand_forecasting_data.py
│   └── validate_ridership_dataset.py
│
├── .gitignore
├── LICENSE
├── README.md
└── bus_route_counts.csv
```

**Note:** Intermediate generated files, including `hourly_ridership_training_cleaned.csv`, `demand_forecasting_features.csv`, and forecasting prediction outputs, are generated locally by the scripts and are not included in the committed project structure. The large raw bus-speed export `export.csv` is also excluded from version control.

## 12. Technologies Used

- Python
- Pandas
- NumPy
- Scikit-learn
- Matplotlib
- Git
- GitHub
- CSV datasets

## 13. Running the Analysis

Clone the repository:

```bash
git clone https://github.com/springboardmentor441p-coderr/Powered-Public-Transit-Route-Optimization.git
```

Navigate into the project:

```bash
cd Powered-Public-Transit-Route-Optimization
```

Install the required Python packages:

```bash
pip install pandas numpy scikit-learn matplotlib
```

Run the passenger-demand cleaning and preparation scripts:

```bash
python scripts/clean_ridership_training_data.py
python scripts/validate_cleaned_ridership.py
python scripts/prepare_demand_forecasting_data.py
python scripts/validate_demand_forecasting_data.py
```

Run model training and evaluation:

```bash
python scripts/train_and_evaluate_demand_models_v2.py
```

The scripts expect the required input datasets to be available in the `data/` directory.

## 14. Limitations and Future Work

### Current Limitations

- The project currently focuses on selected NYC bus routes for passenger-demand forecasting.
- The ridership dataset provides hourly passenger counts, not unique passenger identities or stop-level boarding information.
- The available data does not directly provide onboard passenger loads, vehicle capacity utilization, or crowding levels.
- The bus-speed dataset contains irregular observations and cannot represent every bus journey continuously.
- Some unusual ridership observations require further investigation to establish their causes.
- Forecasting results are retrospective and have not yet been validated in a live operational environment.
- Identifying a slow-moving segment does not independently establish traffic congestion or its cause.

### Future Work

- Integrate and validate NYC GTFS route and service information.
- Develop route-level demand profiles and explainable indicators.
- Investigate route clustering and service-planning opportunities.
- Extend forecasting evaluation and test additional forecasting approaches.
- Develop explainable route-ranking and scenario-analysis methods.
- Build a backend and frontend for presenting route analysis and recommendations.
- Evaluate proposed service changes using carefully defined scenarios.

## 15. Project Goal

The long-term goal is to develop a data-driven public transportation analysis and route optimization system that can support better understanding of passenger demand, bus travel conditions, and potential service-planning improvements in New York City.

The current work establishes the data analysis and passenger-demand forecasting foundation for that system.