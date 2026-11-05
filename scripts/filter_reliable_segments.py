
import pandas as pd

# Input and output files
INPUT_FILE = "data/slow_segments_analysis.csv"
OUTPUT_FILE = "data/reliable_slow_segments.csv"

# Minimum number of speed records required
MIN_RECORDS = 50

# Load weighted segment analysis
df = pd.read_csv(INPUT_FILE)

# Keep segments with sufficient records
reliable = df[df["Records"] >= MIN_RECORDS].copy()

# Sort by weighted average speed
reliable = reliable.sort_values(
    by="Weighted Average Speed (mph)"
)

# Save reliable results
reliable.to_csv(OUTPUT_FILE, index=False)

# Display results
print("\nRELIABLE SLOW BUS SEGMENTS")
print(f"Minimum records required: {MIN_RECORDS}")

for route in ["M15", "Q58", "M101", "B6"]:
    route_data = reliable[reliable["Route"] == route]

    print(f"\n{route}:")

    print(
        route_data[
            [
                "From Stop",
                "To Stop",
                "Hour",
                "Weighted Average Speed (mph)",
                "Total Trip Count",
                "Records"
            ]
        ].to_string(index=False)
    )

print(f"\nResults saved to: {OUTPUT_FILE}")
