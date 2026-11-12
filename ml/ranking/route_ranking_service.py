"""
RouteRanker: Route Productivity Ranking Service
Implements Technical Specification v3.8 Section 10:
- Independent, transparent productivity indicators:
  1. Mean observed daily demand by day type (W, A, U)
  2. Scheduled daily trips from authentic GTFS
  3. Rides per scheduled trip = sum(matched rides) / sum(matched scheduled trips) [Ratio of sums]
  4. Scheduled service hours (assuming calibrated 0.75h = 45 min per trip duration)
  5. Rides per scheduled hour = sum(matched rides) / sum(matched scheduled hours) [Ratio of sums]
- Configurable eligibility gates: >=20 matched observed days and positive scheduled trips
- Clear unranked reasons for ineligible routes
- Transparent explainability of productivity values (not an overall route-quality score or removal justification)
"""

import os
import json
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
GTFS_DIR = os.path.join(RAW_DIR, "gtfs")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

class RouteRankingService:
    def __init__(self, min_observed_days=20, dev_cutoff="2026-05-31", assumed_trip_duration_hours=0.75):
        self.min_observed_days = min_observed_days
        self.dev_cutoff = dev_cutoff
        self.assumed_trip_duration_hours = assumed_trip_duration_hours
        self._cached_rankings = None

    def _compute_gtfs_scheduled_trips(self):
        cal_path = os.path.join(GTFS_DIR, "calendar.txt")
        trips_path = os.path.join(GTFS_DIR, "trips.txt")
        routes_path = os.path.join(GTFS_DIR, "routes.txt")
        
        cal = pd.read_csv(cal_path)
        trips = pd.read_csv(trips_path)
        routes = pd.read_csv(routes_path)
        bus_routes = set(routes[routes["route_type"] == 3]["route_id"].astype(str))

        # Use canonical active weekday service date in October 2026
        date_int = 20261005
        wk_cal = cal[(cal["start_date"] <= date_int) & (cal["end_date"] >= date_int) & (cal["monday"] == 1)]
        sat_cal = cal[(cal["start_date"] <= date_int) & (cal["end_date"] >= date_int) & (cal["saturday"] == 1)]
        sun_cal = cal[(cal["start_date"] <= date_int) & (cal["end_date"] >= date_int) & (cal["sunday"] == 1)]

        bus_trips = trips[trips["route_id"].astype(str).isin(bus_routes)]
        wk_m = bus_trips.merge(wk_cal, on="service_id")
        sat_m = bus_trips.merge(sat_cal, on="service_id")
        sun_m = bus_trips.merge(sun_cal, on="service_id")

        wk_counts = wk_m.groupby("route_id")["trip_id"].nunique().to_dict()
        sat_counts = sat_m.groupby("route_id")["trip_id"].nunique().to_dict()
        sun_counts = sun_m.groupby("route_id")["trip_id"].nunique().to_dict()

        route_names = {}
        for _, r in routes.iterrows():
            route_names[str(r["route_id"])] = str(r.get("route_long_name", f"Route {r['route_id']}"))

        return wk_counts, sat_counts, sun_counts, route_names

    def compute_rankings(self):
        wk_counts, sat_counts, sun_counts, route_names = self._compute_gtfs_scheduled_trips()
        
        bus_csv = os.path.join(RAW_DIR, "cta_ridership_bus_routes_daily.csv")
        df = pd.read_csv(bus_csv)
        df["date_dt"] = pd.to_datetime(df["date"])
        dev_df = df[df["date_dt"] <= self.dev_cutoff]

        rankings = []
        for r, grp in dev_df.groupby("route"):
            r_str = str(r)
            r_name = route_names.get(r_str, f"Route {r_str}")

            for dt, dt_name in [("W", "Weekday"), ("A", "Saturday"), ("U", "Sunday/Holiday")]:
                sub = grp[grp["daytype"] == dt]
                n_days = len(sub)
                tot_rides = int(sub["rides"].sum())

                if dt == "W":
                    sched_trips_per_day = int(wk_counts.get(r_str, 0))
                elif dt == "A":
                    sched_trips_per_day = int(sat_counts.get(r_str, 0))
                else:
                    sched_trips_per_day = int(sun_counts.get(r_str, 0))

                tot_sched_trips = sched_trips_per_day * n_days
                tot_sched_hours = round(tot_sched_trips * self.assumed_trip_duration_hours, 1)

                is_eligible = (n_days >= self.min_observed_days) and (tot_sched_trips > 0)

                mean_rides = round(tot_rides / n_days, 1) if n_days > 0 else 0
                rides_per_trip = round(tot_rides / tot_sched_trips, 2) if is_eligible else None
                rides_per_hour = round(tot_rides / tot_sched_hours, 2) if is_eligible else None

                unranked_reason = None
                if not is_eligible:
                    if n_days < self.min_observed_days:
                        unranked_reason = f"Insufficient observed days ({n_days}/{self.min_observed_days})"
                    else:
                        unranked_reason = "No scheduled GTFS trips found for day type"

                rankings.append({
                    "route_id": r_str,
                    "route_name": r_name,
                    "day_type": dt,
                    "day_type_name": dt_name,
                    "observed_days": n_days,
                    "total_rides": tot_rides,
                    "mean_daily_rides": mean_rides,
                    "scheduled_trips_per_day": sched_trips_per_day,
                    "scheduled_hours_per_day": round(sched_trips_per_day * self.assumed_trip_duration_hours, 1),
                    "rides_per_scheduled_trip": rides_per_trip,
                    "rides_per_scheduled_hour": rides_per_hour,
                    "is_eligible": is_eligible,
                    "unranked_reason": unranked_reason
                })

        rdf = pd.DataFrame(rankings)

        # Assign ranks within each eligible day type
        for dt in ["W", "A", "U"]:
            mask = (rdf["day_type"] == dt) & (rdf["is_eligible"])
            sub_ranked = rdf[mask].sort_values("rides_per_scheduled_hour", ascending=False)
            rdf.loc[mask, "productivity_rank"] = range(1, len(sub_ranked) + 1)

        self._cached_rankings = rdf
        # Save processed ranking table
        rank_out_path = os.path.join(PROCESSED_DIR, "route_productivity_rankings.csv")
        rdf.to_csv(rank_out_path, index=False)
        return rdf

    def get_rankings(self, day_type: str = "W", sort_by: str = "rides_per_scheduled_hour"):
        if self._cached_rankings is None:
            rank_path = os.path.join(PROCESSED_DIR, "route_productivity_rankings.csv")
            if os.path.exists(rank_path):
                self._cached_rankings = pd.read_csv(rank_path)
            else:
                self._cached_rankings = self.compute_rankings()

        dt = day_type.upper()
        sub = self._cached_rankings[self._cached_rankings["day_type"] == dt].copy()
        
        # Sort eligible first, then sort_by descending
        if sort_by in sub.columns:
            sub = sub.sort_values(by=["is_eligible", sort_by], ascending=[False, False])

        records = sub.replace({np.nan: None}).to_dict(orient="records")
        return {
            "day_type": dt,
            "sort_by": sort_by,
            "total_routes_evaluated": len(records),
            "eligible_count": int(sub["is_eligible"].sum()),
            "unranked_count": int((~sub["is_eligible"]).sum()),
            "assumptions": {
                "eligibility_minimum_days": self.min_observed_days,
                "assumed_mean_trip_duration_hours": self.assumed_trip_duration_hours,
                "formula_note": "Ratios are calculated as ratio of sums over matched dates: sum(rides) / sum(trips) and sum(rides) / sum(hours)."
            },
            "rankings": records
        }

route_ranking_service = RouteRankingService()

if __name__ == "__main__":
    res = route_ranking_service.compute_rankings()
    print(f"Route rankings generated: {len(res)} route-daytype records.")

