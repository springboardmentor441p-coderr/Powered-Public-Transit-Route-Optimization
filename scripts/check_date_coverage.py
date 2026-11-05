
import json
import urllib.parse
import urllib.request
import pandas as pd

SPEED_FILE = r"C:\Users\annam\Downloads\export.csv"
API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

print("CHECKING DATASET DATE COVERAGE")

# --------------------------------
# 1. RIDERSHIP DATASET
# --------------------------------

print("\nChecking ridership dataset...")

query = """
SELECT
    MIN(transit_timestamp) AS first_date,
    MAX(transit_timestamp) AS last_date
"""

params = urllib.parse.urlencode({"$query": query})
url = API_URL + "?" + params

try:
    with urllib.request.urlopen(url, timeout=300) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("Ridership earliest date:", data[0]["first_date"])
    print("Ridership latest date:", data[0]["last_date"])

except Exception as e:
    print("Ridership date check failed:", e)


# --------------------------------
# 2. SPEED DATASET
# --------------------------------

print("\nChecking speed dataset...")

earliest = None
latest = None

for chunk in pd.read_csv(
    SPEED_FILE,
    usecols=["Timestamp"],
    chunksize=100000
):
    dates = pd.to_datetime(
        chunk["Timestamp"],
        errors="coerce",
        format="mixed"
    ).dropna()

    if not dates.empty:
        chunk_min = dates.min()
        chunk_max = dates.max()

        if earliest is None or chunk_min < earliest:
            earliest = chunk_min

        if latest is None or chunk_max > latest:
            latest = chunk_max

print("Speed earliest date:", earliest)
print("Speed latest date:", latest)

print("\nDate coverage check completed.")
