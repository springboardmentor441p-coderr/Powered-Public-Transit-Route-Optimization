# MetroFlow Alert & Notification System Documentation

## Overview

MetroFlow's Alert and Notification System (Milestone 3) provides end-to-end operational incident tracking, real-time user notifications, administrative emergency broadcasts, and live WebSocket push feeds.

---

## 1. Operational Alert Taxonomy

Alerts are partitioned into **7 operational categories**:
1. `SERVICE_ACTIVITY`: Scheduled headway shifts, timetable start/end, service frequency adjustments.
2. `CONGESTION_INDICATOR`: Platform passenger density surges, interchange bottleneck saturation.
3. `SCHEDULE_CHANGE`: Timetable modifications, run reassignments, terminal rerouting.
4. `DELAY`: Signal holding, rolling stock slowdowns, headway deviations exceeding threshold.
5. `INCIDENT`: Mechanical faults, door sensor issues, passenger assistance alarms.
6. `EMERGENCY`: Severe weather, track obstructions, power grid disruptions, security alerts.
7. `SYSTEM_EVENT`: GTFS re-ingestion, AI model retraining, database synchronizations.

### Severity Levels
- `INFO`: Normal informational events (blue).
- `WARNING`: Threshold exceedances requiring operator attention (amber).
- `CRITICAL`: Immediate operational threats requiring immediate resolution (red).

### Alert Lifecycle
```
[CREATED] (Status: ACTIVE)
     |
     v
[ACKNOWLEDGED] (Operator reviews & assigns)
     |
     v
[RESOLVED] (Incident cleared & timestamped)
```

---

## 2. In-App Notification & WebSocket Push Architecture

- **Channel:** `/notifications/ws`
- **Protocol:** RFC 6455 WebSockets with JSON message framing.
- **Heartbeat:** Periodic client/server ping/pong (20-second interval).
- **Targeting:** Broadcast to all active sessions or targeted to specific operator IDs (`user_id`).
- **Read State Tracking:** In-app unread counter dynamically synchronizes via `POST /notifications/{id}/read` and `GET /notifications/unread-count`.

---

## 3. Emergency Announcements (Admin Only)

Urgent transit announcements can only be published or deactivated by users with the `admin` role.
- Active announcements are automatically surfaced as a top-level banner across all UI interfaces.
- Includes target affected lines / routes and explicit commuter instructions.
- Full audit trail: records author email and publication/deactivation timestamps.

