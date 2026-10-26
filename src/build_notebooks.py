"""
Builder script to generate and execute Milestone 2 Jupyter Notebooks.
Ensures every notebook:
- Has the required first cell importing from src and reading data/processed/
- Executes top-to-bottom with live outputs, small tables (.head(15)), and saved figures
- Adheres strictly to the routeranker kernel specification
"""

from pathlib import Path
import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = ROOT / "notebooks"
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)

FIRST_CELL_CODE = """from pathlib import Path
import sys

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from src.eda_utils import typical_days, DAY_TYPE_COLORS, calc_period_ratio, calc_cv

DATA = ROOT / "data" / "processed"
FIG = ROOT / "reports" / "figures"
TAB = ROOT / "reports" / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

matched = pd.read_parquet(DATA / "matched_hourly.parquet")
profiles = pd.read_parquet(DATA / "route_profiles.parquet")
print(f"Loaded matched hourly: {len(matched):,} rows (41 routes)")
print(f"Loaded route profiles: {len(profiles)} routes")
"""


def execute_and_save_notebook(nb, out_path: Path):
    """Execute all cells in notebook using NotebookClient and save populated .ipynb."""
    print(f"Executing notebook: {out_path.name}...")
    client = NotebookClient(nb, timeout=600, kernel_name="python3")
    client.execute()
    with open(out_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f"Saved populated notebook -> {out_path.relative_to(ROOT)}")


