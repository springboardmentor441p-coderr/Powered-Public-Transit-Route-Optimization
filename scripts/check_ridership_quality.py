
import json
import urllib.parse
import urllib.request
import urllib.error

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

dates = [
    "2026-10-20",
    "2026-10-21",
    "2026-10-22",
    "2026-10-23",
    "2026-10-24",
    "2026-10-25",
    "2026-10-26",
    "2026-10-27"
]

print("Comparing daily ridership samples...\n")

for day in dates:

    params = urllib.parse.urlencode({
        "$where": (
            f"transit_timestamp >= '{day}T00:00:00' "
            f"AND transit_timestamp < '{day}T23:00:00'"
        ),
        "$limit": 1000,
        "$select": "ridership"
    })

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

        zero_count = sum(
            1 for row in data if int(row["ridership"]) == 0
        )

        nonzero_count = len(data) - zero_count

        total_riders = sum(
            int(row["ridership"]) for row in data
        )

        print(
            f"{day} | Records: {len(data)} | "
            f"Zero: {zero_count} | "
            f"Non-zero: {nonzero_count} | "
            f"Sample riders: {total_riders:,}"
        )

    except Exception as e:
        print(f"{day} | Error: {e}")
