
import json
import urllib.parse
import urllib.request

print("Testing hourly passenger-demand aggregation...")

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

query = """
SELECT
    transit_timestamp,
    bus_route,
    SUM(ridership) AS total_passengers
WHERE transit_timestamp >= '2026-10-20T00:00:00'
AND transit_timestamp < '2026-10-21T00:00:00'
AND bus_route = 'M15'
GROUP BY transit_timestamp, bus_route
ORDER BY transit_timestamp
LIMIT 30
"""

params = urllib.parse.urlencode({"$query": query})
url = API_URL + "?" + params

request = urllib.request.Request(
    url,
    headers={
        "User-Agent": "NYC-Bus-Ridership-Analysis/1.0"
    }
)

try:
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("\nM15 HOURLY PASSENGER DEMAND:\n")

    for row in data:
        print(
            f"Time: {row['transit_timestamp']} | "
            f"Route: {row['bus_route']} | "
            f"Passengers: {float(row['total_passengers']):,.0f}"
        )

    print("\nTotal hourly records:", len(data))

except Exception as e:
    print("Error:", e)
