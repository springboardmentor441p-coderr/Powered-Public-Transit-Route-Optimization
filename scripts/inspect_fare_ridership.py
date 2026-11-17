
import json
import urllib.parse
import urllib.request

print("Inspecting ridership by fare category...")

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

query = """
SELECT
    fare_class_category,
    COUNT(*) AS total_records,
    SUM(ridership) AS total_ridership
WHERE transit_timestamp >= '2026-10-20T00:00:00'
AND transit_timestamp < '2026-10-26T00:00:00'
GROUP BY fare_class_category
ORDER BY total_ridership DESC
LIMIT 20
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

    print("\nFARE CATEGORY RIDERSHIP:\n")

    for row in data:
        print(
            f"Category: {row['fare_class_category']} | "
            f"Records: {row['total_records']} | "
            f"Riders: {float(row['total_ridership']):,.0f}"
        )

except Exception as e:
    print("Error:", e)
