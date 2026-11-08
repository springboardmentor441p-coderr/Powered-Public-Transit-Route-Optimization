import os
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.app.db import SessionLocal, engine, Base
from backend.app.models import (
    Agency, Calendar, FeedInfo, Route, Trip, Stop, StopTime, Shape,
    Role, User, StationCrowd, TrainStatus, ScheduleScenario
)
from backend.scripts.seed_data import seed_roles, seed_admin

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

EXPECTED_COUNTS = {
    "agency.txt": 1,
    "calendar.txt": 1,
    "feed_info.txt": 1,
    "routes.txt": 315,
    "stops.txt": 6745,
    "trips.txt": 10128,
    "shapes.txt": 256823,
    "stop_times.txt": 429302,
}

audit_entries = []

def validate_counts(df: pd.DataFrame, filename: str):
    expected = EXPECTED_COUNTS.get(filename)
    actual = len(df)
    if expected is not None and actual != expected:
        print(f"[WARN] {filename}: expected {expected}, got {actual}")
    else:
        print(f"[OK] {filename}: {actual} rows")
    audit_entries.append((filename, expected, actual))
    return actual, expected

def ingest_agency(session: Session):
    path = DATA_DIR / "agency.txt"
    df = pd.read_csv(path, sep=",")
    validate_counts(df, "agency.txt")
    agencies = [
        Agency(
            agency_id=str(row["agency_id"]) if pd.notna(row.get("agency_id")) else "0",
            agency_name=str(row["agency_name"]),
            agency_url=str(row["agency_url"]),
            agency_timezone=str(row["agency_timezone"]),
            agency_lang=str(row["agency_lang"]) if pd.notna(row.get("agency_lang")) else None,
            agency_phone=str(row["agency_phone"]) if pd.notna(row.get("agency_phone")) else None,
            agency_fare_url=str(row["agency_fare_url"]) if pd.notna(row.get("agency_fare_url")) else None,
            agency_email=str(row["agency_email"]) if pd.notna(row.get("agency_email")) else None,
        )
        for _, row in df.iterrows()
    ]
    session.bulk_save_objects(agencies)
    session.commit()

def ingest_calendar(session: Session):
    path = DATA_DIR / "calendar.txt"
    df = pd.read_csv(path, sep=",")
    validate_counts(df, "calendar.txt")
    calendars = []
    for _, row in df.iterrows():
        calendars.append(
            Calendar(
                service_id=str(row["service_id"]),
                monday=bool(int(row["monday"])),
                tuesday=bool(int(row["tuesday"])),
                wednesday=bool(int(row["wednesday"])),
                thursday=bool(int(row["thursday"])),
                friday=bool(int(row["friday"])),
                saturday=bool(int(row["saturday"])),
                sunday=bool(int(row["sunday"])),
                start_date=pd.to_datetime(str(row["start_date"]), format="%Y%m%d").date(),
                end_date=pd.to_datetime(str(row["end_date"]), format="%Y%m%d").date(),
            )
        )
    session.bulk_save_objects(calendars)
    session.commit()

def ingest_feed_info(session: Session):
    path = DATA_DIR / "feed_info.txt"
    df = pd.read_csv(path, sep=",")
    validate_counts(df, "feed_info.txt")
    feeds = []
    for _, row in df.iterrows():
        feeds.append(
            FeedInfo(
                feed_publisher_name=str(row["feed_publisher_name"]),
                feed_publisher_url=str(row["feed_publisher_url"]) if pd.notna(row.get("feed_publisher_url")) else None,
                feed_lang=str(row["feed_lang"]) if pd.notna(row.get("feed_lang")) else None,
                default_lang=str(row["default_lang"]) if pd.notna(row.get("default_lang")) else None,
                feed_version=str(row["feed_version"]) if pd.notna(row.get("feed_version")) else None,
                feed_contact_email=str(row["feed_contact_email"]) if pd.notna(row.get("feed_contact_email")) else None,
            )
        )
    session.bulk_save_objects(feeds)
    session.commit()