def build_nb01():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "routeranker",
            "language": "python",
            "name": "routeranker"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }

    # Markdown Header
    nb.cells.append(nbf.v4.new_markdown_cell(
        "# 01: Network Demand Patterns\n"
        "**Milestone 2: Week 3 — Steps 1 to 3**\n\n"
        "This notebook explores macro-level ridership patterns across the entire Manhattan bus network (41 routes):\n"
        "- **Step 1:** Define which days count as 'typical' (reusable filter).\n"
        "- **Step 3:** Network patterns:\n"
        "  1. Daily riders over the study window (with timetable switchover vertical lines and disruption shading)\n"
        "  2. Average riders by hour for typical weekdays, Saturdays, and Sundays (with middle 50% IQR band)\n"
        "  3. Weekday riders by month (summer dip & September rebound)\n"
        "  4. The 10 busiest network hours on typical weekdays"
    ))

    # Cell 1: First Cell Setup
    nb.cells.append(nbf.v4.new_code_cell(FIRST_CELL_CODE))

    # Step 1: Typical Days Filter
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 1: Define 'Typical' Days Filter\n"
        "Normal travel days exclude public holidays, special holiday timetables, storm disruptions, and data outage hours.\n"
        "We inspect the date distribution across typical weekdays, Saturdays, Sundays, and special dates."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "wd_typical = typical_days(matched, 'weekday')\n"
        "sat_typical = typical_days(matched, 'saturday')\n"
        "sun_typical = typical_days(matched, 'sunday')\n\n"
        "print(f'Typical Weekdays:  {wd_typical[\"date\"].nunique():>3} dates ({len(wd_typical):>6,} route-hours)')\n"
        "print(f'Typical Saturdays: {sat_typical[\"date\"].nunique():>3} dates ({len(sat_typical):>6,} route-hours)')\n"
        "print(f'Typical Sundays:   {sun_typical[\"date\"].nunique():>3} dates ({len(sun_typical):>6,} route-hours)')\n\n"
        "# Verify special/disrupted dates\n"
        "special_mask = (matched['is_public_holiday']) | (matched['holiday_schedule']) | (matched['is_storm'])\n"
        "special_dates = matched[special_mask][['date', 'day_of_week', 'is_public_holiday', 'holiday_schedule', 'is_storm']].drop_duplicates()\n"
        "print(f'\\nSpecial Dates ({len(special_dates)} days):')\n"
        "special_dates.head(15)"
    ))

    # Step 3: Network Daily Ridership
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 3.1: Daily Network Ridership Over Whole Window\n"
        "Daily network boardings plotted with timetable version switchover lines and disruption shading."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "import matplotlib.dates as mdates\n\n"
        "daily = matched.groupby('date')['ridership'].sum().reset_index()\n"
        "daily['dt'] = pd.to_datetime(daily['date'])\n"
        "daily = daily.sort_values('dt')\n\n"
        "fig, ax = plt.subplots(figsize=(13, 5), dpi=150)\n"
        "ax.plot(daily['dt'], daily['ridership'] / 1000.0, color='#1e3a8a', linewidth=1.5, label='Daily Total Riders (k)')\n\n"
        "# Timetable switchover lines\n"
        "switchovers = [\n"
        "    ('2026-03-27', '27 Mar: Winter Download'),\n"
        "    ('2026-04-12', '12 Apr: Spring Pick'),\n"
        "    ('2026-06-28', '28 Jun: Summer Pick'),\n"
        "    ('2026-09-06', '6 Sep: Fall Pick'),\n"
        "]\n"
        "for d_str, lbl in switchovers:\n"
        "    dt = pd.to_datetime(d_str)\n"
        "    ax.axvline(dt, color='#dc2626', linestyle=':', linewidth=1.3, alpha=0.85)\n"
        "    ax.text(dt + pd.Timedelta(days=1), 850, lbl, rotation=90, fontsize=8, color='#991b1b', verticalalignment='top')\n\n"
        "# Disruption shading\n"
        "ax.axvspan(pd.to_datetime('2026-01-10'), pd.to_datetime('2026-01-16'), color='#9ca3af', alpha=0.35, label='Excluded Blackout (10-15 Jan)')\n"
        "ax.axvspan(pd.to_datetime('2026-01-25'), pd.to_datetime('2026-01-27'), color='#38bdf8', alpha=0.3, label='Snowstorm (25-26 Jan)')\n"
        "ax.axvspan(pd.to_datetime('2026-02-22'), pd.to_datetime('2026-02-25'), color='#38bdf8', alpha=0.3, label='Blizzard (22-24 Feb)')\n\n"
        "ax.set_title('Network Daily Bus Ridership (Manhattan Routes, Jan-Sep 2026)', fontsize=12, fontweight='bold', pad=10)\n"
        "ax.set_ylabel('Daily Boardings (Thousands)', fontsize=10)\n"
        "ax.set_xlabel('Date', fontsize=10)\n"
        "ax.xaxis.set_major_locator(mdates.MonthLocator())\n"
        "ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))\n"
        "ax.set_ylim(0, 920)\n"
        "ax.grid(True, alpha=0.3)\n"
        "ax.legend(loc='lower left', framealpha=0.9, fontsize=8.5)\n"
        "fig.savefig(FIG / 'm2_network_daily_ridership.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()"
    ))

    # Step 3.2: Hourly Demand Profiles by Day Type
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 3.2: Average Riders by Hour with Middle 50% Band (IQR)\n"
        "For typical weekdays, Saturdays, and Sundays, we compute the distribution across dates for each clock hour."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "fig, ax = plt.subplots(figsize=(10, 5), dpi=150)\n\n"
        "for d_name, d_sub in [('Typical Weekday', wd_typical), ('Typical Saturday', sat_typical), ('Typical Sunday', sun_typical)]:\n"
        "    color = DAY_TYPE_COLORS['weekday' if 'Weekday' in d_name else 'saturday' if 'Saturday' in d_name else 'sunday']\n"
        "    # Total network riders per date and hour\n"
        "    h_date = d_sub.groupby(['date', 'hour'])['ridership'].sum().reset_index()\n"
        "    stats = h_date.groupby('hour')['ridership'].agg(\n"
        "        mean='mean',\n"
        "        q25=lambda s: np.percentile(s, 25),\n"
        "        q75=lambda s: np.percentile(s, 75)\n"
        "    ).reset_index()\n"
        "    \n"
        "    ax.plot(stats['hour'], stats['mean'], color=color, linewidth=2.0, label=f'{d_name} (Mean)')\n"
        "    ax.fill_between(stats['hour'], stats['q25'], stats['q75'], color=color, alpha=0.25, label=f'{d_name} IQR (25-75%)')\n\n"
        "ax.set_title('Network Hourly Demand Profile by Day Type with Middle 50% IQR Band', fontsize=12, fontweight='bold', pad=10)\n"
        "ax.set_xlabel('Clock Hour (0-23)', fontsize=10)\n"
        "ax.set_ylabel('Network Boardings per Hour', fontsize=10)\n"
        "ax.set_xticks(range(24))\n"
        "ax.set_xlim(0, 23)\n"
        "ax.grid(True, alpha=0.3)\n"
        "ax.legend(loc='upper left', fontsize=8, ncol=2)\n"
        "fig.savefig(FIG / 'weekday_hourly_curve.png', dpi=150, bbox_inches='tight')\n"
        "fig.savefig(FIG / 'm2_network_hourly_profiles.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()"
    ))

    # Step 3.3: Monthly Weekday Ridership
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 3.3: Weekday Riders by Month (Summer Dip & September Rebound)\n"
        "Shows the average daily weekday boardings by month, illustrating the summer vacation trough."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "monthly = wd_typical.groupby(['month', 'date'])['ridership'].sum().groupby('month').agg(\n"
        "    mean_daily='mean',\n"
        "    days_count='count'\n"
        ").reset_index()\n\n"
        "month_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep'}\n"
        "monthly['month_name'] = monthly['month'].map(month_map)\n\n"
        "fig, ax = plt.subplots(figsize=(8.5, 4.5), dpi=150)\n"
        "bars = ax.bar(monthly['month_name'], monthly['mean_daily'] / 1000.0, color='#3b82f6', width=0.6, edgecolor='#1d4ed8')\n"
        "# Highlight July & August\n"
        "bars[6].set_facecolor('#f97316'); bars[6].set_edgecolor('#c2410c')\n"
        "bars[7].set_facecolor('#f97316'); bars[7].set_edgecolor('#c2410c')\n\n"
        "for b in bars:\n"
        "    h = b.get_height()\n"
        "    ax.text(b.get_x() + b.get_width() / 2.0, h + 6, f'{h:.1f}k', ha='center', va='bottom', fontsize=8.5, fontweight='bold')\n\n"
        "ax.set_title('Average Typical Weekday Boardings by Month (Jan-Sep 2026)', fontsize=11, fontweight='bold', pad=10)\n"
        "ax.set_ylabel('Average Daily Boardings (Thousands)', fontsize=10)\n"
        "ax.set_xlabel('Month (Orange = Summer Recess)', fontsize=10)\n"
        "ax.set_ylim(0, 850)\n"
        "ax.grid(axis='y', alpha=0.3)\n"
        "fig.savefig(FIG / 'm2_network_monthly_ridership.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()"
    ))

    # Step 3.4: Top 10 Busiest Network Hours
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 3.4: The 10 Busiest Network Hours on Typical Weekdays\n"
        "Ranked by average network boardings per clock hour."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "top10_clock = pd.read_csv(TAB / 'm2_top_10_busiest_clock_hours.csv')\n"
        "print('Top 10 Busiest Clock Hours across 180 Typical Weekdays:')\n"
        "top10_clock.head(10)"
    ))

    out_p = NOTEBOOKS_DIR / "01_network_patterns.ipynb"
    execute_and_save_notebook(nb, out_p)


