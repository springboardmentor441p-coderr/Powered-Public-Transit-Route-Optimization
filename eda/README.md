# EDA: `eda/main.py`

All exploratory data analysis is in **one file**, `main.py`. It reads the processed **hourly**
route x hour table produced by the backend and writes its figures and summary into this folder.

| Method | Function | Output |
|---|---|---|
| Descriptive statistics (mean, quantiles, skewness, kurtosis) | `descriptive_stats` | `eda_summary.json` |
| High-traffic time windows | `peak_windows` | `eda_summary.json` |
| IQR outlier rule on daily route ridership | `iqr_outliers` | `eda_summary.json` |
| Hourly ridership curve by day type | `fig_hourly_curves` | `figures/eda_hourly_ridership_curve.png` |
| Daily trend + 7-day rolling mean + holidays | `fig_daily_trend` | `figures/eda_daily_trend.png` |
| Day-of-week box plots | `fig_dow_box` | `figures/eda_day_of_week_box.png` |
| Route density heatmap (route x hour) | `fig_route_heatmap` | `figures/eda_route_density_heatmap.png` |
| Occupancy distribution + class thresholds | `fig_occupancy_distribution` | `figures/eda_occupancy_distribution.png` |
| Performance class share by hour | `fig_class_by_hour` | `figures/eda_class_share_by_hour.png` |
| Spearman correlation of route KPIs | `fig_correlation` | `figures/eda_kpi_correlation.png` |
| Borough / route-type comparison | `fig_borough_type` | `figures/eda_borough_and_type.png` |
| Productivity top / bottom routes | `fig_productivity_rank` | `figures/eda_productivity_top_bottom.png` |
| Speed vs crowding | `fig_speed_vs_load` | `figures/eda_speed_vs_occupancy.png` |
| Stop-set (Jaccard) route overlap | `fig_overlap` | `figures/eda_route_overlap.png` |

## Run (from the project root, after `python backend/main.py train`)

```bash
python eda/main.py
```
