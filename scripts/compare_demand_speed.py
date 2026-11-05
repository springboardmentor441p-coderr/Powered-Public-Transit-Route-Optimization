
import json
import urllib.parse
import urllib.request
import pandas as pd

# --------------------------------
# FILE LOCATIONS AND SETTINGS
# --------------------------------

SPEED_FILE = r"C:\Users\annam\Downloads\export.csv"
API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

START_DATE = "2025-01-01T00:00:00"
END_DATE = "2026-09-01T23:00:00"

# Exact route matches found in both datasets
routes = [
    "M15+",
    "M15",
    "B6",
    "Q58",
    "Q44+",
    "BX12+",
    "Q27",
    "M101"
]

# Peak hours
peak_hours = [7, 8, 15, 16, 17]

print("Analyzing passenger demand and bus speeds...")
print(f"Common date range: {START_DATE} to {END_DATE}")


# --------------------------------
# PART 1: GET RIDERSHIP DATA
# --------------------------------

ridership_results = {}

print("\nRetrieving ridership data route by route...")

for route in routes:

    print(f"Fetching {route}...")

    query = f"""
    SELECT
        bus_route,
        date_extract_hh(transit_timestamp) AS hour,
        SUM(ridership) AS total_ridership
    WHERE
        bus_route = '{route}'
        AND transit_timestamp >= '{START_DATE}'
        AND transit_timestamp <= '{END_DATE}'
        AND date_extract_hh(transit_timestamp)
            IN (7, 8, 15, 16, 17)
    GROUP BY bus_route, hour
    ORDER BY hour
    """

    params = urllib.parse.urlencode({"$query": query})
    url = API_URL + "?" + params

    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        for row in data:
            key = (row["bus_route"], int(row["hour"]))

            ridership_results[key] = float(
                row["total_ridership"]
            )

    except Exception as e:
        print(f"Could not retrieve {route}: {e}")

print("\nRidership retrieval completed.")


# --------------------------------
# PART 2: ANALYZE SPEED DATA
# --------------------------------

print("\nAnalyzing speed dataset...")

speed_totals = {}

for chunk in pd.read_csv(
    SPEED_FILE,
    usecols=[
        "Route ID",
        "Timestamp",
        "Hour of Day",
        "Average Road Speed"
    ],
    dtype="string",
    chunksize=100000
):

    # Convert timestamp
    chunk["Timestamp"] = pd.to_datetime(
        chunk["Timestamp"],
        errors="coerce",
        format="mixed"
    )

    # Apply common date range
    chunk = chunk[
        (chunk["Timestamp"] >= START_DATE)
        & (chunk["Timestamp"] <= END_DATE)
    ]

    # Clean route IDs
    chunk["Route ID"] = chunk["Route ID"].str.strip()

    # Convert numeric columns
    chunk["Hour of Day"] = pd.to_numeric(
        chunk["Hour of Day"],
        errors="coerce"
    )

    chunk["Average Road Speed"] = pd.to_numeric(
        chunk["Average Road Speed"],
        errors="coerce"
    )

    # Keep only selected routes and peak hours
    chunk = chunk[
        chunk["Route ID"].isin(routes)
        & chunk["Hour of Day"].isin(peak_hours)
    ]

    chunk = chunk.dropna(
        subset=["Hour of Day", "Average Road Speed"]
    )

    # Calculate speed totals and record counts
    grouped = chunk.groupby(
        ["Route ID", "Hour of Day"]
    )["Average Road Speed"].agg(["sum", "count"])

    for (route, hour), row in grouped.iterrows():

        key = (route, int(hour))

        if key not in speed_totals:
            speed_totals[key] = [0, 0]

        speed_totals[key][0] += row["sum"]
        speed_totals[key][1] += row["count"]


print("Speed analysis completed.")


# --------------------------------
# PART 3: COMPARE BOTH DATASETS
# --------------------------------

print("\nPASSENGER DEMAND VS AVERAGE BUS SPEED")
print("Speed is measured in miles per hour (mph).")

print("\n" + "=" * 75)

for route in routes:

    print(f"\nROUTE: {route}")
    print("-" * 75)

    print(
        f"{'Hour':<12}"
        f"{'Passengers':>18}"
        f"{'Average Speed':>20}"
    )

    for hour in peak_hours:

        key = (route, hour)

        riders = ridership_results.get(key)
        speed_values = speed_totals.get(key)

        time_label = (
            "7 AM" if hour == 7 else
            "8 AM" if hour == 8 else
            "3 PM" if hour == 15 else
            "4 PM" if hour == 16 else
            "5 PM"
        )

        if riders is not None and speed_values:

            average_speed = (
                speed_values[0] / speed_values[1]
            )

            print(
                f"{time_label:<12}"
                f"{riders:>18,.0f}"
                f"{average_speed:>17.2f} mph"
            )

        else:

            print(
                f"{time_label:<12}"
                f"{'No data':>18}"
                f"{'No data':>20}"
            )


print("\nAnalysis completed.")
