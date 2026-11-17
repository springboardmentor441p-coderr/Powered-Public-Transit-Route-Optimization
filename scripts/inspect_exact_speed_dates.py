
import pandas as pd

ROUTES = ['M15+', 'M15', 'B6', 'Q58', 'Q44+', 'BX12+', 'Q27', 'M101']

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

print("\nEXACT SPEED OBSERVATION DATES")
print("=" * 60)

for route in ROUTES:
    route_data = speed[speed['Route ID'] == route]

    print(f"\nROUTE: {route}")
    print("-" * 40)

    dates = (
        route_data[['Month', 'Date']]
        .drop_duplicates()
        .sort_values(['Month', 'Date'])
    )

    for _, row in dates.iterrows():
        print(f"{row['Month']} : {row['Date']}")

print("\nInspection completed.")