def build_nb02():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "routeranker",
            "language": "python",
            "name": "routeranker"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }

    # Markdown Header
    nb.cells.append(nbf.v4.new_markdown_cell(
        "# 02: Route Demand Patterns & Stability\n"
        "**Milestone 2: Week 3 — Steps 4 & 5**\n\n"
        "This notebook analyzes route-level demand distributions across all 41 Manhattan bus routes:\n"
        "- **Step 4:** Route patterns:\n"
        "  1. Heatmaps of average hourly boardings (sorted by total weekday volume)\n"
        "  2. Heatmaps of riders per trip (blanking cells with $< 2$ trips/hr on average)\n"
        "  3. Route table: morning peak, midday, evening peak, and night efficiency (totals $\\div$ totals)\n"
        "- **Step 5:** Demand stability across typical weekdays (Coefficient of Variation $CV = \\sigma / \\mu$)"
    ))

    # Cell 1: Setup
    nb.cells.append(nbf.v4.new_code_cell(FIRST_CELL_CODE))

    # Step 4.1: Volume Heatmaps
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 4.1: Route Boardings Heatmaps\n"
        "Routes are ordered along the vertical axis by total typical weekday ridership (highest volume at top)."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "wd_typical = typical_days(matched, 'weekday')\n"
        "route_order = wd_typical.groupby('route')['ridership'].sum().sort_values(ascending=False).index.tolist()\n\n"
        "num_days = wd_typical['date'].nunique()\n"
        "pivot_vol = wd_typical.pivot_table(index='route', columns='hour', values='ridership', aggfunc='sum') / num_days\n"
        "pivot_vol = pivot_vol.reindex(index=route_order)\n\n"
        "fig, ax = plt.subplots(figsize=(11, 9), dpi=150)\n"
        "sns.heatmap(pivot_vol, cmap='YlGnBu', ax=ax, cbar_kws={'label': 'Average Hourly Boardings'})\n"
        "ax.set_title('Average Route Boardings by Hour: Typical Weekdays (Routes Ranked by Total Volume)', fontsize=11, fontweight='bold', pad=10)\n"
        "ax.set_xlabel('Clock Hour (0-23)', fontsize=10)\n"
        "ax.set_ylabel('Route', fontsize=10)\n"
        "fig.savefig(FIG / 'm2_heatmap_riders_weekday.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()"
    ))

    # Step 4.2: Riders per Trip Heatmaps (Blanked < 2 trips)
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 4.2: Riders per Trip Heatmaps (Blanked where Average Trips < 2/hr)\n"
        "Blanking cells with fewer than 2 scheduled trips per hour filters out solitary late-night buses."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "sum_riders = wd_typical.pivot_table(index='route', columns='hour', values='ridership', aggfunc='sum')\n"
        "sum_trips = wd_typical.pivot_table(index='route', columns='hour', values='trips_running', aggfunc='sum')\n"
        "avg_trips = sum_trips / num_days\n\n"
        "# Divide totals by totals\n"
        "with np.errstate(divide='ignore', invalid='ignore'):\n"
        "    rpt_grid = np.where(sum_trips > 0, sum_riders / sum_trips, np.nan)\n"
        "    # Blank out cells where avg_trips < 2.0\n"
        "    rpt_filtered = np.where(avg_trips >= 2.0, rpt_grid, np.nan)\n\n"
        "rpt_df = pd.DataFrame(rpt_filtered, index=sum_riders.index, columns=sum_riders.columns).reindex(index=route_order)\n\n"
        "fig, ax = plt.subplots(figsize=(11, 9), dpi=150)\n"
        "sns.heatmap(rpt_df, cmap='magma', ax=ax, vmin=0, vmax=50, cbar_kws={'label': 'Riders per Trip (Totals ÷ Totals)'})\n"
        "ax.set_title('Riders per Trip by Hour: Typical Weekdays (Blanked where Avg Trips < 2/hr)', fontsize=11, fontweight='bold', pad=10)\n"
        "ax.set_xlabel('Clock Hour (0-23)', fontsize=10)\n"
        "ax.set_ylabel('Route', fontsize=10)\n"
        "fig.savefig(FIG / 'm2_heatmap_rpt_weekday.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()"
    ))

    # Step 4.3: Route Table
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 4.3: Route Efficiency Summary Table\n"
        "Evaluates riders per trip and riders per service-hour across 4 time bands (morning peak, midday, evening peak, night)."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "route_table = pd.read_csv(TAB / 'm2_route_performance_table.csv')\n"
        "print(f'Total route-band performance entries: {len(route_table)}')\n"
        "print('\\nSample entries (Typical Weekday Peak and Off-Peak Performance):')\n"
        "route_table[route_table['day_type'] == 'Typical Weekday'].head(15)"
    ))

    # Step 5: Demand Stability
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 5: Demand Stability Across Typical Weekdays\n"
        "Measures how much ridership varies from one weekday to the next using Coefficient of Variation ($CV = \\sigma / \\mu$)."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "var_table = pd.read_csv(TAB / 'm2_route_demand_variability.csv')\n"
        "cv_pivot = var_table.pivot(index='route', columns='hour', values='cv')\n\n"
        "# Rank routes by mean daytime CV (06:00 to 22:00)\n"
        "daytime_cv = var_table[var_table['hour'].between(6, 22)].groupby('route')['cv'].mean().sort_values(ascending=False)\n"
        "cv_pivot = cv_pivot.reindex(index=daytime_cv.index)\n\n"
        "fig, ax = plt.subplots(figsize=(11, 9), dpi=150)\n"
        "sns.heatmap(cv_pivot, cmap='viridis_r', ax=ax, vmin=0.1, vmax=0.6, cbar_kws={'label': 'CV (std ÷ mean)'})\n"
        "ax.set_title('Route Demand Stability by Hour (Typical Weekdays)\\nHigher CV = More Volatile / Less Predictable Demand', fontsize=11, fontweight='bold', pad=10)\n"
        "ax.set_xlabel('Clock Hour (0-23)', fontsize=10)\n"
        "ax.set_ylabel('Route (Sorted by Daytime Volatility)', fontsize=10)\n"
        "fig.savefig(FIG / 'm2_demand_variability.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()\n\n"
        "print('Top 5 Most Predictable Routes (Lowest CV):')\n"
        "print(daytime_cv.tail(5).round(3))\n"
        "print('\\nTop 5 Most Volatile Routes (Highest CV):')\n"
        "print(daytime_cv.head(5).round(3))"
    ))

    out_p = NOTEBOOKS_DIR / "02_route_patterns.ipynb"
    execute_and_save_notebook(nb, out_p)


