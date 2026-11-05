
import json
import urllib.parse
import urllib.request

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

def analyze_peak_routes(hour, label):

    print(f"\nTOP 10 ROUTES AT {label}:\n")

    query = f"""
    SELECT bus_route, SUM(ridership) AS total_ridership
    WHERE date_extract_hh(transit_timestamp) = {hour}
    GROUP BY bus_route
    ORDER BY total_ridership DESC
    LIMIT 10
    """

    params = urllib.parse.urlencode({"$query": query})
    url = API_URL + "?" + params

    with urllib.request.urlopen(url, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    for index, row in enumerate(data, start=1):
        print(
            f"{index}. {row['bus_route']} - "
            f"{float(row['total_ridership']):,.0f} riders"
        )


print("Analyzing busiest routes during peak hours...")

try:
    analyze_peak_routes(7, "7 AM")
    analyze_peak_routes(17, "5 PM")

except Exception as e:
    print("Error:", e)
