"""
Step 5: Exact route/date join & directional coverage reconciliation.
Produces matched utilization, unmatched boardings, and unmatched schedule tables.
"""
import os
import pandas as pd

PROCESSED_DIR = "data/processed"

def run():
    boardings = pd.read_parquet(os.path.join(PROCESSED_DIR, "boardings_clean.parquet"))
    schedule = pd.read_parquet(os.path.join(PROCESSED_DIR, "selected_schedule.parquet"))

    min_sched_date = schedule["service_date"].min()
    max_sched_date = schedule["service_date"].max()
    window_boardings = boardings[
        (boardings["date"] >= min_sched_date) & (boardings["date"] <= max_sched_date)
    ].copy()

    # Exact 1-to-1 join
    matched = window_boardings.merge(
        schedule,
        left_on=["route", "date"],
        right_on=["route", "service_date"],
        how="inner",
    )
    matched["rides_per_scheduled_trip"] = matched["rides"] / matched["scheduled_trips"]
    matched["rides_per_scheduled_hour"] = matched.apply(
        lambda r: (r["rides"] / r["scheduled_service_hours"])
        if pd.notna(r["scheduled_service_hours"]) and r["scheduled_service_hours"] > 0
        else None,
        axis=1,
    )

    # Anti-joins for directional reconciliation
    unmatched_boardings = window_boardings.merge(
        schedule[["route", "service_date"]],
        left_on=["route", "date"],
        right_on=["route", "service_date"],
        how="left",
    )
    unmatched_boardings = unmatched_boardings[unmatched_boardings["service_date"].isna()].drop(columns=["service_date"])

    unmatched_schedule = schedule.merge(
        window_boardings[["route", "date"]],
        left_on=["route", "service_date"],
        right_on=["route", "date"],
        how="left",
    )
    unmatched_schedule = unmatched_schedule[unmatched_schedule["date"].isna()].drop(columns=["date"])

    matched.to_parquet(os.path.join(PROCESSED_DIR, "matched_utilization.parquet"), index=False)
    unmatched_boardings.to_parquet(os.path.join(PROCESSED_DIR, "unmatched_boardings.parquet"), index=False)
    unmatched_schedule.to_parquet(os.path.join(PROCESSED_DIR, "unmatched_schedule.parquet"), index=False)

    print(
        f"[04_join] Matched: {len(matched)} | Unmatched boardings: {len(unmatched_boardings)} | "
        f"Unmatched schedule: {len(unmatched_schedule)}"
    )

if __name__ == "__main__":
    run()