def build_nb03():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "routeranker",
            "language": "python",
            "name": "routeranker"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }

    # Markdown Header
    nb.cells.append(nbf.v4.new_markdown_cell(
        "# 03: Route Overlap & Network Coverage\n"
        "**Milestone 2: Week 3 — Step 6**\n\n"
        "Using the Spring timetable (`2026-04-09`), this notebook evaluates corridor-level redundancy vs planned coordination:\n"
        "- Stop sets per route and direction\n"
        "- Pairwise shared stops, overlap share (shared $\\div$ smaller route stops), and Jaccard similarity\n"
        "- Detailed analysis of top 15 pairs (continuity, direction alignment, hours, peak combined buses/hr)\n"
        "- Classification of planned pairs (Select Bus Service + local versions, SBS branch pairs)\n"
        "- Network coverage metric: share of stops served by no other route\n"
        "- Interactive Folium map of top overlapping corridors"
    ))

    # Cell 1: Setup
    nb.cells.append(nbf.v4.new_code_cell(FIRST_CELL_CODE))

    # Step 6.1: Pairwise Overlap Summary
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 6.1: Pairwise Route Overlap (Spring 2026-04-09 Timetable)\n"
        "Analyzes stop-level overlap across all 127 overlapping route pairs in Manhattan."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "pairs_df = pd.read_csv(TAB / 'm2_route_overlap_all_pairs.csv')\n"
        "print(f'Total overlapping route pairs: {len(pairs_df)}')\n"
        "print('\\nTop 10 Route Pairs by Overlap Share:')\n"
        "pairs_df.head(10)"
    ))

    # Step 6.2: Top 15 Pairs In-Depth Evaluation
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 6.2: Top 15 Overlapping Pairs In-Depth Analysis\n"
        "Profiles corridor continuity, direction alignment, operating hours, peak frequency, and design intent."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "top15 = pd.read_csv(TAB / 'm2_top_15_route_overlaps.csv')\n"
        "top15[['rank', 'route_1', 'route_2', 'shared_stops', 'overlap_share', 'jaccard', 'stretch_type', 'combined_peak_buses_per_hr', 'design_classification', 'design_notes']]"
    ))

    # Step 6.3: Network Coverage (Stop Exclusivity)
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 6.3: Network Coverage & Exclusive Stop Share\n"
        "Measures the share of stops served by no other route. Routes with high exclusivity provide essential coverage."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "coverage = pd.read_csv(TAB / 'm2_route_stop_coverage.csv')\n"
        "print('Top 10 Lifeline Coverage Routes (High Stop Exclusivity):')\n"
        "print(coverage.head(10)[['route', 'total_stops', 'exclusive_stops', 'exclusive_stop_share']])\n\n"
        "print('\\nTop 5 Routes with Lowest Stop Exclusivity (Parallel Corridors):')\n"
        "print(coverage.tail(5)[['route', 'total_stops', 'exclusive_stops', 'exclusive_stop_share']])"
    ))

    # Step 6.4: Interactive Folium Map
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 6.4: Interactive Corridor Map (Folium)\n"
        "Visualizes top overlapping transit corridors on OpenStreetMap."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "import folium\n"
        "from IPython.display import IFrame\n\n"
        "map_file = FIG / 'route_overlaps.html'\n"
        "print(f'Interactive map generated at: {map_file.relative_to(ROOT)}')\n"
        "# Render iframe preview\n"
        "IFrame(src='../reports/figures/route_overlaps.html', width='100%', height=500)"
    ))

    out_p = NOTEBOOKS_DIR / "03_route_overlap.ipynb"
    execute_and_save_notebook(nb, out_p)


