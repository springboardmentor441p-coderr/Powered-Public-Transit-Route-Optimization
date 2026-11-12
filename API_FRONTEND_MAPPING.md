# RouteRanker: API to Frontend Mapping Specification
*Compliance with Technical Specification v3.8 (11 November 2026)*

| Page / Feature | React Component | Backend Endpoint | HTTP Method | Data Source & Provenance | Key Fields Mapped |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **Navbar** | `Navbar.jsx` | `/api/transit/status`<br>`/api/transit/alerts` | `GET`<br>`GET` | Live CTA XML feed + GTFS Simulation | `alerts_api_active`, `total_alerts`, `live_apis` |
| **Dashboard** | `DashboardView.jsx` | `/api/forecast/system`<br>`/api/transit/alerts`<br>`/api/forecast/metrics`<br>`/api/analytics/historical-trend` | `GET`<br>`GET`<br>`GET`<br>`GET` | Official CTA Daily Totals + Random Forest Model | `predicted_total_demand`, `lower_ci_95`, `upper_ci_95`, `MAE`, `MAPE`, `alerts`, `total_rides` |
| **Live Monitoring** | `LiveMonitoringView.jsx` | `/api/transit/bus/vehicles`<br>`/api/transit/train/positions`<br>`/api/transit/alerts` | `GET`<br>`GET`<br>`GET` | Authentic GTFS Shape Vectors + Chicago Bounds | `latitude`, `longitude`, `route_id`, `line`, `heading`, `is_delayed`, `data_source` |
| **Route Planner** | `RoutePlannerView.jsx` | `/api/route/locations`<br>`/api/route/plan` | `GET`<br>`GET` | 182-node Directed Graph + Line Expansion | `total_duration_minutes`, `total_stops`, `transfers_count`, `itinerary_legs`, `waypoints` |
| **Demand Forecasting** | `ForecastingView.jsx` | `/api/forecast/system`<br>`/api/forecast/route`<br>`/api/forecast/metrics` | `GET`<br>`GET`<br>`GET` | Chronological Splits + Calibrated 2025 Val RMSE | `predicted_total_demand`, `predicted_rides`, `lower_ci_95`, `upper_ci_95`, `crowd_classification` |
| **Historical Replay** | `HistoricalReplayView.jsx` | `/api/replays`<br>`/api/replays/{id}`<br>`/api/replays/{id}/control` | `POST`<br>`GET`<br>`POST` | Held-out Test Partition (June–July 2026) | `current_virtual_date`, `latest_permitted_actual_date`, `predicted_rides`, `revealed_actual_rides`, `error` |
| **Route Clusters & Rankings** | `RouteClustersView.jsx` | `/api/route-groups`<br>`/api/rankings` | `GET`<br>`GET` | Lloyd's K-Means (k=4) + GTFS Trips Matching | `cluster_id`, `cluster_name`, `mean_weekday_rides`, `rides_per_scheduled_trip`, `rides_per_scheduled_hour` |
| **Smart Scenarios** | `RecommendationsView.jsx` | `/api/recommendations/simulate` | `GET` | GTFS Baseline Trips + 18-Hour Window | `baseline_headway_minutes`, `operating_headway_minutes`, `baseline_daily_capacity`, `boardings_per_trip` |
| **Network Analytics** | `AnalyticsView.jsx` | `/api/analytics/routes`<br>`/api/analytics/stations`<br>`/api/analytics/network` | `GET`<br>`GET`<br>`GET` | Historical Corridor Aggregations + NetworkX | `mean_daily_rides`, `max_daily_rides`, `betweenness_centrality`, `degree_centrality` |
| **About & Provenance** | `AboutView.jsx` | `/api/data/manifest` | `GET` | Verified Dataset SHA-256 Manifest | `manifest_version`, `dataset_id`, `sha256`, `coverage_start`, `coverage_end`, `agency_timezone` |

