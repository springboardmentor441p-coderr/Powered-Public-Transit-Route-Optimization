# MetroFlow Database Relationships & Entity-Relationship Architecture

## Overview
MetroFlow manages both static transit network topologies (GTFS specification) and dynamic operational data (crowd metrics, vehicle telemetry, alerts, and user accounts).

---

## 1. Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    AGENCIES ||--o{ ROUTES : operates
    ROUTES ||--o{ TRIPS : contains
    CALENDARS ||--o{ TRIPS : schedules
    TRIPS ||--o{ STOP_TIMES : includes
    STOPS ||--o{ STOP_TIMES : visited_at
    TRIPS ||--o{ SHAPES : traces
    ROLES ||--o{ USERS : classifies
    USERS ||--o{ NOTIFICATIONS : receives
    STOPS ||--o{ STATION_CROWD : observes
    TRIPS ||--o{ TRAIN_STATUS : tracks
    ROUTES ||--o{ SCHEDULE_SCENARIOS : simulates
    ROUTES ||--o{ SCHEDULE_UPDATES : alters

    AGENCIES {
        string agency_id PK
        string agency_name
        string agency_url
        string agency_timezone
    }

    ROUTES {
        string route_id PK
        string agency_id FK
        string route_short_name
        string route_long_name
        int route_type
    }

    TRIPS {
        string trip_id PK
        string route_id FK
        string service_id FK
        string trip_headsign
        int direction_id
        string shape_id
    }

    STOPS {
        string stop_id PK
        string stop_name
        float stop_lat
        float stop_lon
    }

    STOP_TIMES {
        int id PK
        string trip_id FK
        string stop_id FK
        string arrival_time
        string departure_time
        int stop_sequence
    }

    USERS {
        int id PK
        string email UK
        string hashed_password
        int role_id FK
    }

    ROLES {
        int id PK
        string name UK
    }

    ALERTS {
        int id PK
        string title
        string category
        string severity
        string status
        string target_stop_id FK
        string target_route_id FK
    }

    NOTIFICATIONS {
        int id PK
        int user_id FK
        string title
        string message
        boolean is_read
    }
```

---

## 2. Foreign Key & Index Optimization Strategies

1. **`stop_times` Composite Index:** Index on `(trip_id, stop_sequence)` accelerates timetable reconstruction to sub-millisecond query time.
2. **`stops` Spatial Coordinates:** Indices on `(stop_lat, stop_lon)` support fast geographic radius queries and interactive map bounding box filtering.
3. **`trips` Route Lookup:** Index on `(route_id, direction_id)` enables instant timetable run queries for scheduling optimization.
4. **`alerts` & `notifications` Time-Series:** Index on `created_at DESC` ensures that active operational dashboards always fetch the freshest state without table scans.