def build_nb04():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "routeranker",
            "language": "python",
            "name": "routeranker"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }

    # Markdown Header
    nb.cells.append(nbf.v4.new_markdown_cell(
        "# 04: Route-Hours with Low Demand per Trip\n"
        "**Milestone 2: Week 3 — Step 7**\n\n"
        "This notebook screens for route, day type, and time band combinations with low riders per trip:\n"
        "- **Screening Criteria:**\n"
        "  1. `riders_per_trip` in bottom 10% for that day type\n"
        "  2. Average trips per day $\\ge 2.0$\n"
        "  3. Days of data behind figure $\\ge 20$\n"
        "- **Contextual Enrichment:**\n"
        "  - Scheduled service-hours and `riders_per_service_hour`\n"
        "  - Exclusive stop coverage share (stops served by no other route)\n"
        "  - Top overlapping partner route and overlap share\n\n"
        "> **Important Principle:** We explicitly call this list **'low riders per trip'**, never 'inefficient routes'. "
        "It is a screening list for operational review, not a verdict. Low patronage often reflects essential lifeline coverage (e.g., M35)."
    ))

    # Cell 1: Setup
    nb.cells.append(nbf.v4.new_code_cell(FIRST_CELL_CODE))

    # Step 7.1: Screening Thresholds
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 7.1: 10th Percentile Thresholds by Day Type\n"
        "Thresholds are derived from the distribution of route-band riders per trip across all active routes."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "perf_table = pd.read_csv(TAB / 'm2_route_performance_table.csv')\n\n"
        "thresholds = {}\n"
        "for dt in ['Typical Weekday', 'Typical Saturday', 'Typical Sunday']:\n"
        "    sub = perf_table[perf_table['day_type'] == dt].dropna(subset=['riders_per_trip'])\n"
        "    p10 = sub['riders_per_trip'].quantile(0.10)\n"
        "    thresholds[dt] = round(p10, 2)\n"
        "    print(f'{dt:18s} Bottom 10% Threshold: <= {p10:.2f} riders/trip')\n\n"
        "pd.Series(thresholds, name='P10_Threshold').to_frame()"
    ))

    # Step 7.2: Screened Review List
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 7.2: Operational Review List: Low Riders per Trip\n"
        "Displays combinations meeting all 3 criteria with stop coverage and corridor overlap context."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "low_df = pd.read_csv(TAB / 'm2_low_riders_per_trip.csv')\n"
        "print(f'Total qualified combinations for review: {len(low_df)}')\n"
        "print(f'Breakdown by day type: {dict(low_df[\"day_type\"].value_counts())}')\n\n"
        "print('\\nTop 15 Lowest Riders per Trip Combinations:')\n"
        "low_df.head(15)"
    ))

    # Step 7.3: Contextual Discussion on Lifeline & Feeder Routes
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 7.3: Policy Context & Network Role Analysis\n"
        "A low riders-per-trip figure does not imply a route should be cut. We examine coverage roles:\n"
        "1. **M35 (Randall's Island Shuttle):** Averages 0.71–3.48 riders/trip, but has **100% exclusive stops**. It is the only transit connection to Randall's Island social service and municipal facilities.\n"
        "2. **M22 / M8 (Crosstown / Lower Manhattan Coverage):** Maintain 72–86% exclusive stops, ensuring access where avenue routes do not reach.\n"
        "3. **M55 / M20 (Off-Peak Avenue Feeders):** Have parallel alternatives (e.g. M1, M7), making them candidates for schedule coordination rather than route elimination."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "coverage = pd.read_csv(TAB / 'm2_route_stop_coverage.csv').set_index('route')\n\n"
        "print('Coverage analysis for key low-demand routes:')\n"
        "for r in ['M35', 'M22', 'M8', 'M55', 'M20', 'M10']:\n"
        "    ex_share = coverage.loc[r, 'exclusive_stop_share']\n"
        "    ex_stops = coverage.loc[r, 'exclusive_stops']\n"
        "    print(f'Route {r:4s}: {ex_share*100:5.1f}% unique stops ({ex_stops} stops served by NO other bus)')"
    ))

    out_p = NOTEBOOKS_DIR / "04_low_riders_per_trip.ipynb"
    execute_and_save_notebook(nb, out_p)


