import pandas as pd

file_path = r"C:\Users\annam\Downloads\export.csv"

target_routes = [
    "M15", "Q25", "B6", "Q58",
    "Q44", "BX12", "Q27", "M86", "M101"
]

found_routes = set()

for chunk in pd.read_csv(
    file_path,
    usecols=["Route ID"],
    dtype="string",
    chunksize=100000
):
    routes = chunk["Route ID"].dropna().unique()
    found_routes.update(routes)

print("\nROUTE MATCHES IN SPEED DATASET:\n")

for route in target_routes:
    matches = sorted(
        r for r in found_routes
        if route in r
    )

    print(f"{route}: {matches if matches else 'No match'}")