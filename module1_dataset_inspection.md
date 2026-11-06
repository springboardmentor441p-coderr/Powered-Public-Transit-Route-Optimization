# Module 1: GTFS Dataset Inspection & Quality Audit Report
**Project:** RouteRanker for Chennai MTC Buses  
**Audit Date:** 2026-11-06  
**Dataset Path:** `C:\Users\kavyasri\Downloads\mtc-gtfs`  
**Audit Scope:** Read-Only Integrity, Relational Consistency & Schema Audit

---

## 1. Executive Summary

This report establishes the baseline dataset quality audit for the Chennai Metropolitan Transport Corporation (MTC) GTFS dataset.
The analysis evaluated all 7 GTFS text files, measuring entity counts, schema adherence, primary and foreign key integrity, temporal monotonicity, and geospatial coordinate accuracy.

### Key Audit Metrics
- **Total Transit Routes:** 4,611 defined (with **3,934** active routes and **677** unserviced routes).
- **Total Bus Stops:** 5,580 defined (with **5,477** active stops and **103** unvisited stops).
- **Total Scheduled Trips:** 47,047 trips across Chennai.
- **Total Stop-Times Records:** 1,360,443 stop arrival/departure records.
- **Data Completeness:** 100% complete across all core operational fields. No null values in stops, routes, trips, or stop_times.
- **Relational Integrity:** 100% clean foreign keys (0 orphaned trips, 0 orphaned stop-times).
- **Temporal Consistency:** 100% clean chronological ordering (0 departure < arrival anomalies, 0 non-monotonic trips).

---

## 2. GTFS File Inventory & Specification Adherence

| File Name | GTFS Requirement | Size (Bytes) | Row Count | Primary Key | Integrity Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `agency.txt` | Required | 133 | 1 | `agency_id` | Valid |
| `calendar.txt` | Conditional (Schedule) | 342 | 6 | `service_id` | Contains 2 Suspicious Records |
| `feed_info.txt` | Optional | 269 | 1 | N/A | Missing start/end dates |
| `routes.txt` | Required | 226,405 | 4,611 | `route_id` | Valid (677 unused routes) |
| `stops.txt` | Required | 230,767 | 5,580 | `stop_id` | Valid (103 unused stops) |
| `trips.txt` | Required | 1,049,101 | 47,047 | `trip_id` | Valid (100% clean) |
| `stop_times.txt` | Required | 43,537,866 | 1,360,443 | `(trip_id, stop_sequence)` | Valid (100% monotonic) |

---

## 3. Suspicious Unreferenced Calendar Records

In `calendar.txt`, 6 service schedules are defined. Only 2 are referenced by scheduled trips (`Regular` with 46,973 trips, and `HSC` with 74 trips).
Four records are unreferenced, of which **two are suspicious/test artifacts**:

| service_id | Active Trips | Issue Identified | Risk / Analysis |
| :--- | :--- | :--- | :--- |
| `'test '` | 0 | Test record with trailing whitespace | Artifact of feed testing during export. |
| `'/><script>alert(1)</script>'` | 0 | XSS (Cross-Site Scripting) probe string | Security test probe injected during upstream data authoring. Must be safely handled in front-end renderers. |
| `'Weekend'` | 0 | Unused schedule | Weekend calendar defined but no trips assigned. |
| `'Hybrid'` | 0 | Unused schedule | Hybrid calendar defined but no trips assigned. |

*Per project guidelines, these records are retained in the source files without alteration, and flagged for sanitation during ingestion.*

---

## 4. Inactive Transit Entities

### 4.1 Unused Routes (677 Routes)
- **Count:** 677 of 4,611 routes (14.68%) have no scheduled trips in `trips.txt`.
- **Sample Routes:**
  - `18761` (Route `T23C CT`: Saidapet TO Ayanavaram)
  - `11919` (Route `55K`: Tambaram West TO Guduvanchery)
  - `18763` (Route `T23C CT1`: Thiruvanmiyur TO Egmore)
  - `13402` (Route `S43`: Pudur TO Villivakkam)
  - `17678` (Route `549`: Poonamallee B.T TO Sriperumbudur)
- **Cause:** Discontinued routes, seasonal services, or catalog placeholders from legacy scheduling software.

### 4.2 Unused Stops (103 Stops)
- **Count:** 103 of 5,580 stops (1.85%) are never referenced in `stop_times.txt`.
- **Sample Stops:**
  - `11` (Alandur Depot, 12.99708° N, 80.19136° E)
  - `9353` (Ambedkar Bridge, 13.04119° N, 80.27450° E)
  - `5345` (Perumbakkam Depot, 12.88775° N, 80.20880° E)
  - `11117` (Anna Salai X Pallavan Salai VB - OUT, 13.07381° N, 80.27649° E)
  - `11118` (Anna Salai X Pallavan Salai VC - IN, 13.07473° N, 80.27766° E)
- **Cause:** Non-revenue depot facilities, internal maintenance terminals, or obsolete stopping points.

---

## 5. Temporal & Geospatial Audit Findings

### 5.1 Temporal Integrity
- **Time Format:** 100% conformant to `HH:MM:SS`.
- **Service Span:** `00:00:00` to `25:41:00` (Standard GTFS hour > 23 representation for overnight trips).
- **Inverted Intervals:** 0 records where departure < arrival.
- **Chronological Sequence:** 0 non-monotonic trips. Arrival times strictly advance with stop sequence.
- **Sequence Clashes:** 0 duplicate stop sequence values within trips.

### 5.2 Geospatial Coordinate Bounds
- **Latitude Span:** `12.61480° N` to `13.49042° N`
- **Longitude Span:** `79.80188° E` to `80.33584° E`
- **Boundaries:** All coordinates lie cleanly within the Chennai Metropolitan Area and its southern/western commuting hinterlands (Mahabalipuram to Arakkonam/Tiruvallur).
- **Out of Range Points:** 0 coordinates violate WGS 84 or geographic sanity limits.

---

## 6. Dataset Limitations & Architecture Impact on RouteRanker

1. **Absence of `shapes.txt`:**
   - *Impact:* No high-resolution polyline trajectories exist.
   - *Design Choice for RouteRanker:* Street trajectories must be reconstructed via road-routing APIs (OSRM/Valhalla) or approximated via sequential stop polylines.
2. **Absence of `calendar_dates.txt`:**
   - *Impact:* Holiday schedules, weekend deviations, and weather cancellations are not captured.
   - *Design Choice for RouteRanker:* Assume standard weekday/daily operations as defined in `Regular`.
3. **Absence of `transfers.txt`:**
   - *Impact:* Inter-route transfer walking times and footpath connectors are unstated.
   - *Design Choice for RouteRanker:* Compute spatial proximity transfers dynamically (e.g. Euclidean/Haversine distance <= 300 m).
4. **Absence of `fare_attributes.txt`:**
   - *Impact:* Fare calculation cannot be conducted directly via GTFS.
   - *Design Choice for RouteRanker:* Multi-criteria route ranking will score travel time, waiting time, number of transfers, and frequency rather than financial fare.

---
**Report generated automatically by Module 1 analysis notebook.**