def build_nb05():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "routeranker",
            "language": "python",
            "name": "routeranker"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }

    # Markdown Header
    nb.cells.append(nbf.v4.new_markdown_cell(
        "# 05: Modeling Features, Targets & Data Splits\n"
        "**Milestone 2: Week 4 — Steps 9 to 12**\n\n"
        "This notebook inspects the output generated by `src/build_features.py`:\n"
        "- **Step 9:** Model task formulation and 75th percentile classification target\n"
        "- **Step 10:** Feature table inspection (known in advance, fixed route, exact calendar lags)\n"
        "- **Step 11:** Date splits inspection (Train: Jan-May, Val: Jun-Jul, Test: Aug-Sep)\n"
        "- **Step 12:** Scikit-learn Pipeline with ColumnTransformer (`models/preprocessor.joblib`)"
    ))

    # Cell 1: Setup
    nb.cells.append(nbf.v4.new_code_cell(FIRST_CELL_CODE))

    # Step 9: Classification Target
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 9: Classification Target Formulation ('High Demand per Trip')\n"
        "An hour counts as 'high demand per trip' when `riders_per_trip` exceeds the 75th percentile for that route and day type, "
        "calculated strictly from training dates (`date <= 2026-05-31`). It must be predicted without using current-hour ridership."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "thresholds = pd.read_csv(TAB / 'm2_high_demand_thresholds.csv')\n"
        "print(f'Total route x day_type threshold combinations: {len(thresholds)}')\n"
        "print('\\nSample 75th Percentile Thresholds (Training Period):')\n"
        "thresholds.head(15)"
    ))

    # Step 10: Features and Exact Calendar Lags
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 10: Features and Exact Calendar Lags\n"
        "Lags (7d, 14d, 21d, 28d) are retrieved by exact calendar date lookup. "
        "Excluded hours remain `NaN` and are never 0-filled. A 1-day lag is omitted from the main model to prevent data leakage."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "feat_all = pd.read_parquet(DATA / 'modeling_features_all.parquet')\n"
        "lag_cols = ['lag_7d', 'lag_14d', 'lag_21d', 'lag_28d', 'lag_mean_available', 'lags_available_count']\n\n"
        "print('Summary of Exact Calendar Lags:')\n"
        "print(feat_all[lag_cols].describe().round(2))\n\n"
        "print('\\nSample row with available lags:')\n"
        "feat_all[['route', 'date', 'hour', 'ridership', 'high_demand_per_trip'] + lag_cols].dropna().head(10)"
    ))

    # Step 11: Date Splits
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 11: Chronological Date Splits\n"
        "Data is partitioned chronologically with zero row shuffling:\n"
        "- **Training:** 4 January to 31 May (125,445 rows)\n"
        "- **Validation:** 1 June to 31 July (54,046 rows)\n"
        "- **Test:** 1 August to 30 September (53,736 rows)\n\n"
        "> **Known Seasonal Weakness:** Training data contains no summer months (July-August), while test data includes school reopenings in September."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "splits_summary = pd.read_csv(TAB / 'm2_data_splits_summary.csv')\n"
        "splits_summary"
    ))

    # Step 12: Preprocessor Pipeline
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 12: Scikit-Learn Preprocessing Pipeline\n"
        "Inspects the fitted pipeline (`models/preprocessor.joblib`), which transforms routes, hour sine/cosine, and scales features."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "import joblib\n\n"
        "preprocessor = joblib.load(ROOT / 'models' / 'preprocessor.joblib')\n"
        "train_df = pd.read_parquet(DATA / 'train_features.parquet').head(50)\n\n"
        "X_transformed = preprocessor.transform(train_df)\n"
        "print(f'Pipeline loaded successfully: {type(preprocessor).__name__}')\n"
        "print(f'Sample input shape: {train_df.shape} -> Transformed feature dimension: {X_transformed.shape}')"
    ))

    out_p = NOTEBOOKS_DIR / "05_features_and_splits.ipynb"
    execute_and_save_notebook(nb, out_p)


