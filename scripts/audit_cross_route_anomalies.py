
import pandas as pd

INPUT_FILE = "data/hourly_ridership_training.csv"
OUTPUT_FILE = "data/cross_route_anomaly_audit.csv"

ANOMALY_TIMESTAMP = "2026-08-16T21:00:00.000"

EXPECTED_ROUTES = [
    "B6", "BX12+", "M101", "M15",
    "M15+", "Q27", "Q44+", "Q58"
]

df = pd.read_csv(INPUT_FILE)

# Select all records at the suspicious timestamp.
anomaly = df[df["timestamp"] == ANOMALY_TIMESTAMP].copy()

# Add audit information without changing the original data.
anomaly["anomaly_reason"] = (
    "Simultaneous near-zero passenger counts across all eight "
    "routes at the same timestamp; cause unverified."
)

anomaly["review_status"] = "Flagged for investigation"
anomaly["automatically_removed"] = False

# Check whether all expected routes are present.
found_routes = set(anomaly["bus_route"])
missing_routes = set(EXPECTED_ROUTES) - found_routes

anomaly.to_csv(OUTPUT_FILE, index=False)

print("CROSS-ROUTE ANOMALY AUDIT")
print("------------------------")
print("Timestamp:", ANOMALY_TIMESTAMP)
print("Records flagged:", len(anomaly))
print("Routes found:", len(found_routes))
print("Missing routes:", sorted(missing_routes))
print("Combined passengers:", anomaly["total_passengers"].sum())
print("Original data modified: No")
print("Records automatically removed: No")
print("Audit saved to:", OUTPUT_FILE)

print("\nFlagged records:")
print(anomaly[["timestamp", "bus_route", "total_passengers"]].to_string(index=False))
