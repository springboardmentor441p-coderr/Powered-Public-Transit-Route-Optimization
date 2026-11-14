"""
Module 2: Feature Engineering
Builds route-level feature profiles from raw GTFS data.
"""
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt


def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great-circle distance between two points (in km)."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def clean_data(data: dict) -> dict:
    """
    Clean all DataFrames: handle missing values, fix types.
    """
    # --- routes ---
    routes = data['routes'].copy()
    routes['route_type'] = routes['route_type'].fillna(3).astype(int)
    routes['route_short_name'] = routes['route_short_name'].fillna(routes['route_id'])
    routes['route_long_name'] = routes['route_long_name'].fillna('')

    # --- trips ---
    trips = data['trips'].copy()
    trips['direction_id'] = trips['direction_id'].fillna(0).astype(int)

    # --- stop_times ---
    stop_times = data['stop_times'].copy()
    # Parse arrival/departure times — some may be blank
    stop_times['arrival_time'] = stop_times['arrival_time'].replace('', np.nan)
    stop_times['departure_time'] = stop_times['departure_time'].replace('', np.nan)

    # --- stops ---
    stops = data['stops'].copy()
    stops = stops.dropna(subset=['stop_lat', 'stop_lon'])

    # --- calendar ---
    calendar = data['calendar'].copy()

    data['routes'] = routes
    data['trips'] = trips
    data['stop_times'] = stop_times
    data['stops'] = stops
    data['calendar'] = calendar

    print("✅ Data cleaning completed.")
    return data


def extract_time_features(stop_times: pd.DataFrame) -> pd.DataFrame:
    """
    Extract hour_of_day from arrival_time.
    """
    def parse_hour(t):
        if pd.isna(t) or t == '':
            return np.nan
        try:
            parts = str(t).split(':')
            return int(parts[0]) % 24
        except Exception:
            return np.nan

    stop_times = stop_times.copy()
    stop_times['hour_of_day'] = stop_times['arrival_time'].apply(parse_hour)
    return stop_times


