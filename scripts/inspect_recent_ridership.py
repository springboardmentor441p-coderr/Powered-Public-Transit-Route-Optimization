
import json
import urllib.parse
import urllib.request

print("Investigating recent passenger ridership records...")

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

query = """
SELECT
    date_trunc_ymd(transit_timestamp) AS day,
    COUNT(*) AS total_records,
    SUM(ridership) AS total_ridership
WHERE transit_timestamp >= '2026-10-20T00:00:00'
GROUP BY day
ORDER BY day DESC
"""

params = urllib.parse.urlencode({"$query": query})
url = API_URL + "?" + params

try:
    with urllib.request.urlopen(url, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("\nDAILY RIDERSHIP SUMMARY:\n")

    for row in data:
        print(
            f"Date: {row['day']} | "
            f"Records: {int(row['total_records']):,} | "
            f"Total Riders: {float(row['total_ridership']):,.0f}"
        )

except Exception as e:
    print("Error retrieving recent ridership:", e)