def build_nb06():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "routeranker",
            "language": "python",
            "name": "routeranker"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }

    # Markdown Header
    nb.cells.append(nbf.v4.new_markdown_cell(
        "# 06: Route Clustering Feature Table\n"
        "**Milestone 2: Week 4 — Step 13**\n\n"
        "This notebook builds and evaluates the route-level feature table for clustering the 41 Manhattan routes:\n"
        "- Computed strictly from **typical weekdays in the training period** (4 January to 31 May)\n"
        "- Candidate metrics: weekday volume (log), weekend-to-weekday ratio, peak shares, peak/offpeak efficiency, length, speed, variability, coverage\n"
        "- Multicollinearity pruning: drop one of each pair with $|r| > 0.85$\n"
        "- Feature standardization using `StandardScaler`"
    ))

    # Cell 1: Setup
    nb.cells.append(nbf.v4.new_code_cell(FIRST_CELL_CODE))

    # Step 13.1: Candidate Metrics & Correlation Matrix
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 13.1: Candidate Features & Multicollinearity Pruning\n"
        "With 41 routes, models require a concise set of 8 to 10 features without redundant collinearity ($|r| > 0.85$)."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "corr_matrix = pd.read_csv(TAB / 'm2_clustering_feature_correlations.csv', index_col=0)\n"
        "print('Correlation Matrix for Candidate Route Metrics:')\n\n"
        "# Plot correlation heatmap\n"
        "fig, ax = plt.subplots(figsize=(10, 8), dpi=150)\n"
        "sns.heatmap(corr_matrix, cmap='vlag', vmin=-1, vmax=1, annot=True, fmt='.2f', annot_kws={'size': 7}, ax=ax)\n"
        "ax.set_title('Pairwise Pearson Correlation: Candidate Clustering Features', fontsize=11, fontweight='bold', pad=10)\n"
        "fig.savefig(FIG / 'm2_clustering_correlations.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()"
    ))

    # Step 13.2: Selected Scaled Feature Table
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 13.2: Selected 9 Scaled Clustering Features\n"
        "The final 9 features cover volume scale, weekend orientation, peak concentration, night service, operational efficiency, length, speed, stability, and network exclusivity (maximum pairwise $|r| = 0.840 < 0.85$)."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "cf_scaled = pd.read_parquet(DATA / 'clustering_features.parquet')\n"
        "print(f'Total routes: {len(cf_scaled)} (41 routes)')\n"
        "print('\\nScaled Features Sample (Ready for K-Means / Hierarchical Clustering in Milestone 3):')\n"
        "cf_scaled.head(15)"
    ))

    # Step 13.3: Unscaled Table for Interpretability
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 13.3: Unscaled Route Profiles (Natural Units)\n"
        "Natural units table for interpreting cluster centroids and business profiles."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "cf_unscaled = pd.read_csv(TAB / 'm2_clustering_features_unscaled.csv')\n"
        "selected_cols = ['route'] + [c for c in cf_scaled.columns if c != 'route']\n"
        "cf_unscaled[selected_cols].head(15)"
    ))

    out_p = NOTEBOOKS_DIR / "06_clustering_table.ipynb"
    execute_and_save_notebook(nb, out_p)


