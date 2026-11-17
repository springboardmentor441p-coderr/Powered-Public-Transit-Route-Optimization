
import csv
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

ROUTES = [
    "M15+",
    "M15",
    "B6",
    "Q58",
    "Q44+",
    "BX12+",
    "Q27",
    "M101"
]

START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 9, 2)  # Exclusive: includes Sep 1

OUTPUT_FILE = "data/hourly_ridership_training.csv"


def next_month(current):
    if current.month == 12:
        return date(current.year + 1, 1, 1)

    return date(current.year, current.month + 1, 1)


def fetch_month(month_start, month_end):
    route_values = ", ".join(
        "'" + route.replace("'", "''") + "'"
        for route in ROUTES
    )

    query = f"""
    SELECT
        transit_timestamp,
        bus_route,
        SUM(ridership) AS total_passengers
    WHERE transit_timestamp >= '{month_start}T00:00:00'
    AND transit_timestamp < '{month_end}T00:00:00'
    AND bus_route IN ({route_values})
    GROUP BY transit_timestamp, bus_route
    ORDER BY transit_timestamp, bus_route
    LIMIT 50000
    """

    params = urllib.parse.urlencode({"$query": query})
    url = API_URL + "?" + params

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NYC-Bus-Demand-Prediction/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    print("Preparing hourly passenger-demand dataset...")
    print("Routes:", ", ".join(ROUTES))
    print("Period:", START_DATE, "to", END_DATE)

    all_rows = []
    current = START_DATE
    month_count = 0

    while current < END_DATE:
        month_end = min(next_month(current), END_DATE)

        print(f"\nFetching {current.strftime('%B %Y')}...")

        try:
            records = fetch_month(current, month_end)

            for row in records:
                all_rows.append({
                    "timestamp": row["transit_timestamp"],
                    "bus_route": row["bus_route"],
                    "total_passengers": int(
                        float(row["total_passengers"])
                    )
                })

            print("Records retrieved:", len(records))
            month_count += 1

        except Exception as error:
            print("Error fetching", current, ":", error)
            print("Stopping extraction. No partial file will be saved.")
            return

        current = month_end
        time.sleep(1)

    all_rows.sort(
        key=lambda row: (row["timestamp"], row["bus_route"])
    )

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "bus_route",
                "total_passengers"
            ]
        )

        writer.writeheader()
        writer.writerows(all_rows)

    print("\nDATASET PREPARATION COMPLETE")
    print("Months processed:", month_count)
    print("Total hourly records:", len(all_rows))
    print("Output file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
