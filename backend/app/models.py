"""SQLAlchemy models for GTFS and authentication.
All tables follow the GTFS spec and include necessary constraints.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Date, Time, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from .db import Base

# ---------------------------------------------------------------------------
# Authentication models
# ---------------------------------------------------------------------------
class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # admin, operator

    users = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    role = relationship("Role", back_populates="users")

# ---------------------------------------------------------------------------
# GTFS core tables (subset needed for milestones)
# ---------------------------------------------------------------------------
class Agency(Base):
    __tablename__ = "agencies"
    agency_id = Column(String, primary_key=True)
    agency_name = Column(String, nullable=False)
    agency_url = Column(String, nullable=False)
    agency_timezone = Column(String, nullable=False)
    agency_lang = Column(String, nullable=True)
    agency_phone = Column(String, nullable=True)
    agency_fare_url = Column(String, nullable=True)
    agency_email = Column(String, nullable=True)

class Calendar(Base):
    __tablename__ = "calendar"
    service_id = Column(String, primary_key=True)
    monday = Column(Boolean, nullable=False)
    tuesday = Column(Boolean, nullable=False)
    wednesday = Column(Boolean, nullable=False)
    thursday = Column(Boolean, nullable=False)
    friday = Column(Boolean, nullable=False)
    saturday = Column(Boolean, nullable=False)
    sunday = Column(Boolean, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

class FeedInfo(Base):
    __tablename__ = "feed_info"
    feed_publisher_name = Column(String, primary_key=True)
    feed_publisher_url = Column(String)
    feed_lang = Column(String)
    default_lang = Column(String)
    feed_version = Column(String)
    feed_contact_email = Column(String)

class Route(Base):
    __tablename__ = "routes"
    route_id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.agency_id"), nullable=False)
    route_short_name = Column(String, nullable=True)
    route_long_name = Column(String, nullable=True)
    route_desc = Column(String, nullable=True)
    route_type = Column(Integer, nullable=False)
    route_url = Column(String, nullable=True)
    route_color = Column(String, nullable=True)
    route_text_color = Column(String, nullable=True)
    route_sort_order = Column(Integer, nullable=True)

    agency = relationship("Agency")
    trips = relationship("Trip", back_populates="route")

class Trip(Base):
    __tablename__ = "trips"
    trip_id = Column(String, primary_key=True)
    route_id = Column(String, ForeignKey("routes.route_id"), nullable=False)
    service_id = Column(String, ForeignKey("calendar.service_id"), nullable=False)
    trip_headsign = Column(String, nullable=True)
    trip_short_name = Column(String, nullable=True)
    direction_id = Column(Integer, nullable=True)
    block_id = Column(String, nullable=True)
    shape_id = Column(String, nullable=True)
    wheelchair_accessible = Column(Integer, nullable=True)
    bikes_allowed = Column(Integer, nullable=True)

    route = relationship("Route", back_populates="trips")
    stop_times = relationship("StopTime", back_populates="trip")

class Stop(Base):
    __tablename__ = "stops"
    stop_id = Column(String, primary_key=True)
    stop_code = Column(String, nullable=True)
    stop_name = Column(String, nullable=False)
    stop_desc = Column(String, nullable=True)
    stop_lat = Column(Float, nullable=False)
    stop_lon = Column(Float, nullable=False)
    zone_id = Column(String, nullable=True)
    stop_url = Column(String, nullable=True)
    location_type = Column(Integer, nullable=True)
    parent_station = Column(String, nullable=True)
    wheelchair_boarding = Column(Integer, nullable=True)

    stop_times = relationship("StopTime", back_populates="stop")

class StopTime(Base):
    __tablename__ = "stop_times"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String, ForeignKey("trips.trip_id"), nullable=False)
    arrival_time = Column(String, nullable=False)  # stored as HH:MM:SS, may exceed 24h
    departure_time = Column(String, nullable=False)
    stop_id = Column(String, ForeignKey("stops.stop_id"), nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    stop_headsign = Column(String, nullable=True)
    pickup_type = Column(Integer, nullable=True)
    drop_off_type = Column(Integer, nullable=True)
    shape_dist_traveled = Column(Float, nullable=True)
    timepoint = Column(Integer, nullable=True)

    trip = relationship("Trip", back_populates="stop_times")
    stop = relationship("Stop", back_populates="stop_times")

    __table_args__ = (
        Index("ix_stop_times_trip_stop_seq", "trip_id", "stop_sequence"),
    )

class Shape(Base):
    __tablename__ = "shapes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    shape_id = Column(String, nullable=False, index=True)
    shape_pt_lat = Column(Float, nullable=False)
    shape_pt_lon = Column(Float, nullable=False)
    shape_pt_sequence = Column(Integer, nullable=False)
    shape_dist_traveled = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("shape_id", "shape_pt_sequence", name="uq_shape_point"),
        Index("ix_shapes_shape_id_seq", "shape_id", "shape_pt_sequence"),
    )

# ---------------------------------------------------------------------------
# MetroFlow Operational, Monitoring & Scheduling Models (Milestones 1 & 2)
# ---------------------------------------------------------------------------
class StationCrowd(Base):
    __tablename__ = "station_crowd"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stop_id = Column(String, ForeignKey("stops.stop_id"), nullable=False, index=True)
    timestamp = Column(String, nullable=False, index=True)
    inflow_rate = Column(Float, default=0.0)  # Passengers/min
    outflow_rate = Column(Float, default=0.0)  # Passengers/min
    passenger_density_percent = Column(Float, nullable=False)  # 0 to 100%
    crowd_level = Column(String, nullable=False)  # LOW, MODERATE, HIGH, CRITICAL
    platform_crowd_count = Column(Integer, default=0)
    congestion_index = Column(Float, default=0.0)  # 0.0 to 1.0

    stop = relationship("Stop")

class TrainStatus(Base):
    __tablename__ = "train_status"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String, ForeignKey("trips.trip_id"), nullable=False, index=True)
    train_number = Column(String, nullable=False)
    route_id = Column(String, ForeignKey("routes.route_id"), nullable=False)
    current_station_id = Column(String, ForeignKey("stops.stop_id"), nullable=True)
    status = Column(String, nullable=False, default="ON_TIME")  # ON_TIME, DELAYED, CRITICAL_DELAY
    delay_minutes = Column(Integer, default=0)
    occupancy_rate = Column(Float, default=0.0)  # 0 to 100%
    updated_at = Column(String, nullable=False)

    trip = relationship("Trip")
    route = relationship("Route")
    current_station = relationship("Stop")

class ScheduleScenario(Base):
    __tablename__ = "schedule_scenarios"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_name = Column(String, nullable=False)
    route_id = Column(String, ForeignKey("routes.route_id"), nullable=False)
    target_headway_minutes = Column(Integer, nullable=False)
    peak_start_time = Column(String, default="08:00:00")
    peak_end_time = Column(String, default="10:00:00")
    additional_trains_recommended = Column(Integer, default=0)
    status = Column(String, default="PROPOSED")  # PROPOSED, APPROVED, APPLIED
    created_at = Column(String, nullable=False)

    route = relationship("Route")

# ---------------------------------------------------------------------------
# Milestone 3: Alerts, Notifications, Emergency Announcements & Updates
# ---------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)  # SERVICE_ACTIVITY, CONGESTION_INDICATOR, SCHEDULE_CHANGE, DELAY, EMERGENCY, SYSTEM_EVENT
    severity = Column(String, nullable=False, default="INFO")  # INFO, WARNING, CRITICAL
    status = Column(String, nullable=False, default="ACTIVE")  # ACTIVE, ACKNOWLEDGED, RESOLVED
    target_stop_id = Column(String, ForeignKey("stops.stop_id"), nullable=True)
    target_route_id = Column(String, ForeignKey("routes.route_id"), nullable=True)
    message = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    acknowledged_by = Column(String, nullable=True)
    resolved_at = Column(String, nullable=True)

    target_stop = relationship("Stop")
    target_route = relationship("Route")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for broadcast
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    category = Column(String, nullable=False, default="GENERAL")
    severity = Column(String, nullable=False, default="INFO")  # INFO, WARNING, CRITICAL
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(String, nullable=False)

    user = relationship("User")

class EmergencyAnnouncement(Base):
    __tablename__ = "emergency_announcements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="CRITICAL")  # MODERATE, SEVERE, CRITICAL
    affected_routes = Column(String, nullable=True)  # comma-separated route_ids
    affected_stops = Column(String, nullable=True)   # comma-separated stop_ids
    is_active = Column(Boolean, default=True, nullable=False)
    published_by = Column(String, nullable=False)
    published_at = Column(String, nullable=False)
    deactivated_at = Column(String, nullable=True)

class ScheduleUpdate(Base):
    __tablename__ = "schedule_updates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String, ForeignKey("routes.route_id"), nullable=False)
    trip_id = Column(String, ForeignKey("trips.trip_id"), nullable=True)
    update_type = Column(String, nullable=False)  # DELAY, CANCELLATION, EXTRA_SERVICE, REROUTE
    description = Column(String, nullable=False)
    delay_minutes = Column(Integer, default=0)
    status = Column(String, default="PUBLISHED")  # PENDING, PUBLISHED, RESOLVED
    created_by = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)

    route = relationship("Route")
    trip = relationship("Trip")



