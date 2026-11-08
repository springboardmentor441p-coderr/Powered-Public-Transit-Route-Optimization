# MetroFlow Project Overview

## What is MetroFlow?

**MetroFlow** is an enterprise-grade AI Public Transportation Intelligence Platform engineered to assist transit authorities, dispatchers, and station operators in:
1. **Real-time Crowd Monitoring:** Visualizing station passenger density, platform overcrowding, and network congestion indices.
2. **Interactive Geographic Mapping:** Exploring transit lines, station coordinates, and congestion markers on a dynamic Leaflet map.
3. **Train & Fleet Telemetry:** Tracking scheduled train/bus trips, delays, and passenger occupancy.
4. **Intelligent Frequency Optimization:** Generating algorithmic recommendations to adjust dispatch headways during peak and off-peak windows to reduce platform overcrowding.
5. **Machine Learning Predictive Analytics:** Forecasting hourly passenger demand and station crowd surges using trained gradient boosted decision trees.
6. **Operational Alerting & Push Notifications:** Centralizing incident management across 7 operational categories with live WebSocket push streams.
7. **Emergency Broadcast Center:** Providing administrative emergency broadcasting for severe weather and network incidents.
8. **Operational Schedule Updates:** Allowing operators to dispatch delays, cancellations, and supplemental shuttles without altering the underlying immutable GTFS baseline records.

---

## High-Level Architecture

```
[ Commuters & Dispatchers ]
           |
           v
[ React.js + TypeScript Web UI ]  <---- (WebSocket Push / Notifications)
           |
   (REST APIs & JWT Auth)
           v
[ FastAPI Intelligence Backend ]
     |           |          |
     |           |          +---> [ Scikit-Learn ML Predictors ]
     |           |
     v           v
[ PostgreSQL / SQLite ] <--- [ GTFS Ingestion Pipeline (Pune PMPML) ]
```

---

## Quick Navigation Guide

- **Live Web Interface:** `http://localhost:8000/`
- **Interactive API Documentation:** `http://localhost:8000/docs`
- **Health Verification:** `http://localhost:8000/health`
- **Downloadable Markdown Report:** `http://localhost:8000/analytics/traffic-report/markdown`

