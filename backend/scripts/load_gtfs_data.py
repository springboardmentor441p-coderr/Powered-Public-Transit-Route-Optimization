#!/usr/bin/env python3
"""
GTFS Data Loader for AI MetroFlow
Loads GTFS (General Transit Feed Specification) data into the database.

Usage:
    python load_gtfs_data.py /path/to/gtfs/directory
"""

import os
import sys
import csv
from datetime import datetime, time
from uuid import uuid4
from pathlib import Path
from typing import Dict, List, Optional
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import Base
from app.models.station import Station, Line
from app.models.train import Train, Schedule, TrainStatus, DayType


class GTFSLoader:
    """Loads GTFS data into the MetroFlow database."""

    def __init__(self, gtfs_path: str):
        self.gtfs_path = Path(gtfs_path)
        self.engine = None
        self.session_factory = None

        # Data caches
        self.agencies: Dict = {}
        self.routes: Dict = {}
        self.stops: Dict = {}
        self.trips: Dict = {}
        self.stop_times: List = []
        self.calendar: Dict = {}
        self.shapes: Dict = {}

    async def init_db(self):
        """Initialize database connection."""
        self.engine = create_async_engine(settings.DATABASE_URL, echo=True)
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()

    def load_gtfs_files(self):
        """Load all GTFS files into memory."""
        print("Loading GTFS files...")

        # Load agencies
        agencies_file = self.gtfs_path / "agency.txt"
        if agencies_file.exists():
            with open(agencies_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.agencies[row['agency_id']] = row
            print(f"  Loaded {len(self.agencies)} agencies")

        # Load routes
        routes_file = self.gtfs_path / "routes.txt"
        if routes_file.exists():
            with open(routes_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.routes[row['route_id']] = row
            print(f"  Loaded {len(self.routes)} routes")

        # Load stops
        stops_file = self.gtfs_path / "stops.txt"
        if stops_file.exists():
            with open(stops_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.stops[row['stop_id']] = row
            print(f"  Loaded {len(self.stops)} stops")

        # Load trips
        trips_file = self.gtfs_path / "trips.txt"
        if trips_file.exists():
            with open(trips_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.trips[row['trip_id']] = row
            print(f"  Loaded {len(self.trips)} trips")

        # Load stop_times
        stop_times_file = self.gtfs_path / "stop_times.txt"
        if stop_times_file.exists():
            with open(stop_times_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.stop_times.append(row)
            print(f"  Loaded {len(self.stop_times)} stop times")

        # Load calendar
        calendar_file = self.gtfs_path / "calendar.txt"
        if calendar_file.exists():
            with open(calendar_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.calendar[row['service_id']] = row
            print(f"  Loaded {len(self.calendar)} calendar entries")

        # Load shapes
        shapes_file = self.gtfs_path / "shapes.txt"
        if shapes_file.exists():
            with open(shapes_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    shape_id = row['shape_id']
                    if shape_id not in self.shapes:
                        self.shapes[shape_id] = []
                    self.shapes[shape_id].append(row)
            print(f"  Loaded {len(self.shapes)} shapes")

    async def create_lines_and_stations(self):
        """Create lines and stations from GTFS routes and stops."""
        async with self.session_factory() as session:
            # Create lines from routes
            line_map = {}
            for route_id, route in self.routes.items():
                # Check if line already exists
                result = await session.execute(
                    select(Line).where(Line.code == route_id[:10].upper())
                )
                line = result.scalar_one_or_none()

                if not line:
                    line = Line(
                        name=route.get('route_long_name', route.get('route_short_name', route_id)),
                        code=route_id[:10].upper(),
                        color=route.get('route_color', '0066CC') if route.get('route_color') else '0066CC',
                        description=route.get('route_desc', ''),
                    )
                    session.add(line)
                    await session.flush()

                line_map[route_id] = line

            # Create stations from stops
            station_map = {}
            for stop_id, stop in self.stops.items():
                # Find which route/line this stop belongs to
                # For simplicity, assign to first route found
                line_id = None
                for route_id, route in self.routes.items():
                    # Check if stop is used by this route
                    for st in self.stop_times:
                        if st['stop_id'] == stop_id and st['trip_id'] in self.trips:
                            if self.trips[st['trip_id']]['route_id'] == route_id:
                                line_id = line_map[route_id].id
                                break
                    if line_id:
                        break

                if not line_id and line_map:
                    # Default to first line
                    line_id = list(line_map.values())[0].id

                if line_id:
                    result = await session.execute(
                        select(Station).where(Station.code == stop_id[:10].upper())
                    )
                    station = result.scalar_one_or_none()

                    if not station:
                        station = Station(
                            line_id=line_id,
                            name=stop.get('stop_name', stop_id),
                            code=stop_id[:10].upper(),
                            order=0,  # Will update later
                            latitude=float(stop.get('stop_lat', 0)),
                            longitude=float(stop.get('stop_lon', 0)),
                            capacity=1000,
                            zone=stop.get('zone_id', '1'),
                            is_interchange=False,
                        )
                        session.add(station)
                        await session.flush()

                    station_map[stop_id] = station

            await session.commit()
            print(f"Created {len(line_map)} lines and {len(station_map)} stations")
            return line_map, station_map

    async def create_trains_and_schedules(self, line_map: Dict, station_map: Dict):
        """Create trains and schedules from GTFS trips and stop_times."""
        async with self.session_factory() as session:
            # Create trains from trips (one train per unique trip pattern)
            train_map = {}
            trip_to_train = {}

            for trip_id, trip in self.trips.items():
                route_id = trip['route_id']
                line = line_map.get(route_id)

                if line:
                    train_number = f"{line.code}-{trip_id[:8]}"

                    result = await session.execute(
                        select(Train).where(Train.train_number == train_number)
                    )
                    train = result.scalar_one_or_none()

                    if not train:
                        train = Train(
                            train_number=train_number,
                            line_id=line.id,
                            capacity=500,
                            status=TrainStatus.ACTIVE,
                        )
                        session.add(train)
                        await session.flush()

                    train_map[train_number] = train
                    trip_to_train[trip_id] = train

            # Create schedules from stop_times
            for stop_time in self.stop_times:
                trip_id = stop_time['trip_id']
                stop_id = stop_time['stop_id']

                train = trip_to_train.get(trip_id)
                station = station_map.get(stop_id)

                if train and station:
                    arrival_time = stop_time.get('arrival_time')
                    departure_time = stop_time.get('departure_time')

                    # Parse time (GTFS format: HH:MM:SS)
                    def parse_time(t):
                        if not t:
                            return None
                        try:
                            parts = t.split(':')
                            return time(int(parts[0]) % 24, int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
                        except:
                            return None

                    arrival = parse_time(arrival_time)
                    departure = parse_time(departure_time)

                    # Determine day type from calendar
                    service_id = self.trips.get(trip_id, {}).get('service_id')
                    day_type = DayType.WEEKDAY
                    if service_id and service_id in self.calendar:
                        cal = self.calendar[service_id]
                        if cal.get('saturday') == '1' and cal.get('sunday') == '0':
                            day_type = DayType.SATURDAY
                        elif cal.get('sunday') == '1' and cal.get('saturday') == '0':
                            day_type = DayType.SUNDAY

                    result = await session.execute(
                        select(Schedule).where(
                            Schedule.train_id == train.id,
                            Schedule.station_id == station.id,
                            Schedule.day_type == day_type,
                        )
                    )
                    schedule = result.scalar_one_or_none()

                    if not schedule:
                        schedule = Schedule(
                            train_id=train.id,
                            station_id=station.id,
                            arrival_time=arrival,
                            departure_time=departure,
                            day_type=day_type,
                            sequence=int(stop_time.get('stop_sequence', 0)),
                        )
                        session.add(schedule)

            await session.commit()
            print(f"Created {len(train_map)} trains and schedules")

    async def load_all(self):
        """Load all GTFS data."""
        await self.init_db()
        self.load_gtfs_files()

        line_map, station_map = await self.create_lines_and_stations()
        await self.create_trains_and_schedules(line_map, station_map)

        await self.close()
        print("GTFS data loading complete!")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python load_gtfs_data.py /path/to/gtfs/directory")
        sys.exit(1)

    gtfs_path = sys.argv[1]
    if not os.path.exists(gtfs_path):
        print(f"Error: GTFS path does not exist: {gtfs_path}")
        sys.exit(1)

    loader = GTFSLoader(gtfs_path)
    await loader.load_all()


if __name__ == "__main__":
    asyncio.run(main())