def ingest_routes(session: Session):
    path = DATA_DIR / "routes.txt"
    df = pd.read_csv(path, sep=",")
    validate_counts(df, "routes.txt")
    routes = []
    for _, row in df.iterrows():
        routes.append(
            Route(
                route_id=str(row["route_id"]),
                agency_id=str(row["agency_id"]),
                route_short_name=str(row["route_short_name"]) if pd.notna(row.get("route_short_name")) else None,
                route_long_name=str(row["route_long_name"]) if pd.notna(row.get("route_long_name")) else None,
                route_desc=str(row["route_desc"]) if pd.notna(row.get("route_desc")) else None,
                route_type=int(row["route_type"]),
                route_url=str(row["route_url"]) if pd.notna(row.get("route_url")) else None,
                route_color=str(row["route_color"]) if pd.notna(row.get("route_color")) else None,
                route_text_color=str(row["route_text_color"]) if pd.notna(row.get("route_text_color")) else None,
                route_sort_order=int(row["route_sort_order"]) if pd.notna(row.get("route_sort_order")) else None,
            )
        )
    session.bulk_save_objects(routes)
    session.commit()

def ingest_stops(session: Session):
    path = DATA_DIR / "stops.txt"
    df = pd.read_csv(path, sep=",")
    validate_counts(df, "stops.txt")
    stops = []
    for _, row in df.iterrows():
        stops.append(
            Stop(
                stop_id=str(row["stop_id"]),
                stop_code=str(row["stop_code"]) if pd.notna(row.get("stop_code")) else None,
                stop_name=str(row["stop_name"]),
                stop_desc=str(row["stop_desc"]) if pd.notna(row.get("stop_desc")) else None,
                stop_lat=float(row["stop_lat"]),
                stop_lon=float(row["stop_lon"]),
                zone_id=str(row["zone_id"]) if pd.notna(row.get("zone_id")) else None,
                stop_url=str(row["stop_url"]) if pd.notna(row.get("stop_url")) else None,
                location_type=int(row["location_type"]) if pd.notna(row.get("location_type")) else None,
                parent_station=str(row["parent_station"]) if pd.notna(row.get("parent_station")) else None,
                wheelchair_boarding=int(row["wheelchair_boarding"]) if pd.notna(row.get("wheelchair_boarding")) else None,
            )
        )
    session.bulk_save_objects(stops)
    session.commit()

def ingest_trips(session: Session):
    path = DATA_DIR / "trips.txt"
    df = pd.read_csv(path, sep=",")
    validate_counts(df, "trips.txt")
    trips = []
    for _, row in df.iterrows():
        trips.append(
            Trip(
                trip_id=str(row["trip_id"]),
                route_id=str(row["route_id"]),
                service_id=str(row["service_id"]),
                trip_headsign=str(row["trip_headsign"]) if pd.notna(row.get("trip_headsign")) else None,
                trip_short_name=str(row["trip_short_name"]) if pd.notna(row.get("trip_short_name")) else None,
                direction_id=int(row["direction_id"]) if pd.notna(row.get("direction_id")) else None,
                block_id=str(row["block_id"]) if pd.notna(row.get("block_id")) else None,
                shape_id=str(row["shape_id"]) if pd.notna(row.get("shape_id")) else None,
                wheelchair_accessible=int(row["wheelchair_accessible"]) if pd.notna(row.get("wheelchair_accessible")) else None,
                bikes_allowed=int(row["bikes_allowed"]) if pd.notna(row.get("bikes_allowed")) else None,
            )
        )
    session.bulk_save_objects(trips)
    session.commit()

def ingest_stop_times_chunked(engine):
    path = DATA_DIR / "stop_times.txt"
    total = 0
    # Process in chunks of 50000 rows
    for chunk in pd.read_csv(path, sep=",", chunksize=50000):
        chunk["trip_id"] = chunk["trip_id"].astype(str)
        chunk["stop_id"] = chunk["stop_id"].astype(str)
        chunk["arrival_time"] = chunk["arrival_time"].astype(str)
        chunk["departure_time"] = chunk["departure_time"].astype(str)
        chunk["stop_sequence"] = chunk["stop_sequence"].astype(int)
        chunk.to_sql("stop_times", con=engine, if_exists="append", index=False)
        total += len(chunk)
    validate_counts(range(total), "stop_times.txt")
    print(f"[OK] stop_times.txt: {total} rows ingested")

def ingest_shapes_chunked(engine):
    path = DATA_DIR / "shapes.txt"
    total = 0
    for chunk in pd.read_csv(path, sep=",", chunksize=50000):
        chunk["shape_id"] = chunk["shape_id"].astype(str)
        chunk["shape_pt_lat"] = chunk["shape_pt_lat"].astype(float)
        chunk["shape_pt_lon"] = chunk["shape_pt_lon"].astype(float)
        chunk["shape_pt_sequence"] = chunk["shape_pt_sequence"].astype(int)
        chunk.to_sql("shapes", con=engine, if_exists="append", index=False)
        total += len(chunk)
    validate_counts(range(total), "shapes.txt")
    print(f"[OK] shapes.txt: {total} rows ingested")

