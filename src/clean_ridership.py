"""
Step 5: clean the Manhattan hourly ridership table.

Reads the raw monthly files in data/raw/ridership/ (never modified) and writes
data/processed/ridership_hourly_clean.parquet with columns:
    route, date, hour, ridership, transfers

What it does:
  1. Splits transit_timestamp (local New York time) into date and hour; casts counts to int.
  2. Checks for nulls, non-integer counts, negative values, transfers > ridership,
     and duplicate route-hour rows. Any failure stops the script.
  3. Applies the hand-made keep/drop list in src/route_decisions.csv. Every route code
     in the raw data must appear there, so new codes are never kept or dropped silently.
  4. Keeps zero-ridership rows (Step 9 decides which zeros mean "no bus running").
  5. Finds the last date with real ridership (any route > 0) and reports it.
  6. Plots total riders per day and flags days that differ sharply from the same
     weekday in nearby weeks.

Outputs:
  data/processed/ridership_hourly_clean.parquet
  reports/figures/daily_ridership.png
  reports/ridership_daily_flags.csv
  reports/ridership_cleaning_summary.json

Usage:
    python src/clean_ridership.py
"""

import json
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ridership"
OUT = ROOT / "data" / "processed" / "ridership_hourly_clean.parquet"
REPORTS = ROOT / "reports"
DECISIONS = Path(__file__).resolve().parent / "route_decisions.csv"

# A day is flagged when its total is this far from the median of the same weekday
# in the 3 weeks before and 3 weeks after.
WINDOW_WEEKS = 3
LOW, HIGH = 0.75, 1.25

# Public holidays in the 2026 study period (NYC Transit runs a holiday/Sunday-like schedule).
HOLIDAYS = {
    "2026-01-01": "New Year's Day",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-02-16": "Presidents' Day",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (observed)",
    "2026-07-04": "Independence Day",
    "2026-09-07": "Labor Day",
}

# Other known unusual days (checked against news reports).
EVENTS = {
    "2026-01-25": "Snowstorm (Jan 25-26, over a foot of snow; articulated buses pulled)",
    "2026-01-26": "Snowstorm (Jan 25-26, over a foot of snow; articulated buses pulled)",
    "2026-02-22": "Blizzard (Feb 22-23; city travel ban 9pm Sun - noon Mon, buses exempt)",
    "2026-02-23": "Blizzard (Feb 22-23; city travel ban 9pm Sun - noon Mon, buses exempt)",
    "2026-02-24": "Day after blizzard (likely recovery from Feb 22-23 storm)",
}


def load_raw() -> pd.DataFrame:
    files = sorted(RAW.glob("20??-??.csv"))
    if not files:
        raise SystemExit(f"No raw files in {RAW}")
    df = duckdb.sql(f"""
        SELECT CAST(transit_timestamp AS TIMESTAMP) AS ts,
               bus_route AS route,
               CAST(ridership AS DOUBLE) AS ridership,
               CAST(transfers AS DOUBLE) AS transfers
        FROM read_csv({[f.as_posix() for f in files]}, all_varchar = true)
    """).df()
    print(f"Loaded {len(df):,} rows from {len(files)} files "
          f"({files[0].name} .. {files[-1].name})")
    return df


def validate(df: pd.DataFrame) -> dict:
    checks = {
        "null_values": int(df[["ts", "route", "ridership", "transfers"]].isna().any(axis=1).sum()),
        "non_integer_counts": int(((df.ridership % 1 != 0) | (df.transfers % 1 != 0)).sum()),
        "negative_ridership": int((df.ridership < 0).sum()),
        "negative_transfers": int((df.transfers < 0).sum()),
        "transfers_gt_ridership": int((df.transfers > df.ridership).sum()),
        "duplicate_route_hours": int(df.duplicated(["route", "ts"]).sum()),
    }
    for k, v in checks.items():
        print(f"  {k:<24} {v}")
    bad = {k: v for k, v in checks.items() if v}
    if bad:
        raise SystemExit(f"Validation failed: {bad}")
    return checks


def apply_route_decisions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dec = pd.read_csv(DECISIONS, dtype=str).fillna("")
    totals = (df.groupby("route")
                .agg(ridership=("ridership", "sum"), transfers=("transfers", "sum"))
                .astype(int).reset_index())
    table = totals.merge(dec, on="route", how="outer", indicator=True)
    missing = table.loc[table._merge == "left_only", "route"].tolist()
    if missing:
        raise SystemExit(f"Route codes with no decision in {DECISIONS.name}: {missing}")
    table = table[table._merge == "both"].drop(columns="_merge")
    keep = set(table.loc[table.decision == "keep", "route"])
    print(f"  keep {len(keep)} routes, drop {sorted(set(table.route) - keep)}")
    return df[df.route.isin(keep)].copy(), table.sort_values(["decision", "route"])