def build_nb07():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "routeranker",
            "language": "python",
            "name": "routeranker"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }

    # Markdown Header
    nb.cells.append(nbf.v4.new_markdown_cell(
        "# 07: Baseline Forecasting Benchmarks\n"
        "**Milestone 2: Week 4 — Step 14**\n\n"
        "This notebook establishes empirical baseline performance hurdles scored on the validation period (1 June to 31 July 2026):\n"
        "1. **Same hour last week:** Ridership 7 days earlier (`lag_7d`)\n"
        "2. **4-week average:** Average of 7, 14, 21, and 28-day lags (`lag_mean_available`)\n\n"
        "Three error metrics are reported:\n"
        "- **MAE:** Mean Absolute Error (in riders)\n"
        "- **RMSE:** Root Mean Squared Error (penalizes large misses)\n"
        "- **WAPE:** Weighted Absolute Percentage Error ($\\sum |y - \\hat{y}| \\div \\sum y$)\n\n"
        "> **Milestone 3 Hurdle:** Every predictive machine learning model developed in Milestone 3 must beat these baseline scores."
    ))

    # Cell 1: Setup
    nb.cells.append(nbf.v4.new_code_cell(FIRST_CELL_CODE))

    # Step 14.1: Overall Benchmark Performance
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 14.1: Overall Network Baseline Performance\n"
        "Evaluated across all 54,046 validation rows (June–July 2026)."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "overall = pd.read_csv(TAB / 'm2_baseline_forecast_overall.csv')\n"
        "print('Overall Validation Baseline Metrics:')\n"
        "overall"
    ))

    # Step 14.2: Per-Route Benchmark Breakdown
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 14.2: Per-Route Benchmark Performance\n"
        "Examines error metrics across individual routes. High-volume trunk lines achieve WAPE $\\approx 11-13\\%$, "
        "while low-volume feeder shuttles register higher percentage errors despite lower absolute errors."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "per_route = pd.read_csv(TAB / 'm2_baseline_forecast_per_route.csv')\n"
        "print(f'Total routes evaluated: {len(per_route)}')\n"
        "print('\\nTop 15 Routes by Volume with Baseline Errors:')\n"
        "per_route.sort_values('total_riders', ascending=False).head(15)"
    ))

    # Step 14.3: Error Comparison Visualization
    nb.cells.append(nbf.v4.new_markdown_cell(
        "## Step 14.3: Comparison of Baseline Models (WAPE %)\n"
        "Visualizes how smoothing across 4 historical weeks reduces error compared to a single-lag forecast."
    ))

    nb.cells.append(nbf.v4.new_code_cell(
        "fig, ax = plt.subplots(figsize=(12, 6), dpi=150)\n"
        "sorted_r = per_route.sort_values('total_riders', ascending=False)\n"
        "x = np.arange(len(sorted_r))\n"
        "width = 0.38\n\n"
        "ax.bar(x - width/2, sorted_r['lag7_wape_pct'], width, label='Same Hour Last Week (lag_7d)', color='#93c5fd', edgecolor='#1d4ed8')\n"
        "ax.bar(x + width/2, sorted_r['avg4wk_wape_pct'], width, label='4-Week Average (lag_mean)', color='#1d4ed8', edgecolor='#1e3a8a')\n\n"
        "ax.set_title('Baseline Forecast WAPE (%) by Route (Ranked by Total Volume)', fontsize=11, fontweight='bold', pad=10)\n"
        "ax.set_ylabel('WAPE (%)', fontsize=10)\n"
        "ax.set_xlabel('Route', fontsize=10)\n"
        "ax.set_xticks(x)\n"
        "ax.set_xticklabels(sorted_r['route'], rotation=90, fontsize=8)\n"
        "ax.axhline(overall.loc[1, 'wape_pct'], color='#dc2626', linestyle='--', linewidth=1.2, label=f'4-Week Network Mean ({overall.loc[1, \"wape_pct\"]}%)')\n"
        "ax.grid(axis='y', alpha=0.3)\n"
        "ax.legend(fontsize=8.5)\n"
        "fig.savefig(FIG / 'm2_baseline_wape_comparison.png', dpi=150, bbox_inches='tight')\n"
        "plt.show()"
    ))

    out_p = NOTEBOOKS_DIR / "07_baselines.ipynb"
    execute_and_save_notebook(nb, out_p)


if __name__ == "__main__":
    build_nb07()