def seed_operational_metro_data(session: Session):
    """Seed sample real-time crowd and operational monitoring data for MetroFlow."""
    # Check if already seeded
    if session.query(StationCrowd).first() is not None:
        print("[INFO] Operational metro data already seeded.")
        return

    print("[INFO] Seeding operational crowd and train status data...")
    stops = session.query(Stop).limit(30).all()
    crowd_records = []
    
    import random
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    
    for stop in stops:
        density = round(random.uniform(25.0, 95.0), 1)
        if density >= 85.0:
            level = "CRITICAL"
        elif density >= 70.0:
            level = "HIGH"
        elif density >= 45.0:
            level = "MODERATE"
        else:
            level = "LOW"
            
        inflow = round(density * 1.5 + random.uniform(-5, 10), 1)
        outflow = round(density * 1.3 + random.uniform(-5, 8), 1)
        congestion = round(density / 100.0, 2)
        platform_count = int(density * 4.2)
        
        crowd_records.append(
            StationCrowd(
                stop_id=stop.stop_id,
                timestamp=now_iso,
                inflow_rate=inflow,
                outflow_rate=outflow,
                passenger_density_percent=density,
                crowd_level=level,
                platform_crowd_count=platform_count,
                congestion_index=congestion
            )
        )
    session.bulk_save_objects(crowd_records)
    session.commit()

    # Seed train status
    trips = session.query(Trip).limit(20).all()
    train_statuses = []
    for idx, trip in enumerate(trips):
        is_delayed = (idx % 4 == 0)
        delay = random.randint(3, 18) if is_delayed else 0
        status_val = "CRITICAL_DELAY" if delay >= 15 else ("DELAYED" if delay > 0 else "ON_TIME")
        occupancy = round(random.uniform(40.0, 98.0), 1)
        
        train_statuses.append(
            TrainStatus(
                trip_id=trip.trip_id,
                train_number=f"TR-{100 + idx}",
                route_id=trip.route_id,
                status=status_val,
                delay_minutes=delay,
                occupancy_rate=occupancy,
                updated_at=now_iso
            )
        )
    session.bulk_save_objects(train_statuses)
    session.commit()
    print("[OK] Operational MetroFlow data seeded.")

def main():
    print("[START] Beginning GTFS ingestion and schema setup...")
    # Create tables
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        # Seed users & roles first
        seed_roles(session)
        seed_admin(session)

        # Clear existing GTFS tables before fresh load
        for tbl in ["agencies", "calendar", "feed_info", "routes", "stops", "trips", "stop_times", "shapes", "station_crowd", "train_status"]:
            try:
                session.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        session.commit()

        print("[INGEST] Ingesting Agency...")
        ingest_agency(session)
        print("[INGEST] Ingesting Calendar...")
        ingest_calendar(session)
        print("[INGEST] Ingesting Feed Info...")
        ingest_feed_info(session)
        print("[INGEST] Ingesting Routes...")
        ingest_routes(session)
        print("[INGEST] Ingesting Stops...")
        ingest_stops(session)
        print("[INGEST] Ingesting Trips...")
        ingest_trips(session)
        print("[INGEST] Ingesting Stop Times (chunked)...")
        ingest_stop_times_chunked(engine)
        print("[INGEST] Ingesting Shapes (chunked)...")
        ingest_shapes_chunked(engine)

        # Seed initial operational MetroFlow crowd and train data
        seed_operational_metro_data(session)

        # Generate audit report
        report_path = Path(__file__).resolve().parents[2] / "DATASET_AUDIT_REPORT.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# GTFS Dataset Audit Report\n\n")
            f.write("## Summary of file row counts\n\n")
            f.write("| File | Expected Rows | Actual Rows | Status |\n")
            f.write("|------|---------------|------------|--------|\n")
            for filename, expected, actual in audit_entries:
                status = "OK" if expected is None or expected == actual else "MISMATCH"
                f.write(f"| {filename} | {expected if expected is not None else '-'} | {actual} | {status} |\n")
        print("[DONE] GTFS ingestion and operational data initialization completed successfully.")
    except Exception as e:
        session.rollback()
        print("[ERROR]", e)
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()
