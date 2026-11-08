# MetroFlow Data Dictionary

## Overview
This document specifies all tables, fields, data types, constraints, and operational descriptions in the MetroFlow transit intelligence database.

---

### 1. Static GTFS Tables

#### Table: `agencies`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `agency_id` | VARCHAR | PRIMARY KEY | Unique GTFS operating authority identifier |
| `agency_name` | VARCHAR | NOT NULL | Official authority name (e.g., PMPML) |
| `agency_url` | VARCHAR | NOT NULL | Official agency website |
| `agency_timezone` | VARCHAR | NOT NULL | Local timezone string (e.g., Asia/Kolkata) |
| `agency_lang` | VARCHAR | NULLABLE | Agency primary communication language |
| `agency_phone` | VARCHAR | NULLABLE | Passenger contact phone number |

#### Table: `calendars`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `service_id` | VARCHAR | PRIMARY KEY | Service schedule key (e.g., WEEKDAY) |
| `monday` - `sunday` | INTEGER | NOT NULL | 1 if active, 0 if inactive |
| `start_date` | VARCHAR | NOT NULL | Validity start date (YYYYMMDD) |
| `end_date` | VARCHAR | NOT NULL | Validity end date (YYYYMMDD) |

#### Table: `routes`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `route_id` | VARCHAR | PRIMARY KEY | Line identifier |
| `agency_id` | VARCHAR | FOREIGN KEY (`agencies.agency_id`) | Agency reference |
| `route_short_name`| VARCHAR | NULLABLE | Short public route designation (e.g. 100) |
| `route_long_name` | VARCHAR | NULLABLE | Full descriptive line route name |
| `route_type` | INTEGER | NOT NULL | GTFS route type (3 = Bus Transit) |
| `route_color` | VARCHAR | NULLABLE | Hex color code for maps/visualizations |

#### Table: `stops`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `stop_id` | VARCHAR | PRIMARY KEY | Unique station or stop code |
| `stop_name` | VARCHAR | NOT NULL | Passenger-facing station/stop name |
| `stop_lat` | FLOAT | NOT NULL | Latitude (WGS 84 coordinate) |
| `stop_lon` | FLOAT | NOT NULL | Longitude (WGS 84 coordinate) |

#### Table: `trips`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `trip_id` | VARCHAR | PRIMARY KEY | Unique scheduled transit trip |
| `route_id` | VARCHAR | FOREIGN KEY (`routes.route_id`) | Line reference |
| `service_id` | VARCHAR | FOREIGN KEY (`calendars.service_id`) | Calendar service pattern |
| `trip_headsign` | VARCHAR | NULLABLE | Destination displayed on train/bus |
| `direction_id` | INTEGER | NULLABLE | 0 for outbound, 1 for inbound |
| `shape_id` | VARCHAR | NULLABLE | Geographic path reference |

#### Table: `stop_times`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY (AUTOINCREMENT) | Surrogate primary key |
| `trip_id` | VARCHAR | FOREIGN KEY (`trips.trip_id`) | Trip reference |
| `stop_id` | VARCHAR | FOREIGN KEY (`stops.stop_id`) | Visited station reference |
| `arrival_time` | VARCHAR | NOT NULL | Scheduled arrival (HH:MM:SS) |
| `departure_time` | VARCHAR | NOT NULL | Scheduled departure (HH:MM:SS) |
| `stop_sequence` | INTEGER | NOT NULL | Sequence index along trip path |

---

### 2. Operational & Security Tables

#### Table: `users`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | User surrogate key |
| `email` | VARCHAR | UNIQUE, NOT NULL | Login credential |
| `hashed_password` | VARCHAR | NOT NULL | Salted sha256 encrypted password hash |
| `full_name` | VARCHAR | NULLABLE | Transit officer / operator full name |
| `role_id` | INTEGER | FOREIGN KEY (`roles.id`) | Role classification reference |

#### Table: `station_crowd`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Record surrogate key |
| `stop_id` | VARCHAR | FOREIGN KEY (`stops.stop_id`) | Monitored station reference |
| `passenger_density_percent` | FLOAT | NOT NULL | Crowd density ratio (0-100%) |
| `crowd_level` | VARCHAR | NOT NULL | LOW, MODERATE, HIGH, CRITICAL |
| `inflow_rate` | FLOAT | NOT NULL | Inflow passenger arrivals / min |
| `outflow_rate` | FLOAT | NOT NULL | Outflow passenger exits / min |
| `platform_crowd_count` | INTEGER | NOT NULL | Real-time passenger count on platform |
| `congestion_index` | FLOAT | NOT NULL | Normalized congestion indicator (0.0-1.0) |

#### Table: `alerts`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY | Alert surrogate key |
| `title` | VARCHAR | NOT NULL | Operational incident headline |
| `category` | VARCHAR | NOT NULL | 1 of 7 defined incident categories |
| `severity` | VARCHAR | NOT NULL | INFO, WARNING, CRITICAL |
| `status` | VARCHAR | NOT NULL | ACTIVE, ACKNOWLEDGED, RESOLVED |
| `message` | TEXT | NOT NULL | Comprehensive incident details |
| `created_at` | VARCHAR | NOT NULL | ISO 8601 creation timestamp |
| `acknowledged_by` | VARCHAR | NULLABLE | Email of acknowledging operator |
| `resolved_at` | VARCHAR | NULLABLE | ISO 8601 resolution timestamp |

