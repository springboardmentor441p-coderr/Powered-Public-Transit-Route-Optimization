# RouteRanker: Official Chicago CTA Real-Time APIs Investigation Report

This report documents the official real-time APIs provided by the Chicago Transit Authority (CTA), detailing authentication, endpoints, rate limits, request parameters, response structures, and integration architecture for RouteRanker.

---

## 1. CTA Bus Tracker API (v2)

- **Official Documentation**: `https://www.transitchicago.com/developers/bustracker/`
- **Base URL**: `http://www.ctabustracker.com/bustime/api/v2/`
- **Authentication**: Free registration required. Developer API key passed via the `key` query parameter.
- **Data Formats**: XML (default) or JSON via `&format=json`.
- **Default Rate Limit**: 10,000 transactions per day per developer key.
- **Update Frequency**: Refreshed every 30 to 60 seconds by CTA AVL (Automatic Vehicle Location) equipment.

### Core Endpoints

| Endpoint | Method | Key Parameters | Response Attributes | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `gettime` | GET | `key` | `tm` (YYYYMMDD HH:MM:SS) | Synchronizes client clocks with CTA tracker server. |
| `getvehicles` | GET | `key`, `rt` (routes), `vid` (vehicle IDs) | `vid`, `tmstmp`, `lat`, `lon`, `hdg` (heading 0-359), `pid` (pattern ID), `rt` (route), `des` (destination), `pdist` (linear distance), `dly` (boolean delay flag), `spd` (speed mph), `tatripid` | Live tracking of active buses on routes. |
| `getroutes` | GET | `key` | `rt`, `rtnm` (route name), `rtclr` (hex color) | Directory of all active bus routes. |
| `getdirections` | GET | `key`, `rt` | `dir` (e.g., "Northbound", "Southbound") | Returns directional branches for a given route. |
| `getstops` | GET | `key`, `rt`, `dir` | `stpid`, `stpnm`, `lat`, `lon` | Returns bus stops along a directional route. |
| `getpredictions` | GET | `key`, `stpid` or `vid`, `top` (max predictions) | `tmstmp`, `typ` (A=arrival, D=departure), `stpnm`, `stpid`, `vid`, `dstp` (distance to stop), `rt`, `des`, `prdtm` (predicted time), `dly` | Estimated arrival countdowns at individual stops. |
| `getpatterns` | GET | `key`, `rt` or `pid` | `pid`, `ln` (length), `r` (points: `seq`, `lat`, `lon`, `typ`) | Route pattern polylines and stopping waypoints. |

---

## 2. CTA Train Tracker API (v1.0)

- **Official Documentation**: `https://www.transitchicago.com/developers/traintracker/`
- **Base URL**: `http://lapi.transitchicago.com/api/1.0/`
- **Authentication**: Free registration required. Developer API key passed via `key` query parameter.
- **Data Formats**: XML (default) or JSON via `&outputType=JSON`.
- **Default Rate Limit**: 50,000 transactions per day per developer key.
- **Update Frequency**: Real-time signal block updates, refreshed every ~20 to 30 seconds.

### Core Endpoints

| Endpoint | Method | Key Parameters | Response Attributes | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `ttarrivals.aspx` | GET | `key`, `mapid` (station ID) or `stpid` (stop ID), `max` | `staId`, `stpId`, `staNm`, `stpDe`, `rn` (run number), `rt` (Red, Blue, Brn, G, Org, P, Pnk, Y), `destSt`, `destNm`, `trDr`, `prdt` (prediction generation time), `arrT` (predicted arrival time), `isApp` (1 if train approaching), `isDly` (1 if delayed) | Station platform arrival countdowns and approaching train alerts. |
| `ttpositions.aspx` | GET | `key`, `rt` (comma-separated line codes) | `rn`, `destSt`, `destNm`, `trDr`, `nextStaId`, `nextStpId`, `nextStaNm`, `prdt`, `arrT`, `isApp`, `isDly`, `lat`, `lon`, `heading` | System-wide train locations and line-level operation overview. |

---

## 3. CTA Customer Alerts & Service Status API

- **Official Documentation**: `https://www.transitchicago.com/developers/alerts/`
- **Endpoint**: `https://www.transitchicago.com/api/1.0/alerts.aspx?outputType=JSON`
- **Authentication**: Publicly accessible without key or with developer key.
- **Response Structure**:
  - `AlertId`, `Headline`, `ShortDescription`, `FullDescription`, `SeverityScore`, `Impact`, `EventStart`, `EventEnd`, `ImpactedService` (ServiceType, ServiceName, ServiceId, ServiceTypeDescription).
- **Purpose**: Live disruption badges, delay advisories, and reroute notices displayed on the dashboard and route planner.

---

## 4. GTFS-Realtime Feeds

CTA publishes GTFS-Realtime feeds matching standard Transit Protocol Buffer (protobuf) specifications:
1. **Trip Updates**: Predicts arrival and departure times at downstream stops.
2. **Vehicle Positions**: Live coordinate streaming for vehicles across the transit grid.
3. **Alerts**: Real-time service alerts formatted in GTFS-RT entities.

---

## 5. Security & Credentials Management

To integrate real-time tracking:
1. Register for free at `https://www.transitchicago.com/developers/`.
2. Request a **Bus Tracker API Key** and a **Train Tracker API Key**.
3. Create a local `.env` file (copied from `.env.example`):
   ```bash
   CTA_BUS_API_KEY=YOUR_ACTUAL_BUS_API_KEY
   CTA_TRAIN_API_KEY=YOUR_ACTUAL_TRAIN_API_KEY
   ```
4. **Never Commit Keys**: `.gitignore` strictly prohibits committing `.env` files.
5. **Graceful Fallback Mode**: If keys are omitted in `.env`, RouteRanker automatically shifts to **Schedule-Derived Real-Time Simulation** using static GTFS vehicle trajectories with explicit UI labels, ensuring the application remains 100% interactive and demonstrable out of the box without requiring manual API key configuration.

