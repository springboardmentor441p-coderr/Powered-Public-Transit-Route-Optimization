"""
RouteRanker: Phase 3 Exploratory Data Analysis & Visualization Suite
Generates publication-quality charts and graphs from cleaned CTA datasets.
Saves all figures to outputs/eda/.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Set visual style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#CBD5E1'
plt.rcParams['axes.linewidth'] = 0.8

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
EDA_DIR = os.path.join(BASE_DIR, "outputs", "eda")
os.makedirs(EDA_DIR, exist_ok=True)

# Theme palette matching UI design specifications (Navy, Teal, Blue)
NAVY = "#0F172A"
BLUE = "#00A1DE"  # CTA Blue
TEAL = "#0D9488"
CORAL = "#E11D48"
GRAY = "#64748B"

def plot_system_daily_trend(df_sys):
    print("Generating Chart 1: System Daily Ridership Trends (2001-2026)...")
    fig, ax = plt.subplots(figsize=(14, 6), dpi=300)
    
    df_sys['service_date'] = pd.to_datetime(df_sys['date'])
    # Compute 30-day rolling averages for smooth visual trend
    df_sys = df_sys.sort_values('service_date')
    df_sys['total_roll30'] = df_sys['total_rides'].rolling(30, min_periods=7).mean()
    df_sys['bus_roll30'] = df_sys['bus'].rolling(30, min_periods=7).mean()
    df_sys['rail_roll30'] = df_sys['rail_boardings'].rolling(30, min_periods=7).mean()
    
    ax.plot(df_sys['service_date'], df_sys['total_roll30'] / 1e6, label='Total Transit (30-day MA)', color=NAVY, linewidth=2.2)
    ax.plot(df_sys['service_date'], df_sys['bus_roll30'] / 1e6, label='Bus Boardings (30-day MA)', color=BLUE, linewidth=1.6)
    ax.plot(df_sys['service_date'], df_sys['rail_roll30'] / 1e6, label='Rail Boardings (30-day MA)', color=TEAL, linewidth=1.6)
    
    # Highlight COVID-19 plunge
    ax.axvspan(pd.to_datetime('2020-03-01'), pd.to_datetime('2021-06-01'), color='#FEE2E2', alpha=0.5, label='COVID-19 Disruption Period')
    ax.text(pd.to_datetime('2020-04-01'), 1.6, 'COVID-19 Impact\n(-75% Ridership)', color=CORAL, fontsize=10, fontweight='bold')
    
    ax.set_title('Chicago Transit Authority (CTA): Daily System Ridership Trends (2001 - 2026)', fontsize=15, fontweight='bold', pad=15, color=NAVY)
    ax.set_xlabel('Service Date', fontsize=12, labelpad=10)
    ax.set_ylabel('Daily Passengers (Millions)', fontsize=12, labelpad=10)
    ax.set_ylim(0, 2.2)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9, loc='upper right')
    
    out_file = os.path.join(EDA_DIR, "01_system_daily_ridership_trend.png")
    plt.tight_layout()
    plt.savefig(out_file)
    plt.close()
    print(f"  Saved: {out_file}")

def plot_weekday_vs_weekend(df_sys):
    print("Generating Chart 2: Weekday vs Weekend Demand Distribution...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)
    
    order = ["Weekday", "Saturday", "Sunday/Holiday"]
    palette = [BLUE, TEAL, "#F59E0B"]
    
    # 1. Total Rides Box Plot
    sns.boxplot(data=df_sys, x='day_type_name', y=df_sys['total_rides'] / 1000, order=order, palette=palette, ax=ax1, width=0.45, fliersize=1)
    ax1.set_title('Passenger Demand by Day Type', fontsize=13, fontweight='bold', color=NAVY)
    ax1.set_xlabel('Day Type', fontsize=11)
    ax1.set_ylabel('Total Daily Boardings (Thousands)', fontsize=11)
    
    # 2. Average Bus vs Rail by Day of Week
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_avg = df_sys.groupby('day_of_week')[['bus', 'rail_boardings']].mean().reindex(dow_order) / 1000
    
    x = np.arange(len(dow_order))
    width = 0.35
    ax2.bar(x - width/2, dow_avg['bus'], width, label='Bus Boardings', color=BLUE)
    ax2.bar(x + width/2, dow_avg['rail_boardings'], width, label='Rail Boardings', color=TEAL)
    
    ax2.set_title('Average Daily Boardings by Day of Week', fontsize=13, fontweight='bold', color=NAVY)
    ax2.set_xlabel('Day of Week', fontsize=11)
    ax2.set_ylabel('Average Passengers (Thousands)', fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels([d[:3] for d in dow_order], fontsize=10)
    ax2.legend(frameon=True)
    
    plt.suptitle('Chicago CTA Passenger Demand: Weekday vs Weekend Analysis', fontsize=15, fontweight='bold', color=NAVY, y=1.02)
    plt.tight_layout()
    out_file = os.path.join(EDA_DIR, "02_weekday_vs_weekend_distribution.png")
    plt.savefig(out_file, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {out_file}")

def plot_monthly_seasonality(df_sys):
    print("Generating Chart 3: Monthly & Seasonal Ridership Patterns...")
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    
    # Exclude peak pandemic years (2020-2021) for representative seasonality baseline
    rep_df = df_sys[~df_sys['year'].isin([2020, 2021])].copy()
    
    monthly_stats = rep_df.groupby('month')[['bus', 'rail_boardings', 'total_rides']].mean() / 1000
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    ax.plot(month_names, monthly_stats['total_rides'], marker='o', color=NAVY, linewidth=2.5, label='Total Average Daily Rides')
    ax.plot(month_names, monthly_stats['bus'], marker='s', color=BLUE, linewidth=2, label='Bus Average Daily Rides')
    ax.plot(month_names, monthly_stats['rail_boardings'], marker='^', color=TEAL, linewidth=2, label='Rail Average Daily Rides')
    
    ax.set_title('CTA System Monthly Seasonality Profile (Representative Baseline)', fontsize=14, fontweight='bold', color=NAVY, pad=15)
    ax.set_xlabel('Month of Year', fontsize=12)
    ax.set_ylabel('Mean Daily Passengers (Thousands)', fontsize=12)
    ax.legend(frameon=True)
    
    # Annotate peak and trough
    peak_month = monthly_stats['total_rides'].idxmax()
    trough_month = monthly_stats['total_rides'].idxmin()
    ax.annotate(f"Peak Month: {month_names[peak_month-1]}", 
                xy=(peak_month-1, monthly_stats.loc[peak_month, 'total_rides']),
                xytext=(peak_month-1, monthly_stats.loc[peak_month, 'total_rides'] + 80),
                arrowprops=dict(facecolor=TEAL, shrink=0.05, width=1, headwidth=6),
                fontweight='bold', color=TEAL)
    
    ax.annotate(f"Winter Low: {month_names[trough_month-1]}", 
                xy=(trough_month-1, monthly_stats.loc[trough_month, 'total_rides']),
                xytext=(trough_month-1, monthly_stats.loc[trough_month, 'total_rides'] - 120),
                arrowprops=dict(facecolor=CORAL, shrink=0.05, width=1, headwidth=6),
                fontweight='bold', color=CORAL)
    
    plt.tight_layout()
    out_file = os.path.join(EDA_DIR, "03_monthly_seasonal_patterns.png")
    plt.savefig(out_file)
    plt.close()
    print(f"  Saved: {out_file}")

def plot_top_bus_routes(df_bus, df_routes):
    print("Generating Chart 4: Top High-Demand Bus Corridors...")
    fig, ax = plt.subplots(figsize=(12, 7), dpi=300)
    
    # Filter active routes
    active_bus = df_bus[df_bus['is_active_gtfs']].copy()
    route_perf = active_bus.groupby('route_id')['rides'].agg(['mean', 'max', 'count']).sort_values('mean', ascending=False).head(15)
    
    # Merge route names
    route_perf = route_perf.reset_index()
    names_map = dict(zip(df_routes['route_id'].astype(str), df_routes['route_long_name']))
    route_perf['route_desc'] = route_perf['route_id'].map(lambda r: f"Rt {r} - {names_map.get(str(r), '')[:22]}")
    
    y_pos = np.arange(len(route_perf))
    bars = ax.barh(y_pos, route_perf['mean'], align='center', color=BLUE, edgecolor='#0284C7', height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(route_perf['route_desc'], fontsize=10)
    ax.invert_yaxis()  # top route at the top
    
    # Add values on bars
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 200, bar.get_y() + bar.get_height()/2, f"{int(width):,} avg", 
                va='center', fontsize=9, color=NAVY, fontweight='medium')
        
    ax.set_title('Top 15 CTA Bus Routes by Mean Daily Ridership', fontsize=14, fontweight='bold', color=NAVY, pad=15)
    ax.set_xlabel('Average Daily Passenger Boardings', fontsize=11)
    ax.set_xlim(0, max(route_perf['mean']) * 1.18)
    
    plt.tight_layout()
    out_file = os.path.join(EDA_DIR, "04_top_bus_routes_demand.png")
    plt.savefig(out_file)
    plt.close()
    print(f"  Saved: {out_file}")

def plot_top_rail_stations(df_rail, df_station_dir):
    print("Generating Chart 5: Top Busiest CTA 'L' Rapid Transit Stations...")
    fig, ax = plt.subplots(figsize=(12, 7), dpi=300)
    
    station_perf = df_rail.groupby(['station_id', 'station_name'])['rides'].agg(['mean', 'max']).sort_values('mean', ascending=False).head(15).reset_index()
    
    y_pos = np.arange(len(station_perf))
    bars = ax.barh(y_pos, station_perf['mean'], align='center', color=TEAL, edgecolor='#0F766E', height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(station_perf['station_name'], fontsize=10)
    ax.invert_yaxis()
    
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 100, bar.get_y() + bar.get_height()/2, f"{int(width):,} avg", 
                va='center', fontsize=9, color=NAVY, fontweight='medium')
        
    ax.set_title("Top 15 Busiest CTA 'L' Stations by Average Daily Turnstile Entries", fontsize=14, fontweight='bold', color=NAVY, pad=15)
    ax.set_xlabel('Average Daily Station Entries', fontsize=11)
    ax.set_xlim(0, max(station_perf['mean']) * 1.18)
    
    plt.tight_layout()
    out_file = os.path.join(EDA_DIR, "05_top_rail_stations_demand.png")
    plt.savefig(out_file)
    plt.close()
    print(f"  Saved: {out_file}")

def plot_modal_split_evolution(df_sys):
    print("Generating Chart 6: Historical Bus vs Rail Modal Split...")
    fig, ax = plt.subplots(figsize=(12, 5), dpi=300)
    
    annual = df_sys.groupby('year')[['bus', 'rail_boardings', 'total_rides']].sum()
    annual['bus_pct'] = (annual['bus'] / annual['total_rides']) * 100
    annual['rail_pct'] = (annual['rail_boardings'] / annual['total_rides']) * 100
    
    years = annual.index
    ax.plot(years, annual['bus_pct'], marker='o', label='Bus Boarding Share (%)', color=BLUE, linewidth=2.2)
    ax.plot(years, annual['rail_pct'], marker='s', label='Rail Boarding Share (%)', color=TEAL, linewidth=2.2)
    
    ax.axhline(50, color='#94A3B8', linestyle='--', alpha=0.7)
    ax.set_title('CTA Modal Split Evolution: Bus vs Rail Ridership Share (2001 - 2026)', fontsize=14, fontweight='bold', color=NAVY, pad=15)
    ax.set_xlabel('Year', fontsize=11)
    ax.set_ylabel('Percentage of Total Rides (%)', fontsize=11)
    ax.set_ylim(20, 80)
    ax.legend(frameon=True, loc='center right')
    
    plt.tight_layout()
    out_file = os.path.join(EDA_DIR, "06_bus_vs_rail_share_over_time.png")
    plt.savefig(out_file)
    plt.close()
    print(f"  Saved: {out_file}")

def plot_gtfs_coverage(df_station_dir, df_routes):
    print("Generating Chart 7: GTFS Network Coverage by Mode & Line...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    
    # 1. Mode breakdown
    mode_counts = df_routes['transit_mode'].value_counts()
    ax1.pie(mode_counts, labels=[f"{k}\n({v} routes)" for k, v in mode_counts.items()], 
            colors=[BLUE, TEAL], autopct='%1.1f%%', startangle=140, 
            wedgeprops=dict(width=0.45, edgecolor='white'))
    ax1.set_title('CTA GTFS Route Breakdown by Mode', fontsize=13, fontweight='bold', color=NAVY)
    
    # 2. Rail lines station counts
    line_names = ['Red', 'Blue', 'Brown', 'Green', 'Orange', 'Purple', 'Pink', 'Yellow']
    line_colors = ['#C60C30', '#00A1DE', '#62361B', '#009B3A', '#F9461C', '#522398', '#E27EA6', '#F9E300']
    
    counts = []
    for l in line_names:
        c = df_station_dir['lines_served'].str.contains(l, case=False, na=False).sum()
        counts.append(c)
        
    bars = ax2.bar(line_names, counts, color=line_colors, edgecolor='#64748B', width=0.55)
    ax2.set_title("Stations Served by 'L' Line", fontsize=13, fontweight='bold', color=NAVY)
    ax2.set_ylabel('Number of Stations', fontsize=11)
    for bar in bars:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 0.5, str(h), ha='center', fontsize=9, fontweight='bold')
    ax2.set_ylim(0, max(counts) + 5)
    
    plt.suptitle('Chicago Transit Authority (CTA) Network Structure', fontsize=15, fontweight='bold', color=NAVY, y=1.02)
    plt.tight_layout()
    out_file = os.path.join(EDA_DIR, "07_gtfs_network_coverage_by_line.png")
    plt.savefig(out_file, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {out_file}")

def plot_unmatched_route_status():
    print("Generating Chart 8: Route Matching & Legacy Classification...")
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    
    categories = ['Active GTFS\nBus Routes', 'Discontinued /\nSpecial Event Routes']
    counts = [124, 7]
    colors = [TEAL, CORAL]
    
    bars = ax.bar(categories, counts, color=colors, width=0.35, edgecolor='#334155')
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 2, f"{h} routes ({h/131*100:.1f}%)", 
                ha='center', fontsize=11, fontweight='bold', color=NAVY)
        
    ax.set_title('CTA Bus Route Matching Status: Active vs Discontinued/Seasonal', fontsize=13, fontweight='bold', color=NAVY, pad=15)
    ax.set_ylabel('Number of Unique Historical Routes', fontsize=11)
    ax.set_ylim(0, 150)
    
    # Legend box detailing the 7 routes
    disc_text = "Discontinued / Seasonal Breakdown:\n• 128: Soldier Field Express\n• 19: United Center Express\n• X98: Avon Express\n• 130: Museum Campus Seasonal\n• 5, 643, 1001: Legacy / Feeder / Pilot"
    ax.text(0.95, 0.75, disc_text, transform=ax.transAxes, fontsize=9, 
            verticalalignment='top', horizontalalignment='right', 
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8FAFC', edgecolor='#CBD5E1'))
    
    plt.tight_layout()
    out_file = os.path.join(EDA_DIR, "08_data_matching_and_unmatched_routes.png")
    plt.savefig(out_file)
    plt.close()
    print(f"  Saved: {out_file}")

def main():
    print("=" * 65)
    print("ROUTERANKER: PHASE 3 EDA VISUALIZATION GENERATION")
    print("=" * 65)
    
    df_sys = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_daily_system_ridership.csv"))
    df_bus = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_bus_route_ridership.csv"))
    df_rail = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_l_station_entries.csv"))
    df_station_dir = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_l_stations_directory.csv"))
    df_routes = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_gtfs_routes.csv"))
    
    plot_system_daily_trend(df_sys)
    plot_weekday_vs_weekend(df_sys)
    plot_monthly_seasonality(df_sys)
    plot_top_bus_routes(df_bus, df_routes)
    plot_top_rail_stations(df_rail, df_station_dir)
    plot_modal_split_evolution(df_sys)
    plot_gtfs_coverage(df_station_dir, df_routes)
    plot_unmatched_route_status()
    
    print("\nAll 8 publication-quality EDA figures generated in outputs/eda/.")

if __name__ == "__main__":
    main()

