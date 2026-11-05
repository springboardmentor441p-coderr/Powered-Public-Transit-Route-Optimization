
import json
import urllib.parse
import urllib.request

print("Analyzing hourly passenger demand...")

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

query = """
SELECT
    date_extract_hh(transit_timestamp) AS hour,
    SUM(ridership) AS total_ridership
GROUP BY hour
ORDER BY total_ridership DESC
LIMIT 24
"""

params = urllib.parse.urlencode({"$query": query})
url = API_URL + "?" + params

try:
    with urllib.request.urlopen(url, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("\nPASSENGER DEMAND BY HOUR:\n")

    for row in data:
        hour = int(row["hour"])
        riders = float(row["total_ridership"])

        time_label = (
            "12 AM" if hour == 0 else
            "12 PM" if hour == 12 else
            f"{hour % 12} {'AM' if hour < 12 else 'PM'}"
        )

        print(f"{time_label:8} - {riders:,.0f} riders")

except Exception as e:
    print("Error retrieving ridership data:", e)