def build_route_profiles(data: dict) -> pd.DataFrame:
    """
    Build comprehensive route-level feature profiles.

    Features per route:
    - trip_count: Total number of trips
    - unique_stops: Number of unique stops served
    - avg_stops_per_trip: Average stops per trip
    - route_length_km: Estimated route length (sum of haversine between consecutive stops)
    - operating_hours: Span of hours the route operates
    - peak_hour_trips: Max trips in any single hour
    - off_peak_trips: Min trips in any single hour (non-zero)
    - peak_ratio: peak_hour_trips / avg trips per hour
    - weekday_service: Whether route runs on weekdays
    - weekend_service: Whether route runs on weekends
    - stop_frequency: Total stop visits across all trips
    - direction_count: Number of directions (1 or 2)
    - avg_trip_duration_min: Average trip duration in minutes
    """
    routes = data['routes']
    trips = data['trips']
    stop_times = data['stop_times']
    stops = data['stops']
    calendar = data['calendar']

    # Add time features
    stop_times = extract_time_features(stop_times)

    # Merge trips with routes
    trip_route = trips.merge(routes[['route_id', 'route_short_name', 'route_long_name', 'route_type']],
                             on='route_id', how='left')

    # Merge stop_times with trip_route
    st_full = stop_times.merge(trip_route[['trip_id', 'route_id', 'direction_id', 'service_id']],
                                on='trip_id', how='left')

    # Merge with stops for coordinates
    st_full = st_full.merge(stops[['stop_id', 'stop_lat', 'stop_lon', 'stop_name']],
                             on='stop_id', how='left')

    # Merge with calendar for day-of-week info
    trip_cal = trip_route.merge(calendar, on='service_id', how='left')

    # ---- Compute route-level features ----
    profiles = []

    for route_id in routes['route_id'].unique():
        route_trips = trip_route[trip_route['route_id'] == route_id]
        route_st = st_full[st_full['route_id'] == route_id]

        if len(route_trips) == 0 or len(route_st) == 0:
            continue

        trip_count = route_trips['trip_id'].nunique()
        unique_stops = route_st['stop_id'].nunique()
        avg_stops_per_trip = route_st.groupby('trip_id')['stop_id'].count().mean()

        # Direction count
        direction_count = route_trips['direction_id'].nunique()

        # Route length estimation using first trip's stop sequence
        first_trip_id = route_trips['trip_id'].iloc[0]
        first_trip_stops = route_st[route_st['trip_id'] == first_trip_id].sort_values('stop_sequence')
        route_length_km = 0.0
        coords = first_trip_stops[['stop_lat', 'stop_lon']].dropna().values
        if len(coords) > 1:
            for i in range(1, len(coords)):
                route_length_km += haversine(coords[i - 1][1], coords[i - 1][0],
                                              coords[i][1], coords[i][0])

        # Hourly trip distribution
        hourly = route_st.dropna(subset=['hour_of_day']).groupby('hour_of_day')['trip_id'].nunique()
        if len(hourly) > 0:
            peak_hour_trips = hourly.max()
            operating_hours = hourly.index.max() - hourly.index.min() + 1
            avg_hourly_trips = hourly.mean()
            peak_ratio = peak_hour_trips / avg_hourly_trips if avg_hourly_trips > 0 else 1.0
            off_peak_trips = hourly[hourly > 0].min() if len(hourly[hourly > 0]) > 0 else 0
        else:
            peak_hour_trips = 0
            operating_hours = 0
            peak_ratio = 1.0
            off_peak_trips = 0

        # Trip duration estimation (first – last timepoint)
        durations = []
        for tid, grp in route_st.groupby('trip_id'):
            times = grp.dropna(subset=['arrival_time'])['arrival_time']
            if len(times) >= 2:
                try:
                    first_t = times.iloc[0]
                    last_t = times.iloc[-1]
                    fp = first_t.split(':')
                    lp = last_t.split(':')
                    dur = (int(lp[0]) * 60 + int(lp[1])) - (int(fp[0]) * 60 + int(fp[1]))
                    if dur > 0:
                        durations.append(dur)
                except Exception:
                    pass
        avg_trip_duration_min = np.mean(durations) if durations else 0

        # Total stop visits (proxy for demand/load)
        stop_frequency = len(route_st)

        # Calendar features
        route_cal = trip_cal[trip_cal['route_id'] == route_id]
        weekday_service = 0
        weekend_service = 0
        if len(route_cal) > 0:
            weekday_cols = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
            weekend_cols = ['saturday', 'sunday']
            if any(col in route_cal.columns for col in weekday_cols):
                weekday_service = int(route_cal[weekday_cols].max().max() > 0) if all(
                    col in route_cal.columns for col in weekday_cols) else 1
            if any(col in route_cal.columns for col in weekend_cols):
                weekend_service = int(route_cal[weekend_cols].max().max() > 0) if all(
                    col in route_cal.columns for col in weekend_cols) else 0

        # Route name
        rinfo = routes[routes['route_id'] == route_id].iloc[0]

        profiles.append({
            'route_id': route_id,
            'route_short_name': rinfo['route_short_name'],
            'route_long_name': rinfo['route_long_name'],
            'route_type': rinfo['route_type'],
            'trip_count': trip_count,
            'unique_stops': unique_stops,
            'avg_stops_per_trip': round(avg_stops_per_trip, 2),
            'route_length_km': round(route_length_km, 2),
            'operating_hours': operating_hours,
            'peak_hour_trips': peak_hour_trips,
            'off_peak_trips': off_peak_trips,
            'peak_ratio': round(peak_ratio, 2),
            'avg_trip_duration_min': round(avg_trip_duration_min, 2),
            'stop_frequency': stop_frequency,
            'direction_count': direction_count,
            'weekday_service': weekday_service,
            'weekend_service': weekend_service,
        })

    profiles_df = pd.DataFrame(profiles)
    print(f"✅ Built route profiles for {len(profiles_df)} routes.")
    return profiles_df


if __name__ == "__main__":
    import os
    from data_collection import load_gtfs_data

    GTFS_DIR = os.path.join(os.path.dirname(__file__), '..', 'gtfs')
    data = load_gtfs_data(GTFS_DIR)
    data = clean_data(data)
    profiles = build_route_profiles(data)
    print(profiles.head(10))
    print(f"\nProfile shape: {profiles.shape}")
    profiles.to_csv(os.path.join(os.path.dirname(__file__), '..', 'outputs', 'route_profiles.csv'), index=False)
    print("✅ Saved route_profiles.csv")
