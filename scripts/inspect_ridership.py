
import json
import urllib.parse
import urllib.request

print("Analyzing bus passenger ridership...")

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

query = """
SELECT bus_route, SUM(ridership) AS total_ridership
GROUP BY bus_route
ORDER BY total_ridership DESC
LIMIT 10
"""

params = urllib.parse.urlencode({"$query": query})
url = API_URL + "?" + params

try:
    with urllib.request.urlopen(url, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("\nTOP 10 BUSIEST BUS ROUTES:\n")

    for index, row in enumerate(data, start=1):
        route = row["bus_route"]
        riders = float(row["total_ridership"])

        print(f"{index}. {route}: {riders:,.0f} riders")

except Exception as e:
    print("Error retrieving ridership data:", e)
