"""
Plot hourly total ridership for Saturday 28 March 2026.
Highlights the 01:00 to 04:59 collection outage alongside a baseline normal Saturday.
Saves figure to reports/figures/mar28_hourly_ridership.png.
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RIDERSHIP_PATH = ROOT / "data" / "processed" / "ridership_hourly_clean.parquet"
OUT_FIG = ROOT / "reports" / "figures" / "mar28_hourly_ridership.png"


def plot_mar28_hourly():
    df = pd.read_parquet(RIDERSHIP_PATH)
    df["date"] = df["date"].astype(str)

    # 28 March and baseline Saturday (21 March)
    mar28 = df[df["date"] == "2026-03-28"].groupby("hour")["ridership"].sum()
    mar21 = df[df["date"] == "2026-03-21"].groupby("hour")["ridership"].sum()

    hours = list(range(24))
    r_mar28 = [mar28.get(h, 0) for h in hours]
    r_mar21 = [mar21.get(h, 0) for h in hours]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    # Plot baseline Saturday in dashed grey
    ax.plot(
        hours,
        r_mar21,
        color="#94a3b8",
        linestyle="--",
        linewidth=1.8,
        label="Typical Saturday (21 Mar)",
    )

    # Plot 28 March
    ax.plot(
        hours,
        r_mar28,
        color="#2563eb",
        linewidth=2.2,
        marker="o",
        markersize=4,
        label="Saturday 28 March 2026",
    )

    # Highlight outage window (hours 1 to 4)
    ax.axvspan(
        0.5,
        4.5,
        color="#ef4444",
        alpha=0.15,
        label="Outage Window (01:00 - 04:59)",
    )

    # Annotation
    ax.annotate(
        "Data collection outage\n(Total: 63 riders across 4 hrs\nvs ~1,480 typical)",
        xy=(2.5, 20),
        xytext=(3.5, 4500),
        arrowprops=dict(facecolor="#dc2626", shrink=0.08, width=1.5, headwidth=6),
        fontsize=9,
        fontweight="bold",
        color="#dc2626",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fee2e2", edgecolor="#dc2626", alpha=0.9),
    )

    ax.set_title(
        "Hourly Bus Ridership on Saturday 28 March 2026 (Manhattan Network)",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Hour of Day (00:00 to 23:00)", fontsize=10, fontweight="bold")
    ax.set_ylabel("Total Recorded Riders", fontsize=10, fontweight="bold")
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], rotation=45, ha="right", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1")
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT_FIG)
    plt.close()
    print(f"Saved 28 March hourly ridership plot -> {OUT_FIG.relative_to(ROOT)}")


if __name__ == "__main__":
    plot_mar28_hourly()
