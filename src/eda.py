"""
Module 3: Exploratory Data Analysis (EDA)
Generates visualizations and summary statistics.
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os


def run_eda(profiles: pd.DataFrame, data: dict, output_dir: str):
    """
    Run full EDA and save plots to output_dir/plots/.
    """
    plots_dir = os.path.join(output_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)

    print("\n📊 Running Exploratory Data Analysis...")

    # ---- 1. Trip Count Distribution ----
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.histplot(profiles['trip_count'], bins=50, kde=True, color='steelblue', ax=ax)
    ax.set_title('Distribution of Trip Counts per Route', fontsize=14, fontweight='bold')
    ax.set_xlabel('Number of Trips')
    ax.set_ylabel('Frequency')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '01_trip_count_distribution.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved trip count distribution plot")

    # ---- 2. Route Length Distribution ----
    fig, ax = plt.subplots(figsize=(12, 5))
    valid_lengths = profiles[profiles['route_length_km'] > 0]['route_length_km']
    sns.histplot(valid_lengths, bins=50, kde=True, color='coral', ax=ax)
    ax.set_title('Distribution of Route Lengths (km)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Route Length (km)')
    ax.set_ylabel('Frequency')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '02_route_length_distribution.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved route length distribution plot")

    # ---- 3. Top 20 Busiest Routes ----
    top20 = profiles.nlargest(20, 'trip_count')
    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.barh(top20['route_short_name'], top20['trip_count'], color='teal')
    ax.set_xlabel('Trip Count')
    ax.set_title('Top 20 Busiest Routes by Trip Count', fontsize=14, fontweight='bold')
    ax.invert_yaxis()
    for bar, val in zip(bars, top20['trip_count']):
        ax.text(val + 0.5, bar.get_y() + bar.get_height() / 2, str(val),
                va='center', fontsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '03_top20_busiest_routes.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved top 20 busiest routes plot")

    # ---- 4. Bottom 20 Underutilized Routes ----
    bottom20 = profiles.nsmallest(20, 'trip_count')
    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.barh(bottom20['route_short_name'], bottom20['trip_count'], color='salmon')
    ax.set_xlabel('Trip Count')
    ax.set_title('Bottom 20 Underutilized Routes by Trip Count', fontsize=14, fontweight='bold')
    ax.invert_yaxis()
    for bar, val in zip(bars, bottom20['trip_count']):
        ax.text(val + 0.2, bar.get_y() + bar.get_height() / 2, str(val),
                va='center', fontsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '04_bottom20_underutilized_routes.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved bottom 20 underutilized routes plot")

    # ---- 5. Hourly Trip Distribution (System-wide) ----
    stop_times = data['stop_times'].copy()
    def parse_hour(t):
        if pd.isna(t) or t == '':
            return np.nan
        try:
            return int(str(t).split(':')[0]) % 24
        except Exception:
            return np.nan

    stop_times['hour'] = stop_times['arrival_time'].apply(parse_hour)
    hourly_trips = stop_times.dropna(subset=['hour']).groupby('hour')['trip_id'].nunique()

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(hourly_trips.index, hourly_trips.values, color='mediumpurple', edgecolor='white')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Unique Trips')
    ax.set_title('System-wide Hourly Trip Distribution', fontsize=14, fontweight='bold')
    ax.set_xticks(range(0, 24))
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '05_hourly_trip_distribution.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved hourly trip distribution plot")

    # ---- 6. Feature Correlation Heatmap ----
    numeric_cols = ['trip_count', 'unique_stops', 'avg_stops_per_trip', 'route_length_km',
                    'operating_hours', 'peak_hour_trips', 'off_peak_trips', 'peak_ratio',
                    'avg_trip_duration_min', 'stop_frequency', 'direction_count']
    corr_data = profiles[numeric_cols].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr_data, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                square=True, ax=ax, linewidths=0.5)
    ax.set_title('Feature Correlation Heatmap', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '06_correlation_heatmap.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved correlation heatmap")

    # ---- 7. Operating Hours vs Trip Count ----
    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(profiles['operating_hours'], profiles['trip_count'],
                         c=profiles['route_length_km'], cmap='viridis',
                         alpha=0.6, s=40, edgecolors='grey', linewidth=0.5)
    plt.colorbar(scatter, label='Route Length (km)')
    ax.set_xlabel('Operating Hours')
    ax.set_ylabel('Trip Count')
    ax.set_title('Operating Hours vs Trip Count (colored by Route Length)',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '07_operating_hours_vs_trips.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved operating hours vs trips scatter plot")

    # ---- 8. Peak Ratio Distribution ----
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(profiles['peak_ratio'], bins=40, kde=True, color='darkorange', ax=ax)
    ax.set_title('Peak Ratio Distribution (Peak / Avg Hourly Trips)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Peak Ratio')
    ax.set_ylabel('Frequency')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '08_peak_ratio_distribution.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved peak ratio distribution plot")

    # ---- 9. Stop Usage Heatmap (Top 30 stops) ----
    trips = data['trips']
    st_trips = stop_times.merge(trips[['trip_id', 'route_id']], on='trip_id', how='left')
    stop_usage = st_trips.groupby('stop_id')['trip_id'].count().reset_index()
    stop_usage.columns = ['stop_id', 'visit_count']
    stops = data['stops']
    stop_usage = stop_usage.merge(stops[['stop_id', 'stop_name']], on='stop_id', how='left')
    top30_stops = stop_usage.nlargest(30, 'visit_count')

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.barh(top30_stops['stop_name'].astype(str), top30_stops['visit_count'], color='forestgreen')
    ax.set_xlabel('Total Visit Count (all trips)')
    ax.set_title('Top 30 Most Visited Stops', fontsize=14, fontweight='bold')
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '09_top30_stops.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved top 30 stops plot")

    # ---- 10. Route Type Distribution ----
    fig, ax = plt.subplots(figsize=(8, 5))
    route_type_map = {0: 'Tram', 1: 'Subway', 2: 'Rail', 3: 'Bus', 4: 'Ferry',
                      5: 'Cable Car', 6: 'Gondola', 7: 'Funicular'}
    profiles['route_type_name'] = profiles['route_type'].map(route_type_map).fillna('Other')
    type_counts = profiles['route_type_name'].value_counts()
    ax.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
           colors=plt.cm.Set3.colors, startangle=140)
    ax.set_title('Route Type Distribution', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '10_route_type_distribution.png'), dpi=150)
    plt.close(fig)
    print("  ✅ Saved route type distribution plot")

    # ---- Summary Statistics ----
    print("\n📈 Summary Statistics:")
    print(f"   Total routes: {len(profiles)}")
    print(f"   Total trips: {profiles['trip_count'].sum()}")
    print(f"   Avg trips per route: {profiles['trip_count'].mean():.1f}")
    print(f"   Avg route length: {profiles['route_length_km'].mean():.1f} km")
    print(f"   Avg stops per route: {profiles['unique_stops'].mean():.1f}")
    print(f"   Routes with weekend service: {profiles['weekend_service'].sum()}")

    # Save summary
    summary = profiles.describe()
    summary.to_csv(os.path.join(output_dir, 'eda_summary_stats.csv'))
    print(f"\n✅ EDA complete! All plots saved to {plots_dir}")

    return profiles


if __name__ == "__main__":
    from data_collection import load_gtfs_data
    from feature_engineering import clean_data, build_route_profiles

    GTFS_DIR = os.path.join(os.path.dirname(__file__), '..', 'gtfs')
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'outputs')

    data = load_gtfs_data(GTFS_DIR)
    data = clean_data(data)
    profiles = build_route_profiles(data)
    run_eda(profiles, data, OUTPUT_DIR)
