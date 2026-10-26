"""
Milestone 2: Exploratory Data Analysis — Steps 1, 3, 4, and 5
- Step 1: Define 'typical' day filter (weekdays, Saturdays, Sundays; exclude holidays, storm days, outliers)
- Step 3: Network patterns (daily time series with switchover lines and shading, hourly profiles with IQR bands, monthly weekday ridership, top 10 network hours)
- Step 4: Route patterns (heatmaps of ridership and riders per trip blanking < 2 trips/hr, comprehensive route performance table using total/total ratios)
- Step 5: Demand stability (CV = std / mean per route and hour across typical weekdays)
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
MATCHED_PATH = ROOT / "data" / "processed" / "matched_hourly.parquet"
RIDERSHIP_CLEAN_PATH = ROOT / "data" / "processed" / "ridership_hourly_clean.parquet"
FIG_DIR = ROOT / "reports" / "figures"
TAB_DIR = ROOT / "reports" / "tables"

FIG_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)

# Set high-quality styling
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica"],
    "axes.edgecolor": "#cccccc",
    "axes.linewidth": 0.8,
    "grid.color": "#e5e7eb",
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
})


def load_data():
    print("Loading matched hourly dataset...")
    df = pd.read_parquet(MATCHED_PATH)
    return df


def define_typical_filter(df: pd.DataFrame):
    """
    Step 1: Define which days count as 'typical'.
    Typical weekday: not a public holiday, no holiday schedule, not a storm day, not an outlier hour.
    Typical Saturday and Sunday: same rules.
    """
    typical_mask = (
        (~df["is_public_holiday"])
        & (~df["holiday_schedule"])
        & (~df["is_storm"])
        & (~df["is_outlier"])
    )
    
    df["day_category"] = "Special/Excluded"
    df.loc[typical_mask & (~df["is_weekend"]), "day_category"] = "Typical Weekday"
    df.loc[typical_mask & (df["day_of_week"] == "Saturday"), "day_category"] = "Typical Saturday"
    df.loc[typical_mask & (df["day_of_week"] == "Sunday"), "day_category"] = "Typical Sunday"
    
    return df


def step_3_network_patterns(df: pd.DataFrame):
    print("\n--- Step 3: Network Patterns ---")

    # 1. Daily ridership across the whole window
    # Read clean ridership to include all dates (even blackout/excluded ones for full network context)
    r_clean = pd.read_parquet(RIDERSHIP_CLEAN_PATH)
    r_clean["date"] = r_clean["date"].astype(str)
    daily_all = r_clean.groupby("date")["ridership"].sum().reset_index()
    daily_all = daily_all[(daily_all["date"] >= "2026-01-04") & (daily_all["date"] <= "2026-09-30")].copy()
    daily_all["dt"] = pd.to_datetime(daily_all["date"])
    daily_all = daily_all.sort_values("dt")

    fig, ax = plt.subplots(figsize=(14, 5.5), dpi=300)
    ax.plot(daily_all["dt"], daily_all["ridership"] / 1000.0, color="#1e3a8a", linewidth=1.5, label="Daily Total Riders (k)")

    # Timetable version switchover vertical lines
    # Version switchovers: 2026-03-27, 2026-04-12, 2026-06-28, 2026-09-06
    switchovers = [
        ("2026-03-27", "27 Mar: Winter Download Pick"),
        ("2026-04-12", "12 Apr: Spring Pick"),
        ("2026-06-28", "28 Jun: Summer Pick"),
        ("2026-09-06", "6 Sep: Fall Pick"),
    ]
    for d_str, label in switchovers:
        dt = pd.to_datetime(d_str)
        ax.axvline(dt, color="#dc2626", linestyle=":", linewidth=1.4, alpha=0.85)
        ax.text(dt + pd.Timedelta(days=1), 880, label, rotation=90, fontsize=8, color="#991b1b", verticalalignment="top")

    # Shading for excluded blackout days (10-15 Jan)
    ax.axvspan(pd.to_datetime("2026-01-10"), pd.to_datetime("2026-01-16"), color="#9ca3af", alpha=0.35, label="Excluded Blackout (10-15 Jan)")

    # Shading for storm days
    storm_ranges = [
        (pd.to_datetime("2026-01-25"), pd.to_datetime("2026-01-27")),
        (pd.to_datetime("2026-02-22"), pd.to_datetime("2026-02-25")),
    ]
    for s_start, s_end in storm_ranges:
        ax.axvspan(s_start, s_end, color="#38bdf8", alpha=0.3, label="Storm Disruption" if s_start == storm_ranges[0][0] else None)

    # Shading for holidays
    holidays = [
        pd.to_datetime("2026-01-19"),
        pd.to_datetime("2026-02-16"),
        pd.to_datetime("2026-05-25"),
        pd.to_datetime("2026-06-19"),
        pd.to_datetime("2026-07-03"),
        pd.to_datetime("2026-07-04"),
        pd.to_datetime("2026-09-07"),
    ]
    for h in holidays:
        ax.axvspan(h - pd.Timedelta(hours=12), h + pd.Timedelta(hours=12), color="#f59e0b", alpha=0.25, label="Public Holiday" if h == holidays[0] else None)

    ax.set_title("Network-Wide Daily Bus Ridership (Manhattan Routes, Jan–Sep 2026)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Daily Boardings (Thousands)", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(True, alpha=0.4)
    ax.set_ylim(0, 950)
    ax.legend(loc="lower left", frameon=True, fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    daily_fig_path = FIG_DIR / "m2_network_daily_ridership.png"
    plt.savefig(daily_fig_path, dpi=300)
    plt.close()
    print(f"Saved: {daily_fig_path.relative_to(ROOT)}")

    # 2. Average riders by hour for typical weekdays, Saturdays, and Sundays with middle 50% band (IQR)
    typical_df = df[df["day_category"].isin(["Typical Weekday", "Typical Saturday", "Typical Sunday"])].copy()
    
    # Calculate network hourly ridership for every date and hour
    net_hourly_date = typical_df.groupby(["day_category", "date", "hour"])["ridership"].sum().reset_index()

    # Aggregate by day_category and hour: mean, Q1 (25%), Q3 (75%), median
    hourly_stats = net_hourly_date.groupby(["day_category", "hour"])["ridership"].agg(
        mean="mean",
        q25=lambda s: np.percentile(s, 25),
        q75=lambda s: np.percentile(s, 75),
        median="median"
    ).reset_index()

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    colors = {
        "Typical Weekday": ("#1d4ed8", "#93c5fd"),
        "Typical Saturday": ("#ea580c", "#fed7aa"),
        "Typical Sunday": ("#16a34a", "#bbf7d0"),
    }

    for cat in ["Typical Weekday", "Typical Saturday", "Typical Sunday"]:
        sub = hourly_stats[hourly_stats["day_category"] == cat].sort_values("hour")
        main_col, band_col = colors[cat]
        ax.plot(sub["hour"], sub["mean"], color=main_col, linewidth=2.2, label=f"{cat} (Mean)")
        ax.fill_between(sub["hour"], sub["q25"], sub["q75"], color=band_col, alpha=0.45, label=f"{cat} Middle 50% (IQR)")

    ax.set_title("Network Hourly Demand Profile by Typical Day Type (Middle 50% IQR Band)", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Hour of Day (0–23)", fontsize=10)
    ax.set_ylabel("Network Boardings per Hour", fontsize=10)
    ax.set_xticks(range(0, 24))
    ax.set_xlim(0, 23)
    ax.grid(True, alpha=0.4)
    ax.legend(loc="upper left", frameon=True, fontsize=8.5, framealpha=0.9, ncol=2)

    plt.tight_layout()
    hourly_fig_path = FIG_DIR / "m2_network_hourly_profiles.png"
    plt.savefig(hourly_fig_path, dpi=300)
    plt.close()
    print(f"Saved: {hourly_fig_path.relative_to(ROOT)}")

    # 3. Weekday riders by month (summer change)
    wd_df = df[df["day_category"] == "Typical Weekday"].copy()
    daily_wd = wd_df.groupby(["month", "date"])["ridership"].sum().reset_index()
    monthly_wd = daily_wd.groupby("month")["ridership"].agg(
        mean_daily="mean",
        median_daily="median",
        std_daily="std",
        typical_days="count"
    ).reset_index()

    month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep"}
    monthly_wd["month_name"] = monthly_wd["month"].map(month_names)

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=300)
    bars = ax.bar(monthly_wd["month_name"], monthly_wd["mean_daily"] / 1000.0, color="#3b82f6", width=0.6, edgecolor="#1d4ed8", linewidth=0.8)

    # Highlight summer months (July & August)
    bars[6].set_facecolor("#f97316")
    bars[6].set_edgecolor("#c2410c")
    bars[7].set_facecolor("#f97316")
    bars[7].set_edgecolor("#c2410c")

    # Add value annotations on bars
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, h + 8, f"{h:.1f}k", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    ax.set_title("Average Typical Weekday Boardings by Month (Jan–Sep 2026)", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Average Daily Boardings (Thousands)", fontsize=10)
    ax.set_xlabel("Month (Orange = Summer Vacation Period)", fontsize=10)
    ax.set_ylim(0, 850)
    ax.grid(axis="y", alpha=0.4)

    plt.tight_layout()
    monthly_fig_path = FIG_DIR / "m2_network_monthly_ridership.png"
    plt.savefig(monthly_fig_path, dpi=300)
    plt.close()
    print(f"Saved: {monthly_fig_path.relative_to(ROOT)}")

    # 4. The 10 busiest network hours on typical weekdays
    # (A) Top 10 specific date-hour instances
    net_instances = wd_df.groupby(["date", "hour"])["ridership"].sum().reset_index()
    top10_instances = net_instances.sort_values("ridership", ascending=False).head(10).reset_index(drop=True)
    top10_instances.index += 1
    top10_instances["ridership_formatted"] = top10_instances["ridership"].apply(lambda x: f"{x:,}")
    top10_instances.to_csv(TAB_DIR / "m2_top_10_network_hours_instances.csv", index=True, index_label="rank")

    # (B) Busiest clock hours on typical weekdays on average
    net_clock_hours = wd_df.groupby("hour")["ridership"].sum() / len(wd_df["date"].unique())
    net_clock_hours = net_clock_hours.reset_index().rename(columns={"ridership": "avg_hourly_riders"})
    top10_clock = net_clock_hours.sort_values("avg_hourly_riders", ascending=False).head(10).reset_index(drop=True)
    top10_clock.index += 1
    top10_clock["avg_riders_formatted"] = top10_clock["avg_hourly_riders"].round(1).apply(lambda x: f"{x:,.1f}")
    top10_clock.to_csv(TAB_DIR / "m2_top_10_busiest_clock_hours.csv", index=True, index_label="rank")

    print("Top 10 Busiest Clock Hours on Typical Weekdays:")
    print(top10_clock[["hour", "avg_riders_formatted"]])


def step_4_route_patterns(df: pd.DataFrame):
    print("\n--- Step 4: Route Patterns ---")
    
    # Order routes by total weekday ridership
    wd_df = df[df["day_category"] == "Typical Weekday"]
    route_totals = wd_df.groupby("route")["ridership"].sum().sort_values(ascending=False)
    route_order = route_totals.index.tolist()

    # 1. Heatmaps of riders: routes (rows) by hour (columns) for Weekday, Saturday, Sunday
    day_types = ["Typical Weekday", "Typical Saturday", "Typical Sunday"]
    file_suffixes = ["weekday", "saturday", "sunday"]

    for d_type, suffix in zip(day_types, file_suffixes):
        sub = df[df["day_category"] == d_type]
        # Pivot table: routes x hours, mean ridership
        # Divide total riders by total days of that day type for each route-hour
        num_days = len(sub["date"].unique())
        pivot_sum = sub.pivot_table(index="route", columns="hour", values="ridership", aggfunc="sum").fillna(0)
        pivot_mean = pivot_sum / num_days
        pivot_mean = pivot_mean.reindex(index=route_order, fill_value=0)

        plt.figure(figsize=(12, 10), dpi=300)
        sns.heatmap(pivot_mean, cmap="YlGnBu", annot=False, cbar_kws={"label": "Average Hourly Boardings"})
        plt.title(f"Average Route Ridership by Hour: {d_type} (Routes Sorted by Total Weekday Demand)", fontsize=12, fontweight="bold", pad=10)
        plt.xlabel("Clock Hour (0–23)", fontsize=10)
        plt.ylabel("Route", fontsize=10)
        plt.tight_layout()
        out_p = FIG_DIR / f"m2_heatmap_riders_{suffix}.png"
        plt.savefig(out_p, dpi=300)
        plt.close()
        print(f"Saved: {out_p.relative_to(ROOT)}")

    # 2. Heatmaps of riders per trip: routes x hours, blanking cells with < 2 trips running on average
    for d_type, suffix in zip(day_types, file_suffixes):
        sub = df[df["day_category"] == d_type]
        num_days = len(sub["date"].unique())
        
        # Calculate totals across the period
        sum_riders = sub.pivot_table(index="route", columns="hour", values="ridership", aggfunc="sum").fillna(0)
        sum_trips = sub.pivot_table(index="route", columns="hour", values="trips_running", aggfunc="sum").fillna(0)
        
        avg_trips = sum_trips / num_days
        # Divide totals by totals: sum_riders / sum_trips
        with np.errstate(divide="ignore", invalid="ignore"):
            rpt_grid = np.where(sum_trips > 0, sum_riders / sum_trips, np.nan)
        
        # Blank out cells with fewer than 2 trips running on average (< 2.0)
        rpt_grid_filtered = np.where(avg_trips >= 2.0, rpt_grid, np.nan)
        rpt_df = pd.DataFrame(rpt_grid_filtered, index=sum_riders.index, columns=sum_riders.columns)
        rpt_df = rpt_df.reindex(index=route_order)

        plt.figure(figsize=(12, 10), dpi=300)
        sns.heatmap(rpt_df, cmap="magma", annot=False, cbar_kws={"label": "Riders per Trip (Totals ÷ Totals)"}, vmin=0, vmax=60)
        plt.title(f"Riders per Trip by Hour: {d_type} (Blanked where Avg Trips < 2/hr)", fontsize=12, fontweight="bold", pad=10)
        plt.xlabel("Clock Hour (0–23)", fontsize=10)
        plt.ylabel("Route", fontsize=10)
        plt.tight_layout()
        out_p = FIG_DIR / f"m2_heatmap_rpt_{suffix}.png"
        plt.savefig(out_p, dpi=300)
        plt.close()
        print(f"Saved: {out_p.relative_to(ROOT)}")

    # 3. Route Table: for each route and day type, riders per trip and riders per service-hour
    # for morning peak, midday, evening peak, night, with the number of days behind each figure.
    # Total riders / total trips and total riders / total service-hours (divide totals by totals).
    records = []
    bands = ["morning_peak", "midday", "evening_peak", "night"]

    for d_type in day_types:
        sub = df[df["day_category"] == d_type]
        num_days = len(sub["date"].unique())
        for r in sorted(df["route"].unique()):
            r_sub = sub[sub["route"] == r]
            for b in bands:
                b_sub = r_sub[r_sub["time_band"] == b]
                tot_riders = b_sub["ridership"].sum()
                tot_trips = b_sub["trips_running"].sum()
                tot_service_hours = b_sub["service_hours"].sum()
                days_present = len(b_sub["date"].unique())
                
                rpt = (tot_riders / tot_trips) if tot_trips > 0 else np.nan
                rpsh = (tot_riders / tot_service_hours) if tot_service_hours > 0 else np.nan

                records.append({
                    "route": r,
                    "day_type": d_type,
                    "time_band": b,
                    "days_count": days_present,
                    "total_riders": int(tot_riders),
                    "total_trips": int(tot_trips),
                    "total_service_hours": round(float(tot_service_hours), 2),
                    "riders_per_trip": round(float(rpt), 2) if not np.isnan(rpt) else np.nan,
                    "riders_per_service_hour": round(float(rpsh), 2) if not np.isnan(rpsh) else np.nan,
                })

    route_perf_df = pd.DataFrame(records)
    route_perf_csv = TAB_DIR / "m2_route_performance_table.csv"
    route_perf_df.to_csv(route_perf_csv, index=False)
    print(f"Saved: {route_perf_csv.relative_to(ROOT)} ({len(route_perf_df)} rows)")


def step_5_demand_stability(df: pd.DataFrame):
    print("\n--- Step 5: Demand Stability (Coefficient of Variation) ---")
    # For each route and hour, measure how much riders vary from one typical weekday to the next:
    # CV = std / mean
    wd_df = df[df["day_category"] == "Typical Weekday"].copy()
    
    cv_records = []
    routes = sorted(df["route"].unique())
    for r in routes:
        r_sub = wd_df[wd_df["route"] == r]
        for h in range(24):
            h_sub = r_sub[r_sub["hour"] == h]["ridership"]
            m = h_sub.mean()
            s = h_sub.std()
            cv = (s / m) if (m > 0 and len(h_sub) > 1) else np.nan
            cv_records.append({
                "route": r,
                "hour": h,
                "mean_riders": round(m, 2),
                "std_riders": round(s, 2),
                "cv": round(cv, 4) if not np.isnan(cv) else np.nan,
                "sample_days": len(h_sub),
            })
    
    cv_df = pd.DataFrame(cv_records)
    cv_csv = TAB_DIR / "m2_route_demand_variability.csv"
    cv_df.to_csv(cv_csv, index=False)
    print(f"Saved: {cv_csv.relative_to(ROOT)} ({len(cv_df)} rows)")

    # Create pivot heatmap of CV
    cv_pivot = cv_df.pivot(index="route", columns="hour", values="cv")
    # Sort routes by overall average CV across daytime hours (06:00 to 22:00)
    daytime_cv = cv_df[cv_df["hour"].between(6, 22)].groupby("route")["cv"].mean()
    sorted_by_cv = daytime_cv.sort_values(ascending=False).index.tolist()
    cv_pivot = cv_pivot.reindex(index=sorted_by_cv)

    plt.figure(figsize=(12, 10), dpi=300)
    sns.heatmap(cv_pivot, cmap="viridis_r", annot=False, cbar_kws={"label": "Coefficient of Variation (CV = std / mean)"}, vmin=0.1, vmax=0.7)
    plt.title("Route Demand Variability by Hour (Typical Weekdays)\nHigher CV = Less Predictable / More Volatile Demand", fontsize=12, fontweight="bold", pad=10)
    plt.xlabel("Clock Hour (0–23)", fontsize=10)
    plt.ylabel("Route (Sorted by Daytime Volatility)", fontsize=10)
    plt.tight_layout()
    cv_fig_path = FIG_DIR / "m2_demand_variability.png"
    plt.savefig(cv_fig_path, dpi=300)
    plt.close()
    print(f"Saved: {cv_fig_path.relative_to(ROOT)}")


def main():
    df = load_data()
    df = define_typical_filter(df)
    step_3_network_patterns(df)
    step_4_route_patterns(df)
    step_5_demand_stability(df)
    print("\nEDA Patterns analysis completed successfully!")


if __name__ == "__main__":
    main()
