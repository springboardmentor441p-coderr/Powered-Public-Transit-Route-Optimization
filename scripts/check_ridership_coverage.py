
import json
import urllib.parse
import urllib.request

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

def run_query(query):
    params = urllib.parse.urlencode({"$query": query})
    url = API_URL + "?" + params

    with urllib.request.urlopen(url, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))

try:
    print("Checking passenger ridership date coverage...")

    latest_overall = run_query("""
        SELECT MAX(transit_timestamp) AS latest_timestamp
    """)

    latest_nonzero = run_query("""
        SELECT MAX(transit_timestamp) AS latest_nonzero_timestamp
        WHERE ridership > 0
    """)

    earliest_nonzero = run_query("""
        SELECT MIN(transit_timestamp) AS earliest_nonzero_timestamp
        WHERE ridership > 0
    """)

    print("\nDATE COVERAGE RESULTS:\n")

    print(
        "Earliest non-zero record:",
        earliest_nonzero[0]["earliest_nonzero_timestamp"]
    )

    print(
        "Latest record in dataset:",
        latest_overall[0]["latest_timestamp"]
    )

    print(
        "Latest non-zero record:",
        latest_nonzero[0]["latest_nonzero_timestamp"]
    )

except Exception as e:
    print("Error checking date coverage:", e)
