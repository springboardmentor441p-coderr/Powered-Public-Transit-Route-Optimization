
import pandas as pd

# Dataset location
FILE_PATH = r"C:\Users\annam\Downloads\export.csv"

# Common date range
START_DATE = "2025-01-01 00:00:00"
END_DATE = "2026-09-01 23:00:00"

# Selected routes and afternoon peak hours
ROUTES = ["M15", "Q58", "M101", "B6"]
PEAK_HOURS = [15, 16, 17]

# Required dataset columns
USE_COLUMNS = [
    "Route ID",
    "Timestamp",
    "Hour of Day",
    "Timepoint Stop Name",
    "Next Timepoint Stop Name",
    "Average Road Speed",
    "Average Travel Time",
    "Road Distance",
    "Bus Trip Count"
]

print("Analyzing slow bus route segments...")

# Store grouped results
all_data = []

# Read dataset in chunks
for chunk in pd.read_csv(
    FILE_PATH,
    usecols=USE_COLUMNS,
    chunksize=100000
):

    # Convert columns to appropriate data types
    chunk["Timestamp"] = pd.to_datetime(
        chunk["Timestamp"], errors="coerce"
    )

    numeric_columns = [
        "Hour of Day",
        "Average Road Speed",
        "Average Travel Time",
        "Road Distance",
        "Bus Trip Count"
    ]

    for column in numeric_columns:
        chunk[column] = pd.to_numeric(
            chunk[column], errors="coerce"
        )

    # Filter by date, route, and peak hours
    chunk = chunk[
        (chunk["Timestamp"] >= START_DATE) &
        (chunk["Timestamp"] <= END_DATE) &
        (chunk["Route ID"].isin(ROUTES)) &
        (chunk["Hour of Day"].isin(PEAK_HOURS))
    ].copy()

    # Remove invalid values
    chunk = chunk.dropna(
        subset=[
            "Timepoint Stop Name",
            "Next Timepoint Stop Name",
            "Average Road Speed",
            "Bus Trip Count"
        ]
    )

    # Keep only positive trip counts
    chunk = chunk[chunk["Bus Trip Count"] > 0]

    if chunk.empty:
        continue

    # Calculate weighted speed
    chunk["Weighted Speed"] = (
        chunk["Average Road Speed"] * chunk["Bus Trip Count"]
    )

    # Group by route, segment, and hour
    grouped = chunk.groupby(
        [
            "Route ID",
            "Timepoint Stop Name",
            "Next Timepoint Stop Name",
            "Hour of Day"
        ]
    ).agg(
        average_speed=("Average Road Speed", "mean"),
        weighted_speed_sum=("Weighted Speed", "sum"),
        total_trip_count=("Bus Trip Count", "sum"),
        average_travel_time=("Average Travel Time", "mean"),
        average_road_distance=("Road Distance", "mean"),
        records=("Average Road Speed", "count")
    ).reset_index()

    all_data.append(grouped)

# Combine chunk results
if not all_data:
    print("No matching records found.")
    raise SystemExit

results = pd.concat(all_data, ignore_index=True)

# Combine groups across chunks
final_results = results.groupby(
    [
        "Route ID",
        "Timepoint Stop Name",
        "Next Timepoint Stop Name",
        "Hour of Day"
    ]
).agg(
    average_speed_sum=("average_speed", "sum"),
    weighted_speed_sum=("weighted_speed_sum", "sum"),
    total_trip_count=("total_trip_count", "sum"),
    average_travel_time=("average_travel_time", "mean"),
    average_road_distance=("average_road_distance", "mean"),
    records=("records", "sum")
).reset_index()

# Calculate final averages
final_results["Average Speed (mph)"] = (
    final_results["average_speed_sum"] /
    final_results["records"]
)

final_results["Weighted Average Speed (mph)"] = (
    final_results["weighted_speed_sum"] /
    final_results["total_trip_count"]
)

# Rename columns
final_results = final_results.rename(columns={
    "Route ID": "Route",
    "Timepoint Stop Name": "From Stop",
    "Next Timepoint Stop Name": "To Stop",
    "Hour of Day": "Hour",
    "average_travel_time": "Average Travel Time",
    "average_road_distance": "Average Road Distance",
    "total_trip_count": "Total Trip Count",
    "records": "Records"
})

# Remove temporary columns
final_results = final_results.drop(
    columns=["average_speed_sum", "weighted_speed_sum"]
)

# Sort by weighted average speed
final_results = final_results.sort_values(
    by="Weighted Average Speed (mph)"
)

# Save output
output_path = "data/slow_segments_analysis.csv"

final_results.to_csv(output_path, index=False)

# Display slowest segments for each route
for route in ROUTES:
    route_data = final_results[
        final_results["Route"] == route
    ].sort_values(
        by="Weighted Average Speed (mph)"
    )

    print(f"\n{route} - SLOWEST SEGMENTS:")

    print(
        route_data[
            [
                "From Stop",
                "To Stop",
                "Hour",
                "Average Speed (mph)",
                "Weighted Average Speed (mph)",
                "Total Trip Count",
                "Records"
            ]
        ].head(10).to_string(index=False)
    )

print(f"\nAnalysis saved to: {output_path}")
