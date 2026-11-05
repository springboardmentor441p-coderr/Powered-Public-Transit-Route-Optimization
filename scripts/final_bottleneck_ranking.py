
import pandas as pd

INPUT_FILE = "data/reliable_slow_segments.csv"
OUTPUT_FILE = "data/final_bottleneck_ranking.csv"

print("Creating final bus bottleneck ranking...")

# Load reliable segment results
df = pd.read_csv(INPUT_FILE)

# Calculate weighted speed contribution for each hour
df["Weighted Speed Sum"] = (
    df["Weighted Average Speed (mph)"] *
    df["Total Trip Count"]
)

# Combine the afternoon hours for each route segment
ranking = df.groupby(
    ["Route", "From Stop", "To Stop"]
).agg(
    Weighted_Speed_Sum=("Weighted Speed Sum", "sum"),
    Total_Trip_Count=("Total Trip Count", "sum"),
    Total_Records=("Records", "sum"),
    Hours_Analyzed=("Hour", "nunique")
).reset_index()

# Calculate combined weighted average speed
ranking["Overall Weighted Average Speed (mph)"] = (
    ranking["Weighted_Speed_Sum"] /
    ranking["Total_Trip_Count"]
)

# Keep segments represented in all three afternoon hours
ranking = ranking[ranking["Hours_Analyzed"] == 3].copy()

# Sort slowest to fastest
ranking = ranking.sort_values(
    by="Overall Weighted Average Speed (mph)"
)

# Assign priority ranking
ranking.insert(
    0,
    "Priority",
    range(1, len(ranking) + 1)
)

# Remove temporary calculation column
ranking = ranking.drop(columns=["Weighted_Speed_Sum"])

# Save final ranking
ranking.to_csv(OUTPUT_FILE, index=False)

# Display final results
print("\nFINAL BUS BOTTLENECK RANKING\n")

print(ranking.to_string(index=False))

print(f"\nFinal ranking saved to: {OUTPUT_FILE}")
