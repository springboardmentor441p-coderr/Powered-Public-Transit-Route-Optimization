
import pandas as pd

routes = ['M15+', 'M15', 'B6', 'Q58', 'Q44+', 'BX12+', 'Q27', 'M101']

# Read only the route columns
speed = pd.read_csv('export.csv', usecols=['Route ID'])
ridership = pd.read_csv(
    'data/hourly_ridership_training_cleaned.csv',
    usecols=['bus_route']
)

print("\nROUTE COVERAGE COMPARISON")
print("-" * 50)
print(f"{'Route':<12}{'Ridership Records':<22}{'Speed Records'}")
print("-" * 50)

for route in routes:
    ridership_count = (ridership['bus_route'] == route).sum()
    speed_count = (speed['Route ID'] == route).sum()

    print(f"{route:<12}{ridership_count:<22}{speed_count}")

print("-" * 50)
