
import os
import pandas as pd
import matplotlib.pyplot as plt

# File paths
RANKING_FILE = "data/final_bottleneck_ranking.csv"
RELIABLE_FILE = "data/reliable_slow_segments.csv"
OUTPUT_FOLDER = "charts"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

print("Creating project visualizations...")

# Load analysis results
ranking = pd.read_csv(RANKING_FILE)
reliable = pd.read_csv(RELIABLE_FILE)

# -------------------------------------------------
# CHART 1: TOP BOTTLENECK SEGMENTS
# -------------------------------------------------

top_segments = ranking.head(9).copy()

top_segments["Segment"] = (
    top_segments["Route"] + " | " +
    top_segments["From Stop"] + " to " +
    top_segments["To Stop"]
)

top_segments = top_segments.sort_values(
    "Overall Weighted Average Speed (mph)",
    ascending=True
)

plt.figure(figsize=(13, 8))

plt.barh(
    top_segments["Segment"],
    top_segments["Overall Weighted Average Speed (mph)"]
)

plt.xlabel("Weighted Average Speed (mph)")
plt.ylabel("Bus Route and Segment")
plt.title("Top 9 Slowest NYC Bus Bottleneck Segments")
plt.tight_layout()

plt.savefig(
    os.path.join(OUTPUT_FOLDER, "top_bottleneck_segments.png"),
    dpi=300
)
plt.close()

# -------------------------------------------------
# CHART 2: ROUTE-WISE BOTTLENECK SPEED COMPARISON
# -------------------------------------------------

route_comparison = (
    ranking.groupby("Route")[
        "Overall Weighted Average Speed (mph)"
    ]
    .min()
    .sort_values()
)

plt.figure(figsize=(9, 6))

plt.bar(
    route_comparison.index,
    route_comparison.values
)

plt.xlabel("Bus Route")
plt.ylabel("Weighted Average Speed (mph)")
plt.title("Slowest Bottleneck Speed by Bus Route")
plt.tight_layout()

plt.savefig(
    os.path.join(OUTPUT_FOLDER, "route_speed_comparison.png"),
    dpi=300
)
plt.close()

# -------------------------------------------------
# CHART 3: HOURLY SPEED COMPARISON
# -------------------------------------------------

# Select the slowest segment for each route
main_bottlenecks = ranking.loc[
    ranking.groupby("Route")[
        "Overall Weighted Average Speed (mph)"
    ].idxmin()
]

plt.figure(figsize=(10, 6))

for _, segment in main_bottlenecks.iterrows():

    route = segment["Route"]

    hourly = reliable[
        (reliable["Route"] == route) &
        (reliable["From Stop"] == segment["From Stop"]) &
        (reliable["To Stop"] == segment["To Stop"])
    ].copy()

    hourly = hourly.sort_values("Hour")

    plt.plot(
        hourly["Hour"],
        hourly["Weighted Average Speed (mph)"],
        marker="o",
        label=route
    )

plt.xticks([15, 16, 17], ["3 PM", "4 PM", "5 PM"])
plt.xlabel("Afternoon Peak Hour")
plt.ylabel("Weighted Average Speed (mph)")
plt.title("Hourly Speed Changes at Main Bottleneck Segments")
plt.legend(title="Bus Route")
plt.grid(True)
plt.tight_layout()

plt.savefig(
    os.path.join(OUTPUT_FOLDER, "hourly_speed_comparison.png"),
    dpi=300
)
plt.close()

# -------------------------------------------------
# CHART 4: PASSENGER DEMAND VS BUS SPEED
# -------------------------------------------------

# Cumulative passenger totals and route average speeds
# Common period: Jan 1, 2025 to Sep 1, 2026
comparison_data = {
    "M15+": {
        7: (1024075, 8.26),
        8: (1204938, 8.15),
        15: (829327, 8.04),
        16: (901080, 8.07),
        17: (1005466, 8.23)
    },
    "M15": {
        7: (383494, 6.55),
        8: (492528, 5.83),
        15: (541182, 5.05),
        16: (538334, 5.17),
        17: (575955, 5.31)
    },
    "B6": {
        7: (714893, 8.16),
        8: (707172, 7.92),
        15: (559820, 7.12),
        16: (582879, 7.12),
        17: (621840, 7.18)
    },
    "Q58": {
        7: (732009, 7.09),
        8: (628402, 7.29),
        15: (556234, 6.09),
        16: (613356, 6.12),
        17: (606261, 6.16)
    },
    "Q44+": {
        7: (680459, 8.51),
        8: (662349, 8.24),
        15: (521865, 7.70),
        16: (549652, 7.58),
        17: (534231, 7.83)
    },
    "BX12+": {
        7: (675218, 14.07),
        8: (657176, 14.42),
        15: (555966, 11.78),
        16: (560323, 11.29),
        17: (488881, 11.07)
    },
    "Q27": {
        7: (525087, 10.02),
        8: (508745, 9.55),
        15: (429841, 8.99),
        16: (455646, 8.93),
        17: (481003, 8.80)
    },
    "M101": {
        7: (447099, 7.28),
        8: (546047, 7.45),
        15: (495840, 6.37),
        16: (503780, 6.43),
        17: (531528, 7.00)
    }
}

plt.figure(figsize=(11, 7))

for route, hours in comparison_data.items():

    passengers = [values[0] for values in hours.values()]
    speeds = [values[1] for values in hours.values()]

    plt.scatter(
        passengers,
        speeds,
        label=route
    )

plt.xlabel("Cumulative Passenger Demand")
plt.ylabel("Average Bus Speed (mph)")
plt.title("Passenger Demand vs Average Bus Speed")
plt.legend(title="Bus Route")
plt.grid(True)
plt.tight_layout()

plt.savefig(
    os.path.join(OUTPUT_FOLDER, "passenger_demand_vs_speed.png"),
    dpi=300
)
plt.close()

print("\nALL FOUR CHARTS CREATED SUCCESSFULLY!")

print("\nSaved charts:")
for filename in os.listdir(OUTPUT_FOLDER):
    print(os.path.join(OUTPUT_FOLDER, filename))
