# MetroFlow Database Schema & Data Dictionary
*Project: MetroFlow AI Platform for Metro Crowd Management & Scheduling*
*Document Reference: DB-SCHEMA-01*

---

## 1. Relational Entity Overview
The database uses a normalized relational architecture connecting standard GTFS timetable entities with operational monitoring tables and role-based authentication.

---

## 2. Table Specifications

### 2.1 Authentication & RBAC

#### `roles`
Stores access control roles.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Unique role ID |
| `name` | VARCHAR | UNIQUE, NOT NULL | Role name (`admin`, `operator`) |

#### `users`
Stores user credentials and assigned role.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Unique user ID |
| `email` | VARCHAR | UNIQUE, NOT NULL, INDEX | User login email |
| `hashed_password` | VARCHAR | NOT NULL | Salted password hash |
| `full_name` | VARCHAR | NULLABLE | Operator or Admin display name |
| `role_id` | INTEGER | FOREIGN KEY (`roles.id`) | Assigned RBAC role |

---

### 2.2 GTFS Core Timetable Tables

#### `agencies`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `agency_id` | VARCHAR | PRIMARY KEY | Transit agency identifier |
| `agency_name` | VARCHAR | NOT NULL | Name of transit operator |
| `agency_url` | VARCHAR | NOT NULL | Official transit agency URL |
| `agency_timezone` | VARCHAR | NOT NULL | IANA timezone (e.g., `Asia/Kolkata`) |

#### `routes`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `route_id` | VARCHAR | PRIMARY KEY | Unique line / route code |
| `agency_id` | VARCHAR | FOREIGN KEY (`agencies.agency_id`) | Operating agency |
| `route_short_name` | VARCHAR | NULLABLE | Line designation code (e.g. `100`) |
| `route_long_name` | VARCHAR | NULLABLE | Full route descriptor |
| `route_type` | INTEGER | NOT NULL | GTFS transit mode (`3` = Bus transit) |
| `route_color` | VARCHAR | NULLABLE | HEX branding color |

#### `stops`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `stop_id` | VARCHAR | PRIMARY KEY | Station / stop identifier |
| `stop_name` | VARCHAR | NOT NULL | Station name |
| `stop_lat` | FLOAT | NOT NULL | Latitude coordinates |
| `stop_lon` | FLOAT | NOT NULL | Longitude coordinates |
| `zone_id` | VARCHAR | NULLABLE | Fare zone code |

#### `trips`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `trip_id` | VARCHAR | PRIMARY KEY | Unique scheduled run ID |
| `route_id` | VARCHAR | FOREIGN KEY (`routes.route_id`) | Associated line |
| `service_id` | VARCHAR | FOREIGN KEY (`calendar.service_id`) | Active calendar service |
| `trip_headsign` | VARCHAR | NULLABLE | Direction indicator |
| `direction_id` | INTEGER | NULLABLE | Inbound (`0`) or Outbound (`1`) |
| `shape_id` | VARCHAR | NULLABLE | Path alignment reference |

#### `stop_times`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Row identifier |
| `trip_id` | VARCHAR | FOREIGN KEY (`trips.trip_id`), INDEX | Associated trip |
| `arrival_time` | VARCHAR | NOT NULL | Scheduled arrival (`HH:MM:SS`) |
| `departure_time` | VARCHAR | NOT NULL | Scheduled departure (`HH:MM:SS`) |
| `stop_id` | VARCHAR | FOREIGN KEY (`stops.stop_id`), INDEX | Station ID |
| `stop_sequence` | INTEGER | NOT NULL | Stop order sequence on route |

#### `shapes`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Coordinate point ID |
| `shape_id` | VARCHAR | NOT NULL, INDEX | Path geometry identifier |
| `shape_pt_lat` | FLOAT | NOT NULL | Latitude |
| `shape_pt_lon` | FLOAT | NOT NULL | Longitude |
| `shape_pt_sequence`| INTEGER | NOT NULL | Sequential point index |

---

### 2.3 Real-Time Operational & Crowd Tables

#### `station_crowd`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Observation ID |
| `stop_id` | VARCHAR | FOREIGN KEY (`stops.stop_id`), INDEX | Monitored station |
| `timestamp` | VARCHAR | NOT NULL, INDEX | ISO-8601 observation time |
| `inflow_rate` | FLOAT | DEFAULT 0.0 | Ingress rate (pax/min) |
| `outflow_rate` | FLOAT | DEFAULT 0.0 | Egress rate (pax/min) |
| `passenger_density_percent` | FLOAT | NOT NULL | Platform density (0% - 100%) |
| `crowd_level` | VARCHAR | NOT NULL | `LOW`, `MODERATE`, `HIGH`, `CRITICAL` |
| `platform_crowd_count` | INTEGER | DEFAULT 0 | Active platform headcount |
| `congestion_index` | FLOAT | DEFAULT 0.0 | Normalized congestion ratio (0.0 - 1.0) |

#### `train_status`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Vehicle status record |
| `trip_id` | VARCHAR | FOREIGN KEY (`trips.trip_id`), INDEX | Running trip |
| `train_number` | VARCHAR | NOT NULL | Fleet vehicle number |
| `route_id` | VARCHAR | FOREIGN KEY (`routes.route_id`) | Active route |
| `current_station_id` | VARCHAR | FOREIGN KEY (`stops.stop_id`) | Current or next station |
| `status` | VARCHAR | NOT NULL | `ON_TIME`, `DELAYED`, `CRITICAL_DELAY` |
| `delay_minutes` | INTEGER | DEFAULT 0 | Punctuality deviation in minutes |
| `occupancy_rate` | FLOAT | DEFAULT 0.0 | Vehicle capacity occupied (0% - 100%) |
| `updated_at` | VARCHAR | NOT NULL | Telemetry timestamp |

#### `schedule_scenarios`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Scenario ID |
| `scenario_name` | VARCHAR | NOT NULL | Scenario title |
| `route_id` | VARCHAR | FOREIGN KEY (`routes.route_id`) | Target line |
| `target_headway_minutes` | INTEGER | NOT NULL | Optimized dispatch interval |
| `peak_start_time` | VARCHAR | DEFAULT `08:00:00` | Optimization start window |
| `peak_end_time` | VARCHAR | DEFAULT `10:00:00` | Optimization end window |
| `additional_trains_recommended` | INTEGER | DEFAULT 0 | Required extra vehicle sets |
| `status` | VARCHAR | DEFAULT `PROPOSED` | `PROPOSED`, `APPROVED`, `APPLIED` |
| `created_at` | VARCHAR | NOT NULL | Creation timestamp |

