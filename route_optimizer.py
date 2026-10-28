
import pandas as pd
from pathlib import Path

# GTFS dataset directory
DATA_DIR = Path("data/chennai_mtc_gtfs")


def load_gtfs_data():
    """Load Chennai public transit GTFS data."""
    files = {
        "stops": "stops.txt",
        "routes": "routes.txt",
        "trips": "trips.txt",
        "stop_times": "stop_times.txt",
    }

    data = {}

    for key, filename in files.items():
        file_path = DATA_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Missing {file_path}. Download and extract "
                "the GTFS dataset before running this program."
            )

        data[key] = pd.read_csv(file_path, dtype=str).fillna("")

    return data


def find_routes(start_stop, end_stop):
    """Find direct scheduled trips between two bus stops."""
    data = load_gtfs_data()

    stops = data["stops"]
    routes = data["routes"]
    trips = data["trips"]
    stop_times = data["stop_times"]

    start_matches = stops[
        stops["stop_name"].str.contains(
            start_stop, case=False, regex=False, na=False
        )
    ]

    end_matches = stops[
        stops["stop_name"].str.contains(
            end_stop, case=False, regex=False, na=False
        )
    ]

    if start_matches.empty:
        print(f"Starting stop not found: {start_stop}")
        return

    if end_matches.empty:
        print(f"Destination stop not found: {end_stop}")
        return

    stop_times["stop_sequence"] = pd.to_numeric(
        stop_times["stop_sequence"], errors="coerce"
    )
    stop_times = stop_times.dropna(subset=["stop_sequence"])

    start_ids = set(start_matches["stop_id"])
    end_ids = set(end_matches["stop_id"])

    start_times = stop_times[
        stop_times["stop_id"].isin(start_ids)
    ][["trip_id", "stop_sequence"]].rename(
        columns={"stop_sequence": "start_sequence"}
    )

    end_times = stop_times[
        stop_times["stop_id"].isin(end_ids)
    ][["trip_id", "stop_sequence"]].rename(
        columns={"stop_sequence": "end_sequence"}
    )

    matching = start_times.merge(end_times, on="trip_id")

    matching = matching[
        matching["start_sequence"] < matching["end_sequence"]
    ]

    if matching.empty:
        print("No direct scheduled trip found between these stops.")
        return

    matching = matching.merge(
        trips[["trip_id", "route_id"]].drop_duplicates(),
        on="trip_id",
        how="inner",
    )

    results = matching.merge(routes, on="route_id", how="left")

    columns = [
        col for col in
        ["route_id", "route_short_name", "route_long_name"]
        if col in results.columns
    ]

    print("\nDirect bus routes found:")
    print(results[columns].drop_duplicates().to_string(index=False))


if __name__ == "__main__":
    # Replace these with stop names from your stops.txt file.
    START_STOP = "Central"
    END_STOP = "T Nagar"

    try:
        find_routes(START_STOP, END_STOP)
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
        print(f"Error: {error}")
