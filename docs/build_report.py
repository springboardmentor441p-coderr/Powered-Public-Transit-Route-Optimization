"""Generate the project report (Word .docx) from the pipeline outputs.

    python docs/build_report.py            -> docs/RouteRanker_Project_Report.docx

Numbers, tables and figures are read from reports/metrics/*.json and
reports/figures/*.png, so the report always matches the last pipeline run.
The function reference is generated from the source code (signatures + docstrings).
"""
from __future__ import annotations

import ast
import re
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import main as C  # noqa: E402  (backend/main.py doubles as the configuration namespace)

M = json.loads((C.METRICS_DIR / "model_metrics.json").read_text())
E = json.loads((C.EDA_DIR / "eda_summary.json").read_text())
MAN = json.loads((C.METRICS_DIR / "pipeline_manifest.json").read_text())
FIG = {**E["figures"], **M["figures"]}
OUT = ROOT / "docs" / "RouteRanker_Project_Report.docx"
TOC_JSON = ROOT / "docs" / ".toc_pages.json"
PASS = int(os.environ.get("RR_PASS", "1"))
HEADINGS: list[tuple[str, int]] = []
BLUE = RGBColor(0x1E, 0x3A, 0x8A)

doc = Document()


# ----------------------------------------------------------------- styles
def setup_styles():
    st = doc.styles
    st["Normal"].font.name = "Calibri"
    st["Normal"].font.size = Pt(11)
    st["Normal"].paragraph_format.space_after = Pt(6)
    for lvl, size in ((1, 18), (2, 14), (3, 12)):
        s = st[f"Heading {lvl}"]
        s.font.name = "Calibri"
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = BLUE
        s.paragraph_format.space_before = Pt(14 if lvl == 1 else 10)
        s.paragraph_format.space_after = Pt(6)
        s.paragraph_format.keep_with_next = True
        rpr = s.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            fonts.set(qn(a), "Calibri")
    for sec in doc.sections:
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.2)
        sec.top_margin = sec.bottom_margin = Cm(2.0)


def H(text, lvl=1):
    doc.add_heading(text, level=lvl)
    if text != "Table of Contents":
        HEADINGS.append((text, lvl))


def P(text, bold=False, italic=False, size=None, align=None):
    p = doc.add_paragraph()
    _rich(p, text, bold, italic, size)
    if align:
        p.alignment = align
    return p


def _rich(p, text, bold=False, italic=False, size=None):
    """Very small **bold** / `code` markup support."""
    import re
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**"):
            r = p.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`"):
            r = p.add_run(part[1:-1]); r.font.name = "Consolas"; r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0x7E, 0x22, 0xCE)
        else:
            r = p.add_run(part); r.bold = bold
        r.italic = italic or r.italic
        if size and not part.startswith("`"):
            r.font.size = Pt(size)


def B(items, style="List Bullet"):
    for it in items:
        p = doc.add_paragraph(style=style)
        _rich(p, it)


def N(items):
    B(items, "List Number")


def code(text):
    for line in text.strip("\n").split("\n"):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Cm(0.5)
        r = p.add_run(line or " ")
        r.font.name = "Consolas"; r.font.size = Pt(8.5)
        _shade(p, "F1F5F9")


def _shade(p, color):
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color)
    ppr.append(shd)


def _cell_shade(cell, color):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color)
    tcpr.append(shd)


def T(header, rows, widths=None, size=9):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    total = 16.6
    widths = widths or [total / len(header)] * len(header)
    trpr = t.rows[0]._tr.get_or_add_trPr()  # repeat header row on every page
    th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); trpr.append(th)
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(str(h)); r.bold = True; r.font.size = Pt(size)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _cell_shade(c, "1E3A8A")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            _rich(cells[i].paragraphs[0], str(v), size=size)
            for r in cells[i].paragraphs[0].runs:
                r.font.size = Pt(size)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return t


