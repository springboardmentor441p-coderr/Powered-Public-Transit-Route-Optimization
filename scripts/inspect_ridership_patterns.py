
import json
import urllib.parse
import urllib.request

print("Checking non-zero passenger ridership records...")

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

query = """
SELECT
    transit_timestamp,
    bus_route,
    SUM(ridership) AS hourly_ridership
WHERE ridership > 0
GROUP BY transit_timestamp, bus_route
ORDER BY transit_timestamp DESC
LIMIT 15
"""

params = urllib.parse.urlencode({"$query": query})
url = API_URL + "?" + params

try:
    with urllib.request.urlopen(url, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("\nNON-ZERO HOURLY RIDERSHIP RECORDS:\n")

    for row in data:
        print(
            f"Timestamp: {row['transit_timestamp']} | "
            f"Route: {row['bus_route']} | "
            f"Total Riders: {float(row['hourly_ridership']):,.0f}"
        )

    if not data:
        print("No non-zero records found.")

except Exception as e:
    print("Error retrieving ridership data:", e)
