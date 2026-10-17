"""
GPS Vehicle Feed Exploratory Data Analysis (EDA)
Analyzes bus pings, reporting gaps, hourly speeds, route rankings, and data quality.
"""

import os
import glob
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def find_file(possible_paths):
    for p in possible_paths:
        if os.path.exists(p):
            return p
    return None

def run_gps_eda(db_path=None, routes_path=None, output_dir='data'):
    if db_path is None:
        db_path = find_file([
            'data/raw/delhi_avl_2019/2019-07-04.db',
            'data/raw/july_19_corrected/2019-07-04.db',
            'data/raw/2019-07-04.db'
        ])
        if db_path is None:
            # Search dynamically for any .db file in data/raw
            db_candidates = glob.glob('data/raw/**/*.db', recursive=True)
            if db_candidates:
                db_path = db_candidates[0]

    if routes_path is None:
        routes_path = find_file([
            'data/raw/delhi_gtfs_2018/routes.txt',
            'data/raw/routes.txt'
        ])

    if not db_path or not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    os.makedirs(output_dir, exist_ok=True)
    print(f"Loading data from database: {db_path}...")
    conn = sqlite3.connect(db_path)
    query = """
    SELECT vehicle_id, lat, lng, speed, route_id, trip_id, CAST(timestamp AS INTEGER) as ts, date, time
    FROM vehicle_feed
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    total_raw = len(df)
    print(f"Total raw records loaded: {total_raw:,}")

    # --- 1. BAD RECORDS & DATA CLEANING ---
    df_clean = df.drop_duplicates(subset=['vehicle_id', 'ts']).copy()
    duplicates_count = total_raw - len(df_clean)
    dup_pct = (duplicates_count / total_raw) * 100

    df_clean['lat'] = pd.to_numeric(df_clean['lat'], errors='coerce')
    df_clean['lng'] = pd.to_numeric(df_clean['lng'], errors='coerce')
    df_clean['speed'] = pd.to_numeric(df_clean['speed'], errors='coerce')
    df_clean['route_id'] = pd.to_numeric(df_clean['route_id'], errors='coerce')

    zero_coords = ((df_clean['lat'] == 0) | (df_clean['lng'] == 0)).sum()
    out_of_bounds = ((df_clean['lat'] < 28.0) | (df_clean['lat'] > 29.5) | (df_clean['lng'] < 76.5) | (df_clean['lng'] > 78.0)).sum()
    neg_speeds = (df_clean['speed'] < 0).sum()
    zero_speeds = (df_clean['speed'] == 0).sum()
    zero_speed_pct = (zero_speeds / len(df_clean)) * 100
    max_speed_ms = df_clean['speed'].max()
    max_speed_kmh = max_speed_ms * 3.6

    # --- 2. BUS READINGS & GAPS ---
    bus_counts = df_clean.groupby('vehicle_id').size()
    total_buses = len(bus_counts)

    df_sorted = df_clean.sort_values(by=['vehicle_id', 'ts'])
    df_sorted['prev_ts'] = df_sorted.groupby('vehicle_id')['ts'].shift(1)
    df_sorted['gap_sec'] = df_sorted['ts'] - df_sorted['prev_ts']
    gaps = df_sorted['gap_sec'].dropna()

    # --- 3. HOURLY SPEEDS ---
    def parse_hour(t_str):
        try:
            return int(str(t_str).split(':')[0])
        except:
            return None

    df_clean['hour'] = df_clean['time'].apply(parse_hour)
    hourly = df_clean.groupby('hour')['speed'].agg(
        pings='count',
        mean_speed='mean',
        moving_speed=lambda x: x[x > 0].mean() if (x > 0).sum() > 0 else 0
    ).reset_index()
    hourly['mean_kmh'] = hourly['mean_speed'] * 3.6
    hourly['moving_kmh'] = hourly['moving_speed'] * 3.6

    # Generate Hourly Speed Chart
    plt.figure(figsize=(10, 5), dpi=150)
    plt.plot(hourly['hour'], hourly['moving_kmh'], marker='o', color='#1a73e8', linewidth=2, label='Moving Speed (> 0 m/s)')
    plt.plot(hourly['hour'], hourly['mean_kmh'], marker='s', color='#ea4335', linewidth=2, linestyle='--', label='Commercial Speed (Overall)')
    plt.title('Delhi Transit: Average Bus Speed by Hour of Day', fontsize=14, pad=12)
    plt.xlabel('Hour of Day (24h)', fontsize=11)
    plt.ylabel('Speed (km/h)', fontsize=11)
    plt.xticks(range(0, 24))
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(frameon=True)
    plt.tight_layout()
    chart_path = os.path.join(output_dir, 'hourly_speed_profile.png')
    plt.savefig(chart_path)
    plt.close()
    print(f"Chart saved to {chart_path}")

    # --- 4. FASTEST & SLOWEST ROUTES ---
    route_speed = df_clean.groupby('route_id')['speed'].agg(
        pings='count',
        mean_speed='mean',
        moving_speed=lambda x: x[x > 0].mean() if (x > 0).sum() > 0 else 0
    ).reset_index()

    if routes_path and os.path.exists(routes_path):
        routes_df = pd.read_csv(routes_path)
        route_speed = route_speed.merge(routes_df[['route_id', 'route_long_name']], on='route_id', how='left')

    qualified = route_speed[route_speed['pings'] >= 500].copy()
    qualified['mean_kmh'] = qualified['mean_speed'] * 3.6
    qualified['moving_kmh'] = qualified['moving_speed'] * 3.6

    fastest = qualified.sort_values(by='mean_kmh', ascending=False).head(10)
    slowest = qualified.sort_values(by='mean_kmh', ascending=True).head(10)

    print("\nEDA Completed Successfully.")
    return {
        'total_raw': total_raw,
        'duplicates_count': duplicates_count,
        'dup_pct': dup_pct,
        'zero_coords': zero_coords,
        'out_of_bounds': out_of_bounds,
        'neg_speeds': neg_speeds,
        'zero_speeds': zero_speeds,
        'zero_speed_pct': zero_speed_pct,
        'max_speed_kmh': max_speed_kmh,
        'total_buses': total_buses,
        'bus_counts': bus_counts,
        'gaps': gaps,
        'hourly': hourly,
        'fastest': fastest,
        'slowest': slowest
    }

if __name__ == '__main__':
    run_gps_eda()