def IMG(key_or_path, caption, width=16):
    path = ROOT / FIG[key_or_path] if key_or_path in FIG and FIG[key_or_path] else ROOT / key_or_path
    if not path.exists():
        return
    doc.add_picture(str(path), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = P(caption, italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.space_after = Pt(10)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def toc():
    if PASS > 1 and TOC_JSON.exists():
        for text, lvl, page in json.loads(TOC_JSON.read_text(encoding="utf-8")):
            p = doc.add_paragraph()
            p.paragraph_format.tab_stops.add_tab_stop(Cm(16.6), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
            p.paragraph_format.left_indent = Cm(0.6 * (lvl - 1))
            p.paragraph_format.space_after = Pt(1 if lvl > 1 else 3)
            r = p.add_run(f"{text}	{page}")
            r.font.size = Pt(10 if lvl > 1 else 11)
            r.bold = lvl == 1
        return
    p = doc.add_paragraph()
    r = p.add_run()
    for tag, txt in (("begin", None), (None, 'TOC \\o "1-2" \\h \\z \\u'), ("separate", None)):
        if tag:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), tag); r._r.append(el)
        else:
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = txt; r._r.append(it)
    r2 = p.add_run("Right-click → Update Field to refresh the table of contents.")
    r2.italic = True
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end"); r2._r.append(end)


def f(x, d=3):
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else str(x)


# =================================================================== content
setup_styles()
cl, fc, km, db = M["classification"], M["forecasting"], M["clustering"]["kmeans"], M["clustering"]["dbscan"]
imp = M["optimisation_impact_validation"]
cr = E["cleaning_report"]

# ---- title
for _ in range(5):
    doc.add_paragraph()
P("RouteRanker", bold=True, size=36, align=WD_ALIGN_PARAGRAPH.CENTER).runs[0].font.color.rgb = BLUE
P("AI-Powered Public Transit Route Optimisation", size=18, align=WD_ALIGN_PARAGRAPH.CENTER)
P("Technical Project Report - methodology, models, architecture and function reference", italic=True, size=12,
  align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
P(f"Data: MTA Bus Hourly Ridership (data.ny.gov) · {MAN['data_start']} to {MAN['data_end']} · "
  f"{MAN['routes']} routes · {MAN['route_hours']:,} route-hours", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
P(f"Report generated {datetime.now(C.IST):%d %B %Y, %I:%M %p} IST · models built {MAN['built_at_ist']}", size=10,
  align=WD_ALIGN_PARAGRAPH.CENTER)
page_break()
H("Table of Contents")
toc()
page_break()

# ---- 1 executive summary
H("1. Executive Summary")
P("RouteRanker is an end-to-end machine-learning system that analyses public bus transit data, identifies "
  "under-performing and overcrowded routes, recommends optimisation actions (frequency changes, merging, "
  "splitting) and predicts the best route for any selected date and time. Results are delivered through a "
  "Streamlit dashboard (11 pages) and a FastAPI REST backend, both running on localhost. All user-facing dates "
  "and times are shown in Indian Standard Time (IST).")
T(["Item", "Result"], [
    ["Data granularity", "**Hourly** - boardings per route per clock hour (daily = sum of hours)"],
    ["Data window", f"{MAN['data_start']} → {MAN['data_end']} ({E['days']} days)"],
    ["Routes modelled / route-hours", f"{MAN['routes']} / {MAN['route_hours']:,}"],
    ["Total boardings analysed", f"{E['total_boardings'] / 1e6:,.1f} million"],
    ["Clustering", f"KMeans k={km['k']} (silhouette {km['silhouette']:.3f}); DBSCAN {db['n_clusters']} dense "
                   f"cluster(s) + {db['n_outliers']} outlier routes"],
    ["Classification (best)", f"{cl['best']} - macro-F1 {cl[cl['best']]['f1_macro']:.3f}, accuracy "
                              f"{cl[cl['best']]['accuracy']:.3f}"],
    ["Forecasting (best)", f"{fc['best']} - MAE {fc[fc['best']]['mae']:.2f} boardings/route-hour, R² "
                           f"{fc[fc['best']]['r2']:.3f}, WAPE {fc[fc['best']]['wape']:.1%} (baseline WAPE "
                           f"{fc['SeasonalProfileBaseline']['wape']:.1%})"],
    ["Optimisation impact (hold-out)", f"overcrowded route-hours {imp['overcrowded_share_now']:.1%} → "
                                       f"{imp['overcrowded_share_opt']:.1%}; underutilised "
                                       f"{imp['underutilized_share_now']:.1%} → {imp['underutilized_share_opt']:.1%}"],
    ["Architecture", "Layered modular monolith: data → processing → ML → service layer → Streamlit UI + FastAPI"],
], [5, 11.6])

# ---- 2 problem
H("2. Problem Statement and Objectives")
P("The project brief (AI_RouteRanker PDF) asks for an AI system that analyses public-transit data to optimise "
  "inefficient bus routes, identifies underperforming or overcrowded routes, recommends changes (merging, "
  "frequency adjustment) and provides insights through a Streamlit interface. Expected outcomes:")
B(["Clear identification of route inefficiencies.", "Strategic optimisation recommendations.",
   "A user-friendly interface for planners to view and act on model insights."])
P("Additional requirements implemented in this build:")
B(["Date selection: choose today (real-time prediction) or any past/future date; the app returns the best route, "
   "**why** it is best, and validates it by comparing with the other routes.",
   "Pages for network overview, productivity ranking, route comparison, historical replay, scenario simulator and "
   "data & coverage, plus EDA, model performance, optimisation actions and pipeline/architecture.",
   "Forecast timestamps and dates in **IST**; pipeline and architecture diagrams embedded in the application.",
   "Well-organised GitHub repository with README; this Word report."])
H("2.1 Data-source decision", 2)
P("The brief names the Lepton Software GTFS feed for 23 Indian cities. That feed is a commercial product and "
  "GTFS itself contains schedules only - **no ridership counts**, so passenger load cannot be measured from it. "
  "The data links supplied with the request point to the MTA (New York) open-data portal, which publishes "
  "**hourly ridership per route** together with GTFS-derived schedules, routes, stops and speeds. RouteRanker "
  "therefore trains on the MTA data (the only source that has the required ridership parameter at hourly "
  "resolution) and also includes a **GTFS upload analyser** so that any Indian GTFS feed (Lepton, DIMTS, BMTC "
  "...) can be profiled, clustered and screened for overlaps in the same app.")
H("2.2 Why 'MTA Bus Hourly Ridership: Beginning 2025' is the primary dataset", 2)
T(["Candidate link", "Granularity", "Decision"], [
    ["MTA Bus Hourly Ridership: Beginning Feb 2022 / 2020-2024", "Hourly x route", "Superseded / historical - not current"],
    ["**MTA Bus Hourly Ridership: Beginning 2025** (gxb3-akrn)", "Hourly x route x fare class",
     "**Chosen** - current (updated weekly), hourly, has ridership + transfers per route"],
    ["MTA Bus Stop Level Ridership: Beginning 2024", "Monthly x stop (estimates)", "Not hourly; used conceptually only"],
    ["MTA Bus Route Segment Speeds: Beginning 2025 (kufs-yh3x)", "Hourly x route x day-of-week x segment",
     "**Used** - hourly operating speed per route"],
    ["MTA Bus Route Segment Speeds: 2023-2024", "Same", "Older; not needed"],
    ["MTA Bus Speeds: Beginning 2015/2020 (cudb-vcni)", "Monthly x route x period", "**Used** - speed fallback"],
    ["MTA GTFS Static Data", "Schedules", "Replaced by the tabular, queryable GTFS-derived tables below"],
    ["MTA Bus Schedules 2026, Routes, Stops, Wait Assessment", "Trip/stop, route, route-month",
     "**Used** - trips per hour, length, geometry, stops, reliability"],
], [6.2, 4.2, 6.2])

# ---- 3 data collection
H("3. Module 1 - Data Collection")
P("All data is pulled from the Socrata Open Data API (SODA) at data.ny.gov using SoQL. Heavy tables are "
  "**aggregated server-side** so only the required granularity is transferred (e.g. hourly ridership is summed "
  "over payment method and fare class into one row per route per hour). Ridership is downloaded month by month "
  "and cached as Parquet; completed months are never re-downloaded, so a refresh only fetches the current "
  "month (incremental update for near-real-time operation).")
rows = [[s["name"], s["id"], s["granularity"], s["role"]] for s in MAN["sources"].values()]
T(["Dataset", "ID", "Granularity", "Role in RouteRanker"], rows, [5.2, 2.2, 4.4, 4.8], size=8.5)
P("Rows pulled per raw table: " + ", ".join(f"{k} = {v:,}" for k, v in MAN["raw_rows"].items()) + ".")
P("Example SoQL (hourly ridership, one month):", bold=True)
code("""SELECT transit_timestamp, bus_route, sum(ridership) AS ridership, sum(transfers) AS transfers
WHERE transit_timestamp >= '2026-10-01T00:00:00' AND transit_timestamp < '2026-11-01T00:00:00'
GROUP BY transit_timestamp, bus_route
ORDER BY transit_timestamp, bus_route        -- paged 50,000 rows at a time ($limit / $offset)""")
P("Scheduled trips per hour are computed from the stop-level schedule table by counting trip origins "
  "(`origin = '1'`) per route and hour for a representative Weekday, Saturday and Sunday "
  f"({', '.join(f'{k}: {v}' for k, v in C.SCHEDULE_DATES.items())}).")

# ---- 4 cleaning
H("4. Module 2 - Data Cleaning")
N(["Type coercion - timestamps parsed, counts converted to numeric; rows with no route or timestamp dropped "
   f"(missing values found: {cr.get('missing_values')}).",
   "Route-ID normalisation - upper-case, whitespace removed, '-SBS' suffix → '+' so that all sources join.",
   f"Duplicates - identical route + hour rows summed ({cr.get('duplicates_merged', 0):,} merged).",
   f"Negative counts clipped to zero ({cr.get('negative_values', 0)} found).",
   f"Hourly grid completion - every route gets a continuous hourly series; {cr.get('imputed_hours', 0):,} missing "
   "hours filled with 0 and flagged `imputed`.",
   f"Outlier capping - values above 3 × the route's 99.9th percentile capped ({cr.get('outliers_capped', 0):,} values).",
   f"Low-volume filter - routes with < 20 boardings/day removed ({len(cr.get('routes_dropped_low_ridership', []))} routes); "
   f"routes without a schedule removed ({len(cr.get('routes_without_schedule', []))}).",
   "Schedules - complete 24-hour x day-type grid; route length = 75th percentile of pattern lengths (ft → miles).",
   "Speeds - trip-weighted speed = Σ(distance × trips) / Σ(time × trips); values outside 1-45 mph discarded; "
   "hierarchical fill: route-dow-hour → route monthly average → route-type-hour median → global median.",
   "Reliability - wait assessment = Σ trips passing / Σ scheduled trips (overall and peak)."])
P(f"Result: {cr.get('clean_rows', 0):,} clean route-hours for {cr.get('routes_modelled', MAN['routes'])} routes "
  f"({cr.get('date_min', '')[:10]} → {cr.get('date_max', '')[:10]}).")

# ---- 5 feature engineering
H("5. Module 2b - Feature Engineering")
P("Granularity of the analytical table: **one row per route per clock hour** (America/New_York local time). "
  "Daily figures are sums of hours.")
T(["Group", "Feature", "Definition"], [
    ["Time", "hour, dow, month, weekofyear", "calendar parts of the timestamp"],
    ["Time", "is_weekend, is_holiday, day_type", "US/NY public holidays (holidays lib); holidays use the Sunday schedule"],
    ["Time", "is_am_peak, is_pm_peak, is_peak, is_night, is_summer", "06-10, 16-20 weekday peaks; 00-06 night; Jul-Aug"],
    ["Time", "hour_sin/cos, dow_sin/cos", "cyclical encodings sin(2πh/24), cos(2πh/24), etc."],
    ["Service", "trips", "scheduled trip starts on the route in that hour (by day type)"],
    ["Service", "speed_mph, trip_minutes", "hourly operating speed; trip time = 60·length/speed"],
    ["Route", "length_mi, n_stops, stop_density", "route length, stops, stops per mile"],
    ["Route", "route_type, borough, capacity", "Local / Limited / SBS / Express; capacity per vehicle type"],
    ["Route", "reliability, reliability_peak", "wait-assessment share"],
    ["KPI", "evasion_factor, est_riders", "1 / (1 - fare-evasion rate of the route type); est_riders = paid boardings × factor"],
    ["KPI", "load_per_trip", "est_riders / trips"],
    ["KPI", "occupancy", f"load_per_trip × peak-load factor ({C.PEAK_LOAD_FACTOR}) / capacity"],
    ["KPI", "productivity", "est_riders / revenue vehicle-hours (trips × trip_minutes / 60)"],
    ["KPI", "headway_min, avg_wait_min", "60 / trips, headway / 2"],
    ["KPI", "transfer_rate", "transfers / ridership"],
    ["Label", "perf_class", f"Underutilized (occ < {C.UNDERUTILIZED_MAX:.3f}), Balanced, Overcrowded (occ > {C.OVERCROWDED_MIN:.3f}) - thresholds calibrated from data"],
    ["Profile", "avg_daily_ridership, am/pm_peak_share, night_share, weekend_ratio, cv_hourly, trend_4w_pct, "
                "pct_hours_overcrowded/underutilized, riders_per_mile", "route-level aggregates for clustering & ranking"],
], [2.2, 6.0, 8.4], size=8.5)
H("5.1 Fare-evasion correction and threshold calibration", 2)
ev = MAN["assumptions"].get("fare_evasion_rates", {})
P("The hourly ridership table counts **paid** boardings (OMNY / MetroCard taps). MTA's own Bus Fare Evasion "
  "dataset reports that a large share of riders do not pay (latest four quarters: " +
  ", ".join(f"{k} {v:.1%}" for k, v in ev.items() if k in ("Local", "Select Bus Service", "Express")) +
  "). Load and crowding are therefore computed on estimated total riders = paid boardings / (1 - evasion "
  "rate). Forecasting still predicts paid boardings (the published quantity), and the factor is applied afterwards.")
qs = MAN["assumptions"].get("threshold_quantiles", [0.25, 0.9])
P(f"Because occupancy is an estimate (boardings, not on-board counts), fixed absolute cut-offs would label almost "
  f"every hour 'underutilised'. The class thresholds are therefore **calibrated on the training period**: "
  f"Underutilized = below the {qs[0]:.0%} quantile of service-hour occupancy ({C.UNDERUTILIZED_MAX:.3f}), "
  f"Overcrowded = above the {qs[1]:.0%} quantile ({C.OVERCROWDED_MIN:.3f}), Balanced in between. The optimiser "
  f"targets occupancy {C.TARGET_OCCUPANCY:.3f}. The calibrated values are saved to data/processed/thresholds.json "
  "and reused by the app and API.")
P("Vehicle capacity assumptions: " + ", ".join(f"{k} {v}" for k, v in C.VEHICLE_CAPACITY.items()) +
  ". These, the peak-load factor and the class thresholds are configurable in the configuration section of `backend/main.py`.")

# ---- 6 EDA
H("6. Module 3 - Exploratory Data Analysis")
T(["EDA method", "What it shows", "Output"], [
    ["Descriptive statistics (mean, std, quantiles, skewness, kurtosis)", "scale & shape of ridership, load, speed", "eda/eda_summary.json"],
    ["Hour-of-day curves per day type", "high-traffic time windows", "hourly curve figure"],
    ["Daily time series + 7-day rolling mean, holiday markers", "trend, seasonality, holiday dips", "daily trend figure"],
    ["Day-of-week box plots", "weekly pattern & variability", "box-plot figure"],
    ["Route density heatmap (route x hour)", "which routes are busy when", "heatmap figure"],
    ["Occupancy histogram with thresholds", "share of under/over-utilised service", "distribution figure"],
    ["Class share by hour (stacked bars)", "when crowding happens", "class-by-hour figure"],
    ["Spearman rank correlation", "monotonic relations between KPIs", "correlation heatmap"],
    ["IQR outlier rule on daily route ridership", "anomalous days (storms, holidays, detours)", "outlier stats"],
    ["Group comparison by borough / route type", "spatial and service-type differences", "bar charts"],
    ["Stop-set Jaccard overlap", "duplicated / overlapping routes", "overlap figure"],
    ["Under-utilisation screen (> 60 % of hours under-utilised)", "candidate routes for cuts/merges", "route list"],
], [6.2, 6.0, 4.4], size=8.5)
pw = E["peak_windows"]
B([f"{k}: peak hour {v['peak_hour']}:00 with ≈{v['peak_boardings']:,.0f} boardings/hour network-wide; top hours "
   f"{v['top_hours']}; ≈{v['daily_total']:,.0f} boardings/day." for k, v in pw.items()])
cd = E["class_distribution"]
P("Class distribution over all service hours: " + ", ".join(f"{k} {v:.1%}" for k, v in cd.items()) + ".")
P(f"IQR outliers: {E['iqr_outliers']['outlier_share']:.1%} of route-days; dates with most outliers: "
  + ", ".join(list(E["iqr_outliers"]["dates_with_most_outliers"])[:6]) + ".")
for k, cap in [("hourly_curve", "Figure 6.1 - Network hourly ridership by day type"),
               ("daily_trend", "Figure 6.2 - Daily ridership with 7-day rolling mean"),
               ("dow_box", "Figure 6.3 - Daily ridership by day of week"),
               ("route_heatmap", "Figure 6.4 - Route density heatmap (weekday)"),
               ("occupancy_distribution", "Figure 6.5 - Occupancy distribution and class thresholds"),
               ("class_by_hour", "Figure 6.6 - Performance class share by hour"),
               ("correlation", "Figure 6.7 - Spearman correlation of route KPIs"),
               ("borough_type", "Figure 6.8 - Ridership by borough and productivity by route type"),
               ("productivity_rank", "Figure 6.9 - Most and least productive routes"),
               ("speed_vs_load", "Figure 6.10 - Speed vs crowding"),
               ("overlap", "Figure 6.11 - Most overlapping route pairs")]:
    IMG(k, cap, 15.5 if k != "route_heatmap" else 13)

# ---- 7 preprocessing
H("7. Module 4 - Data Preprocessing")
sp = M["split"]
B([f"**Chronological split** - training {sp['train_start']} → day before {sp['cutoff']} ({sp['train_rows']:,} rows); "
   f"validation = last {C.VALIDATION_DAYS} days {sp['cutoff']} → {sp['valid_end']} ({sp['valid_rows']:,} rows). "
   "No random shuffling, so the evaluation mimics forecasting unseen future days.",
   "**Target (profile) encoding of route IDs** - `ProfileEncoder` learns, on the training period only, mean "
   "log-ridership per (route, day-of-week, hour), (route, day-type, hour), (route, hour), route, and mean "
   "occupancy per (route, day-type, hour). Unseen combinations fall back hierarchically.",
   "**Label encoding** - `route_code` from scikit-learn `LabelEncoder` (unknown routes = -1).",
   "**One-hot encoding** - route_type and borough with a fixed vocabulary.",
   "**Target transform** - forecasting target is log1p(ridership) to stabilise variance (skewed counts).",
   "**Scaling** - route-profile features for clustering: log1p on volume features then `StandardScaler` "
   "(z-score); `RobustScaler` available. Tree models (RF/XGBoost) do not need scaling.",
   f"**Class imbalance** - classifiers use balanced class weights / sample weights. Training class counts: "
   f"{cl['class_distribution_train']}."])
P(f"Final model matrix: {len(json.loads(json.dumps(cl['feature_importance'][cl['best']])))} features "
  "(calendar 14, service 8, encoded 6, one-hot 14).")

# ---- 8 models
H("8. Module 5 - Model Selection and Training")
H("8.1 Clustering - grouping routes with similar usage profiles", 2)
P("**Type of clustering:** (1) **KMeans** - partitional, centroid-based clustering (Euclidean distance, "
  "k-means++ initialisation, 50 restarts); (2) **DBSCAN** - density-based spatial clustering that also labels "
  "noise points, used here as an **outlier detector** for atypical routes. Both run on 15 standardised route-"
  "profile features: avg daily ridership, AM/PM peak share, night share, weekend ratio, mean & p90 occupancy, "
  "productivity, speed, length, stop density, reliability, daily trips, riders per mile, hourly CV.")
B([f"k selected by the best silhouette score for k ∈ [4, 10] (fewer than 4 segments is not actionable); "
   f"chosen **k = {km['k']}**, silhouette {km['silhouette']:.3f}, Davies-Bouldin {km['davies_bouldin']:.3f}, "
   f"Calinski-Harabasz {km['calinski_harabasz']:.0f}.",
   f"DBSCAN eps chosen at the knee of the k-distance curve (eps = {db['eps']:.2f}, min_samples = {db['min_samples']}) "
   f"→ {db['n_clusters']} dense cluster(s), {db['n_outliers']} outlier routes.",
   "Each KMeans cluster is auto-named from its centroid (e.g. High-Volume Trunk, Peak Commuter, Low-Demand, "
   "Slow Urban, Fast/Long-Haul) - names: " + "; ".join(f"{k}: {v}" for k, v in km["cluster_names"].items()) + ".",
   f"PCA (2 components, {sum(M['clustering']['pca_explained_variance']):.0%} variance) is used only for plotting."])
T(["k", "Inertia", "Silhouette", "Davies-Bouldin", "Calinski-Harabasz"],
  [[r["k"], f(r["inertia"], 0), f(r["silhouette"]), f(r["davies_bouldin"]), f(r["calinski_harabasz"], 0)]
   for r in M["clustering"]["k_selection"]], [2, 3.5, 3.5, 3.8, 3.8])
IMG("k_selection", "Figure 8.1 - KMeans k selection (elbow, silhouette, Davies-Bouldin)")
IMG("clusters_pca", "Figure 8.2 - KMeans segments and DBSCAN outliers (PCA projection)")

H("8.2 Classification - predicting route performance (Random Forest vs XGBoost)", 2)
P("Task: for every route-hour with scheduled service, predict the performance class "
  "**Underutilized / Balanced / Overcrowded** from information known in advance (calendar, schedule, speed, "
  "route attributes and historical profile encodings) - i.e. without seeing that hour's ridership.")
T(["Model", "Key hyper-parameters"], [
    ["RandomForestClassifier", "200 trees, max_depth 20, min_samples_leaf 5, max_features sqrt, "
                               "class_weight balanced_subsample, trained on a 400k-row sample"],
    ["XGBClassifier", "hist trees, 600 rounds with early stopping (40), depth 8, learning-rate 0.08, subsample 0.8, "
                      "colsample 0.8, multi:softprob, balanced sample weights"],
], [4.5, 12.1])
T(["Metric", "Random Forest", "XGBoost"],
  [[m, f(cl["RandomForest"][m]), f(cl["XGBoost"][m])] for m in ("accuracy", "balanced_accuracy", "f1_macro", "f1_weighted")]
  + [["train seconds", cl["RandomForest"]["train_seconds"], cl["XGBoost"]["train_seconds"]]], [6, 5.3, 5.3])
P(f"Selected classifier: **{cl['best']}** (highest macro-F1). Per-class F1 ({cl['best']}): " +
  ", ".join(f"{c} {cl[cl['best']]['report'][c]['f1-score']:.3f}" for c in C.CLASS_LABELS) + ".")
IMG("confusion", "Figure 8.3 - Normalised confusion matrices")

H("8.3 Forecasting - hourly ridership per route (XGBoost vs Random Forest vs baseline)", 2)
P("A regression model predicts log1p(boardings) for any route, date and hour, enabling real-time and future-date "
  "predictions. The seasonal-profile baseline predicts the training mean for the same route, weekday and hour.")
T(["Model", "MAE", "RMSE", "R²", "WAPE"],
  [[m, f(fc[m]["mae"], 2), f(fc[m]["rmse"], 2), f(fc[m]["r2"]), f"{fc[m]['wape']:.1%}"]
   for m in ("SeasonalProfileBaseline", "RandomForest", "XGBoost")], [5.6, 2.6, 2.6, 2.6, 3.2])
P(f"Selected forecaster: **{fc['best']}** (lowest MAE). XGBoost: 1,500 max rounds, early stopping 60, depth 9, "
  "learning-rate 0.05, subsample/colsample 0.8, L2 2.0. Random Forest: 150 trees, depth 22, max_features 0.5 "
  "on a 500k-row sample.")
IMG("importance", "Figure 8.4 - Top features (classifier and forecaster)")
IMG("forecast_fit", "Figure 8.5 - Validation period: forecast vs actual")
IMG("forecast_comparison", "Figure 8.6 - Forecast error comparison")

# ---- 9 inference
H("9. Module 6 - Inference and Route Suggestion")
P("`RouteRankerService.predict_day(date)` builds a 24-hour feature frame for every route, predicts hourly "
  "boardings with the forecaster, derives occupancy/productivity/wait from the schedule, and adds class "
  "probabilities from the classifier. Dates inside the data window also get the actual values for comparison.")
H("9.1 RouteRank score - how the 'best route' is chosen", 2)
P("For the selected time window each candidate route gets five components, each converted to a percentile "
  "rank (0-100) among the candidates and combined with user-adjustable weights:")
T(["Component", "Measure", "Default weight"], [
    ["Productivity", "predicted boardings per revenue vehicle-hour", "25 %"],
    ["Speed", "expected operating speed (mph) for that weekday/hour", "20 %"],
    ["Reliability", "wait-assessment share (peak value in peak windows)", "20 %"],
    ["Frequency", "scheduled buses per hour (→ shorter waits)", "15 %"],
    ["Comfort", "1 - mean P(Overcrowded) from the classifier", "20 %"],
], [3.5, 9.6, 3.5])
P("Score = Σ weightᵢ × percentileᵢ. Presets: Balanced, Rider (speed/reliability/comfort) and Planner (efficiency).")
H("9.2 Explanation ('why is it the best route today')", 2)
P("`explain()` produces a natural-language justification: the score margin over the runner-up and, for every "
  "component, the winner's value versus the median of the alternatives and its percentile, plus the expected "
  "wait time and load.")
H("9.3 Validation against other routes", 2)
P("`validate()` back-tests the recommendation: for the previous same-weekday dates in history, all candidates "
  "are re-scored using **actual** ridership; the report shows the recommended route's rank on actuals, the "
  "top-3 hit rate, the actual winner, and the predicted-vs-actual riders with the absolute percentage error.")
H("9.4 Journey mode", 2)
P("`find_routes_between(origin, destination)` returns every route that serves a stop matching both names "
  "(direct trips), so a rider can compare only the routes that make the journey.")

H("10. Optimisation Recommendations and Scenario Simulator")
B([f"**Increase frequency** in overcrowded hours: trips needed = ⌈ridership × {C.PEAK_LOAD_FACTOR} / "
   f"(capacity × {C.TARGET_OCCUPANCY})⌉.",
   f"**Reduce frequency** in under-utilised hours, never below {C.MIN_TRIPS_PER_HOUR} trips/hour (30-min policy headway).",
   "**Rebalance** when a route needs both (shift buses from off-peak to peak).",
   "**Merge** a mostly under-utilised route with a partner that serves > 40 % of its stops.",
   "**Split / short-turn** long routes (≥ 90th percentile length) with below-median reliability and crowding."])
T(["Network KPI (validation period)", "Current", "Optimised"], [
    ["Overcrowded route-hours", f"{imp['overcrowded_share_now']:.1%}", f"{imp['overcrowded_share_opt']:.1%}"],
    ["Underutilised route-hours", f"{imp['underutilized_share_now']:.1%}", f"{imp['underutilized_share_opt']:.1%}"],
    ["Balanced route-hours", f"{imp['balanced_share_now']:.1%}", f"{imp['balanced_share_opt']:.1%}"],
    ["Trips", f"{imp['trips_now']:,.0f}", f"{imp['trips_opt']:,.0f}"],
    ["Revenue vehicle-hours", f"{imp['veh_hours_now']:,.0f}", f"{imp['veh_hours_opt']:,.0f}"],
    ["Productivity (boardings/veh-h)", f"{imp['productivity_now']:.1f}", f"{imp['productivity_opt']:.1f}"],
    ["Mean wait (min)", f"{imp['mean_wait_now']:.1f}", f"{imp['mean_wait_opt']:.1f}"],
], [7.6, 4.5, 4.5])
P("The **Scenario Simulator** (`simulate_scenario`) applies demand change %, frequency multiplier, speed change "
  "(e.g. bus lanes) and vehicle capacity to chosen routes and hours and recomputes every KPI, showing current vs "
  "simulated loads (evaluation criterion 'optimisation effectiveness').")

# ---- 11 architecture
H("11. System Architecture")
P("**Architecture type: layered modular monolith with a shared service layer and two presentation channels** "
  "(Streamlit dashboard and FastAPI REST API). Batch ML pipeline (offline training) + online inference service. "
  "Storage is file-based (Parquet for data, joblib for models, JSON for metrics), so it runs on a laptop without "
  "a database server.")
IMG("architecture", "Figure 11.1 - System architecture", 16.5)
IMG("pipeline", "Figure 11.2 - End-to-end ML pipeline", 16.5)
T(["Layer", "Modules", "Responsibility"], [
    ["Configuration", "backend/main.py §1", "paths, data sources, time zones, assumptions"],
    ["Data ingestion", "backend/main.py §2", "SODA/SoQL pulls, server-side aggregation, caching, freshness check"],
    ["Processing", "backend/main.py §3-5", "cleaning, feature engineering / KPIs, preprocessing (encodings, split)"],
    ["EDA", "eda/main.py", "all exploratory analysis, 11 figures + eda_summary.json"],
    ["Modelling", "backend/main.py §6-7", "KMeans, DBSCAN, RF & XGBoost classifier/regressor"],
    ["Service", "backend/main.py §8-10", "optimisation, simulation, prediction, ranking, explanation, validation, GTFS"],
    ["Orchestration", "backend/main.py §11-12, §14", "figures, training pipeline, command-line interface"],
    ["Backend API", "backend/main.py §13", "FastAPI REST endpoints"],
    ["Frontend", "frontend/main.py", "shared UI helpers + 11 Streamlit pages + navigation"],
], [3.2, 6.4, 7.0], size=8.5)
P("Tech stack: Python 3, Pandas, NumPy, scikit-learn, XGBoost, Matplotlib, Seaborn, Plotly (MapLibre maps), "
  "Folium (optional), Streamlit, FastAPI/Uvicorn, holidays, PyArrow, python-docx, pytest.")
st = MAN["stage_seconds"]
T(["Pipeline stage", "Seconds"], [[k, v] for k, v in st.items()], [10, 6.6])

# ---- 12 frontend
H("12. Frontend Development and UI/UX")
T(["Page", "What it does"], [
    ["Network Overview", "KPI tiles, route map coloured by segment/predicted status/borough/type, segments table, today's forecast curve (IST hover), class mix by hour"],
    ["Best Route Today (Live)", "IST date & time picker, candidate set (journey A→B, borough/type, manual), weight presets; winner card, explanation, radar & score charts, hourly forecast, back-test validation; auto-refresh every 5 min for today"],
    ["Productivity Ranking", "league table by forecast date or historical average, top/bottom N, efficiency-vs-comfort bubble chart, CSV export"],
    ["Route Comparison", "2-6 routes: indicator table, radar, map, hourly forecasts, occupancy, speed, trips, history, weekday profile, class mix"],
    ["Historical Replay", "animated map (▶) of any past day hour-by-hour, actual vs forecast, hour inspector"],
    ["EDA Insights", "interactive EDA (curves, heatmap, distributions, correlations, overlaps, statistics) + static figures"],
    ["Scenario Simulator", "what-if sliders (demand, frequency, speed, vehicle) with before/after KPIs and charts"],
    ["Optimisation Actions", "network impact, action mix, trips per hour current vs optimised, action table, route drill-down, overlap list"],
    ["Model Performance", "clustering metrics & PCA, classifier metrics/confusion/report, forecaster metrics & validation plots, feature importance"],
    ["Data & Coverage", "sources with links, granularity, freshness check vs live API, completeness heatmap, GTFS upload analyser"],
    ["Pipeline & Architecture", "architecture & pipeline diagrams, stage timings, model figures"],
], [4.2, 12.4], size=8.5)
P("UI/UX principles applied:")
B(["Consistent gradient hero header per page, metric tiles at the top, details in tabs and expanders "
   "(progressive disclosure).",
   "Colour semantics fixed app-wide: grey = underutilised, green = balanced, red = overcrowded.",
   "Every chart is interactive (Plotly hover, zoom, legend toggle); tables use progress-bar columns.",
   "Live IST clock in the sidebar (updates every 30 s) with the corresponding network-local time; every "
   "forecast shows its generation time in IST.",
   "Material icons, grouped navigation (Overview, Analysis, Optimisation, Models & Data), wide layout, light/dark aware."])

SCREENS = ROOT / "reports" / "figures" / "screens"
shots = [("network_overview", "Network Overview"), ("best_route", "Best Route Today (Live) - IST date/time selection"),
         ("productivity_ranking", "Productivity Ranking"), ("route_comparison", "Route Comparison"),
         ("historical_replay", "Historical Replay"), ("scenario_simulator", "Scenario Simulator"),
         ("recommendations", "Optimisation Actions"), ("model_performance", "Model Performance"),
         ("data_coverage", "Data & Coverage"), ("eda_insights", "EDA Insights"),
         ("pipeline_architecture", "Pipeline & Architecture")]
if SCREENS.exists() and any(SCREENS.glob("*.png")):
    H("12.1 Application screenshots", 2)
    for i, (k, cap) in enumerate(shots, 1):
        if (SCREENS / f"{k}.png").exists():
            IMG(f"reports/figures/screens/{k}.png", f"Screenshot 12.{i} - {cap}", 15.5)

# ---- 13 backend
H("13. Backend Development (FastAPI)")
T(["Method & path", "Purpose"], [
    ["GET /api/health", "status, IST time, data window"],
    ["GET /api/routes", "route catalogue with segment and KPIs (filters: borough, route_type)"],
    ["GET /api/predict?route_id&date_ist", "24-hour forecast + class probabilities for a route"],
    ["GET /api/best-route?date_ist&time_ist&window&origin&destination&borough&preset", "best route, explanation, ranking, validation"],
    ["GET /api/ranking?date_ist&start_hour&end_hour", "RouteRank league table"],
    ["GET /api/recommendations?date_ist", "optimisation actions and impact"],
    ["POST /api/simulate", "scenario simulation (JSON body)"],
], [8.6, 8.0], size=8.5)
P("Interactive documentation is generated automatically at http://localhost:8000/docs.")

H("14. Time Handling (IST) and Real-Time Analysis")
B(["The user selects date and time in **IST** (Asia/Kolkata). The service converts it to the bus network's local "
   "time (America/New_York) because ridership patterns are local; both are displayed.",
   "Today's date triggers a real-time prediction for the current local hour; the Best Route page refreshes "
   "every 5 minutes and the clock every 30 seconds.",
   "Data freshness can be checked against the live API from the Data & Coverage page; re-running the pipeline "
   "downloads only the newest month (incremental).",
   "Holidays automatically switch to the Sunday schedule and the holiday flag in the models."])

H("15. Testing and Validation")
B(["`pytest` unit tests (18) cover route-ID normalisation, borough inference, holiday/day-type logic, IST "
   "conversion, cleaning (grid completion, duplicate merge), KPI and class computation, optimiser rules, "
   "simulator monotonicity, chronological split, overlap detection and an end-to-end GTFS analysis on a "
   "synthetic feed.",
   "Models are validated on a strictly later 28-day hold-out; forecasts are compared to a seasonal baseline; "
   "recommendations are back-tested on actual data."])

H("16. Deployment on Localhost and GitHub Structure")
code("""pip install -r requirements.txt
python backend/main.py train            # download data + train (≈ 35 min download + 15 min training)
python eda/main.py                       # exploratory data analysis -> eda/figures, eda/eda_summary.json
streamlit run frontend/main.py           # frontend dashboard: http://localhost:8501
python backend/main.py serve             # backend REST API:   http://localhost:8000/docs
pytest -q""")
code("""Route Ranker/
├── backend/main.py         ALL backend code: config, data collection, cleaning, features,
│                           preprocessing, clustering, classification, forecasting, optimisation,
│                           inference service, GTFS analyser, diagrams, pipeline, FastAPI, CLI
├── eda/main.py             ALL exploratory data analysis (+ eda/figures, eda/eda_summary.json)
├── frontend/main.py        ALL frontend code: UI helpers + 11 Streamlit pages + navigation
├── tests/                  pytest suite + page smoke test
├── reports/figures, reports/metrics   generated figures & JSON metrics
├── docs/                   this report + generator
├── scripts/                run_pipeline / run_app / run_api (.bat, .sh)
├── data/, models/          generated (git-ignored)
└── README.md, requirements.txt, pyproject.toml, LICENSE, .gitignore""")

H("17. Milestone Mapping (from the project brief)")
T(["Milestone / week", "Delivered"], [
    ["M1 W1 - collect & load GTFS, inspect", "backend/main.py §2 (MTA datasets incl. GTFS-derived routes/stops/schedules), manifest, Data & Coverage page"],
    ["M1 W2 - clean, time features, passengers per route per hour, route profiles", "backend/main.py §3-4"],
    ["M2 W3 - EDA, heatmaps, hourly curves, overlap/underuse", "eda/main.py, EDA Insights page"],
    ["M2 W4 - scaling, encoding, train/validation split", "backend/main.py §5"],
    ["M3 W5 - KMeans, DBSCAN, XGBoost, Random Forest, evaluation", "backend/main.py §6-7, Model Performance page"],
    ["M3 W6 - inference, merge/split/frequency suggestions, current vs optimised", "backend/main.py §8-9, Optimisation Actions page"],
    ["M4 W7 - Streamlit dashboard, GTFS upload, clusters, scenarios", "frontend/main.py (11 pages), GTFS analyser, Scenario Simulator"],
    ["M4 W8 - architecture docs, recommendations", "architecture & pipeline diagrams, README, this report"],
], [6.6, 10.0], size=8.5)

H("18. Limitations and Future Work")
B(["Occupancy is estimated from boardings with a peak-load factor; automatic passenger counter (APC) load data "
   "would make the crowding labels exact.",
   "The schedule is taken from representative dates of the latest bundle; schedule changes after that bundle "
   "are not reflected until the pipeline is re-run.",
   "Hourly ridership is published with a delay of about a week, so 'real-time' means a model forecast for the "
   "current hour; plugging the MTA Bus Time (SIRI) live feed with an API key would add live vehicle positions.",
   "Journey mode covers direct routes only; transfers could be added with a graph search over shared stops.",
   "Indian GTFS feeds can be analysed on the supply side today; once ridership/ETM ticket data for an Indian "
   "city is available the same pipeline can be retrained by changing the source list in `backend/main.py`."])

# ---- function reference
page_break()
H("Appendix A - Function Reference")
P("Generated automatically from the source code of the three main files (backend, eda, frontend): every "
  "section, class and function with its signature and docstring.")
MARKER = re.compile(r"^# (?:SECTION |PAGE: )?(.+?)\s*$")


def _section_markers(src: str) -> list[tuple[int, str]]:
    """(line number, title) of the '# ====' banner sections inside a main file."""
    lines, out = src.split("\n"), []
    for i in range(1, len(lines) - 1):
        if lines[i - 1].startswith("# ====") and lines[i + 1].startswith("# ===="):
            m = MARKER.match(lines[i])
            if m:
                out.append((i + 1, m.group(1)))
    return out


def _rows(nodes) -> list:
    """Table rows (signature, first docstring paragraph) for functions, classes and methods."""
    rows = []
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = f"{node.name}({ast.unparse(node.args)})"
            rows.append([f"`{sig}`", (ast.get_docstring(node) or "-").split("\n\n")[0].replace("\n", " ")])
        elif isinstance(node, ast.ClassDef):
            rows.append([f"`class {node.name}`", (ast.get_docstring(node) or "-").split("\n\n")[0].replace("\n", " ")])
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and (not sub.name.startswith("__") or sub.name == "__init__"):
                    sig = f"{node.name}.{sub.name}({ast.unparse(sub.args)})"
                    rows.append([f"`{sig}`", (ast.get_docstring(sub) or "-").split("\n\n")[0].replace("\n", " ")])
    return rows


for folder in ("backend", "eda", "frontend"):
    fpath = ROOT / folder / "main.py"
    src = fpath.read_text(encoding="utf-8")
    tree = ast.parse(src)
    H(f"{folder}/main.py", 2)
    mdoc = ast.get_docstring(tree)
    if mdoc:
        P(mdoc.split("\n\n")[0].replace("\n", " "), italic=True)
    marks = _section_markers(src)
    groups: dict = {}
    for node in tree.body:
        title = next((t for ln, t in reversed(marks) if ln < node.lineno), "Module")
        groups.setdefault(title, []).append(node)
    for title, nodes in groups.items():
        rows = _rows(nodes)
        if rows:
            if len(groups) > 1:
                H(title, 3)
            T(["Function / class", "Description"], rows, [7.6, 9.0], size=8)

H("Appendix B - Configuration and Assumptions")
T(["Setting", "Value"], [[k, json.dumps(v)] for k, v in MAN["assumptions"].items()], [6, 10.6])

# page-number footer
for sec in doc.sections:
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("RouteRanker - Technical Report  ·  page ")
    r.font.size = Pt(8)
    fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
    rr = OxmlElement("w:r"); t = OxmlElement("w:t"); t.text = "1"; rr.append(t); fld.append(rr)
    fp._p.append(fld)

doc.save(OUT)
print(f"saved {OUT} (pass {PASS})")


def to_pdf() -> Path | None:
    soffice = shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"
    if not Path(soffice).exists():
        return None
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(OUT.parent), str(OUT)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return OUT.with_suffix(".pdf")


def heading_pages(pdf: Path) -> list:
    import pymupdf
    d = pymupdf.open(pdf)
    texts = [pg.get_text() for pg in d]
    out, start = [], 2
    for text, lvl in HEADINGS:
        if lvl > 2:
            continue
        key = " ".join(text.split())[:45]
        for i in range(start, len(texts)):
            if key in " ".join(texts[i].split()):
                out.append([text, lvl, i + 1]); start = i
                break
    return out


if __name__ == "__main__":
    pdf = to_pdf()
    if pdf and PASS < 3:
        try:
            pages = heading_pages(pdf)
        except ImportError:
            pages = None
        if pages:
            old = TOC_JSON.read_text(encoding="utf-8") if TOC_JSON.exists() else ""
            TOC_JSON.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
            if PASS == 1 or json.dumps(pages, ensure_ascii=False) != old:
                subprocess.run([sys.executable, __file__], env={**os.environ, "RR_PASS": str(PASS + 1)}, check=True)
    elif pdf:
        print("saved", pdf)