def daily_flags(clean: pd.DataFrame) -> pd.DataFrame:
    pos = clean[clean.ridership > 0]
    d = clean.groupby("date", as_index=False)["ridership"].sum()
    d["routes_with_riders"] = d["date"].map(pos.groupby("date")["route"].nunique()).fillna(0).astype(int)
    d["date"] = pd.to_datetime(d["date"])
    d["weekday"] = d["date"].dt.day_name()
    key = d["date"].dt.strftime("%Y-%m-%d")
    d["holiday"] = key.map(HOLIDAYS).fillna("")
    d["event"] = key.map(EVENTS).fillna("")
    d["missing"] = d["ridership"] == 0

    # Reference = median of the same weekday in nearby weeks, using only ordinary days
    # (not missing, not holidays, not known events) so one bad day doesn't distort another.
    ordinary = d.loc[~d.missing & (d.holiday == "") & (d.event == "")].set_index("date")["ridership"]
    ref = []
    for day in d["date"]:
        same = [day + pd.Timedelta(weeks=k) for k in range(-WINDOW_WEEKS, WINDOW_WEEKS + 1) if k]
        ref.append(ordinary.reindex(same).dropna().median())
    d["same_weekday_median"] = ref
    d["ratio"] = (d["ridership"] / d["same_weekday_median"]).round(3)
    d["flag"] = ""
    d.loc[d.ratio < LOW, "flag"] = "low"
    d.loc[d.ratio > HIGH, "flag"] = "high"
    d.loc[d.missing, "flag"] = "missing"
    return d


def plot_daily(d: pd.DataFrame, last_real: pd.Timestamp, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(d["date"], d["ridership"] / 1e3, color="#3b6ea5", lw=1.2, label="Total riders")
    ax.plot(d["date"], d["same_weekday_median"] / 1e3, color="#aaaaaa", lw=1, ls="--",
            label=f"Median of same weekday (±{WINDOW_WEEKS} weeks)")
    f = d[d.flag != ""]
    ax.scatter(f["date"], f["ridership"] / 1e3, color="#d1495b", zorder=3, s=30,
               label=f"Flagged (<{LOW:.0%} or >{HIGH:.0%} of median, or missing)")
    m = d[d.missing]
    if len(m):
        ax.axvspan(m.date.min() - pd.Timedelta(hours=12), m.date.max() + pd.Timedelta(hours=12),
                   color="#d1495b", alpha=0.12, label="Missing data (all routes zero)")
    for _, r in f[~f.missing].iterrows():
        label = r.holiday or (r.event.split(" (")[0] if r.event else r.date.strftime("%d %b"))
        ax.annotate(label, (r.date, r.ridership / 1e3), xytext=(0, -14),
                    textcoords="offset points", ha="center", fontsize=7, color="#d1495b")
    ax.axvline(pd.Timestamp("2026-01-03"), color="#2e8b57", lw=0.8, ls=":")
    ax.text(pd.Timestamp("2026-01-03"), ax.get_ylim()[1] * 0.98, " matched window starts",
            fontsize=7, color="#2e8b57", va="top")
    ax.axvline(last_real, color="#2e8b57", lw=0.8, ls=":")
    ax.set_title("Manhattan bus ridership per day (kept routes)")
    ax.set_ylabel("Riders (thousands)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4, fontsize=8, frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    raw = load_raw()

    print("Validation:")
    checks = validate(raw)

    print("Route decisions:")
    kept, decisions = apply_route_decisions(raw)

    kept["date"] = kept["ts"].dt.date
    kept["hour"] = kept["ts"].dt.hour.astype("int8")
    kept["ridership"] = kept["ridership"].astype("int32")
    kept["transfers"] = kept["transfers"].astype("int32")
    clean = (kept[["route", "date", "hour", "ridership", "transfers"]]
             .sort_values(["route", "date", "hour"]).reset_index(drop=True))

    daily_routes = clean[clean.ridership > 0].groupby("date")["route"].nunique()
    last_real = pd.Timestamp(daily_routes.index.max())
    zero_rows = int((clean.ridership == 0).sum())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(OUT, index=False)
    print(f"Wrote {len(clean):,} rows -> {OUT.relative_to(ROOT)}")

    d = daily_flags(clean)
    plot_daily(d, last_real, REPORTS / "figures" / "daily_ridership.png")
    flagged = d[(d.flag != "") | (d.holiday != "") | (d.event != "")]
    flagged.assign(date=flagged.date.dt.date).to_csv(REPORTS / "ridership_daily_flags.csv", index=False)

    summary = {
        "raw_rows": len(raw),
        "clean_rows": len(clean),
        "first_date": str(clean.date.min()),
        "last_date_in_files": str(clean.date.max()),
        "last_date_with_ridership": str(last_real.date()),
        "missing_dates": [str(x.date()) for x in d.loc[d.missing, "date"]],
        "routes_kept": int(clean.route.nunique()),
        "zero_ridership_rows_kept": zero_rows,
        "zero_ridership_share": round(zero_rows / len(clean), 4),
        "validation": checks,
        "route_decisions": decisions.to_dict(orient="records"),
        "daily_flags": flagged.assign(date=flagged.date.dt.strftime("%Y-%m-%d"))
                              .to_dict(orient="records"),
    }
    (REPORTS / "ridership_cleaning_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print(f"Last date with ridership: {last_real.date()} "
          f"(files end {clean.date.max()})")
    print(f"Zero-ridership rows kept: {zero_rows:,} ({zero_rows / len(clean):.1%})")
    print("\nFlagged / holiday days:")
    print(flagged[["date", "weekday", "ridership", "routes_with_riders", "same_weekday_median",
                   "ratio", "flag", "holiday", "event"]]
          .assign(date=flagged.date.dt.date, same_weekday_median=flagged.same_weekday_median.round(),
                  event=flagged.event.str.split(" \\(").str[0])
          .to_string(index=False))


if __name__ == "__main__":
    main()
