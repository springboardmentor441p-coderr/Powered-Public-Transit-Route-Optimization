
import pandas as pd

ROUTES = ['M15+', 'M15', 'B6', 'Q58', 'Q44+', 'BX12+', 'Q27', 'M101']

print("CHECKING HOURLY DATA OVERLAP")
print("=" * 60)

# Load cleaned passenger ridership data
ridership = pd.read_csv(
    'data/hourly_ridership_training_cleaned.csv'
)

ridership['timestamp'] = pd.to_datetime(
    ridership['timestamp'], errors='coerce'
)

ridership = ridership[
    ridership['bus_route'].isin(ROUTES)
].dropna(subset=['timestamp', 'bus_route'])

ridership_keys = ridership[
    ['timestamp', 'bus_route']
].drop_duplicates()

# Load only the required speed dataset columns
speed = pd.read_csv(
    'export.csv',
    usecols=[
        'Timestamp',
        'Route ID',
        'Average Road Speed',
        'Average Travel Time',
        'Bus Trip Count'
    ]
)

speed['Timestamp'] = pd.to_datetime(
    speed['Timestamp'], errors='coerce'
)

for col in [
    'Average Road Speed',
    'Average Travel Time',
    'Bus Trip Count'
]:
    speed[col] = pd.to_numeric(speed[col], errors='coerce')

speed = speed[
    speed['Route ID'].isin(ROUTES)
].dropna(
    subset=[
        'Timestamp',
        'Route ID',
        'Average Road Speed',
        'Average Travel Time',
        'Bus Trip Count'
    ]
)

# Calculate weighted values for each route-hour
speed['speed_weighted'] = (
    speed['Average Road Speed'] * speed['Bus Trip Count']
)

speed['time_weighted'] = (
    speed['Average Travel Time'] * speed['Bus Trip Count']
)

speed_hourly = speed.groupby(
    ['Timestamp', 'Route ID']
).agg(
    weighted_speed_sum=('speed_weighted', 'sum'),
    weighted_time_sum=('time_weighted', 'sum'),
    total_trips=('Bus Trip Count', 'sum')
).reset_index()

speed_hourly['average_speed'] = (
    speed_hourly['weighted_speed_sum'] /
    speed_hourly['total_trips'].where(speed_hourly['total_trips'] > 0)
)

speed_hourly['average_travel_time'] = (
    speed_hourly['weighted_time_sum'] /
    speed_hourly['total_trips'].where(speed_hourly['total_trips'] > 0)
)

speed_hourly = speed_hourly.dropna(
    subset=['average_speed', 'average_travel_time']
)

speed_keys = speed_hourly[
    ['Timestamp', 'Route ID']
].drop_duplicates()

# Compare route-hour combinations
matched = ridership_keys.merge(
    speed_keys,
    left_on=['timestamp', 'bus_route'],
    right_on=['Timestamp', 'Route ID'],
    how='inner'
)

print("\nOVERALL RESULTS")
print("-" * 60)
print("Unique ridership route-hours:", len(ridership_keys))
print("Unique speed route-hours:", len(speed_keys))
print("Matching route-hours:", len(matched))
print(
    "Ridership route-hours without speed:",
    len(ridership_keys) - len(matched)
)

print("\nMATCHING RESULTS BY ROUTE")
print("-" * 60)

for route in ROUTES:
    demand_count = (
        ridership_keys['bus_route'] == route
    ).sum()

    speed_count = (
        speed_keys['Route ID'] == route
    ).sum()

    match_count = (
        matched['bus_route'] == route
    ).sum()

    print(
        f"{route:<10} "
        f"Ridership: {demand_count:<8} "
        f"Speed: {speed_count:<8} "
        f"Matched: {match_count}"
    )

print("\nOverlap check completed.")
