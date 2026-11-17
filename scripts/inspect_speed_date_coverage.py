
import pandas as pd

ROUTES = ['M15+', 'M15', 'B6', 'Q58', 'Q44+', 'BX12+', 'Q27', 'M101']

print("INSPECTING SPEED DATA DATE COVERAGE")
print("=" * 60)

speed = pd.read_csv(
    'export.csv',
    usecols=['Timestamp', 'Route ID']
)

speed['Timestamp'] = pd.to_datetime(
    speed['Timestamp'],
    errors='coerce'
)

speed = speed[
    speed['Route ID'].isin(ROUTES)
].dropna(subset=['Timestamp'])

speed['Date'] = speed['Timestamp'].dt.date
speed['Month'] = speed['Timestamp'].dt.to_period('M')
speed['Hour'] = speed['Timestamp'].dt.hour

print("\nUNIQUE OBSERVATION DATES BY ROUTE")
print("-" * 60)

for route in ROUTES:
    route_data = speed[speed['Route ID'] == route]

    print(
        f"{route:<10} "
        f"Unique dates: {route_data['Date'].nunique():<6} "
        f"Unique hours: {route_data['Hour'].nunique():<6} "
        f"Route-hour records: {len(route_data.groupby(['Timestamp']).size()):<6}"
    )

print("\nMONTHLY SPEED OBSERVATION COVERAGE")
print("-" * 60)

monthly = (
    speed.groupby(['Month', 'Route ID'])
    .agg(
        unique_dates=('Date', 'nunique'),
        unique_hours=('Hour', 'nunique'),
        records=('Timestamp', 'count')
    )
    .reset_index()
)

for route in ROUTES:
    print(f"\n{route}:")
    route_monthly = monthly[monthly['Route ID'] == route]

    if route_monthly.empty:
        print("No observations")
        continue

    print(route_monthly.to_string(index=False))

print("\nDate coverage inspection completed.")
