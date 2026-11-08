# MetroFlow Authentication & User Management Documentation

## Overview

The MetroFlow platform implements industry-standard JSON Web Token (JWT) OAuth2 Bearer authentication and Role-Based Access Control (RBAC). It differentiates between administrative operations (such as user provisioning and emergency announcements) and operator operations (such as delay handling and schedule updates).

---

## 1. Security Architecture

- **Token Standard:** JWT (RFC 7519) with `HS256` signature algorithm.
- **Password Hashing:** `sha256_crypt` via `passlib.context.CryptContext` with automatic salt generation.
- **Token Expiry:** Configurable via `.env` (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30 minutes).
- **Transport:** HTTP Authorization header: `Bearer <access_token>`.
- **Eager Role Loading:** Role relations are eagerly loaded with `joinedload(User.role)` to prevent session detached errors and minimize database roundtrips.

---

## 2. Roles & Permissions Matrix

| Capability / API Endpoint | Admin (`admin`) | Operator (`operator`) | Public / Anonymous |
| :--- | :---: | :---: | :---: |
| Health Check (`GET /health`) | Yes | Yes | Yes |
| GTFS Summary (`GET /dashboard/summary`) | Yes | Yes | Yes |
| OpenAPI Schema & Docs (`GET /docs`, `/openapi.json`) | Yes | Yes | Yes |
| User Login (`POST /auth/login`) | Yes | Yes | Yes |
| User Profile (`GET /auth/me`) | Yes | Yes | No (401) |
| Operator Provisioning (`POST /auth/admin/users`) | Yes | No (403) | No (401) |
| Live Crowd Monitoring (`GET /crowd/live`) | Yes | Yes | No (401) |
| Congestion Overview (`GET /crowd/congestion`) | Yes | Yes | No (401) |
| Route Timetables & Trips (`GET /schedule/*`) | Yes | Yes | No (401) |
| Delay Reporting (`POST /schedule/delays`) | Yes | Yes | No (401) |
| Headway Recommendations (`GET /scheduling/frequency/recommendations`) | Yes | Yes | No (401) |
| Schedule Scenario Simulation (`POST /scheduling/scenarios`) | Yes | Yes | No (401) |
| AI Crowd & Demand Forecasting (`POST /predict/crowd`) | Yes | Yes | No (401) |
| Traffic Analysis Reports (`GET /analytics/traffic-report`) | Yes | Yes | No (401) |
| Operational Alerts (`GET`, `POST`, `ack`, `resolve` `/alerts/*`) | Yes | Yes | No (401) |
| Notifications Feed (`GET`, `POST`, `read` `/notifications/*`) | Yes | Yes | No (401) |
| WebSocket Push Feed (`/notifications/ws`) | Yes | Yes | Yes |
| Emergency Announcements List (`GET /announcements/active`) | Yes | Yes | No (401) |
| Emergency Announcement Broadcast (`POST /announcements`) | **Yes** | **No (403)** | No (401) |
| Emergency Announcement Deactivation (`POST /announcements/{id}/deactivate`) | **Yes** | **No (403)** | No (401) |
| Schedule Updates Dispatch (`GET`, `POST` `/schedule-updates`) | Yes | Yes | No (401) |

---

## 3. Authentication Endpoints

### 3.1 Token Request (`POST /auth/login`)
- **Request Format:** `application/x-www-form-urlencoded`
- **Fields:** `username` (email address), `password` (plaintext password)
- **Response Format:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3.2 User Profile (`GET /auth/me`)
- **Headers:** `Authorization: Bearer <access_token>`
- **Response Format:**
```json
{
  "id": 1,
  "email": "admin@example.com",
  "full_name": "Admin User",
  "role": "admin"
}
```

### 3.3 Create Operator / Admin (`POST /auth/admin/users`)
- **Privilege Required:** `admin`
- **Headers:** `Authorization: Bearer <admin_token>`
- **Request Format:**
```json
{
  "email": "operator_pune@metroflow.org",
  "password": "SecurePassword#2026",
  "full_name": "Station Master Rajesh",
  "role": "operator"
}
```

---

## 4. Frontend Integration Workflow

1. On initial load, the frontend checks `localStorage.getItem('metroflow_token')`.
2. If token exists, calls `GET /auth/me` to authenticate session.
3. If token is absent or invalid, seamlessly logs in with default seed credentials (`admin@example.com` / `admin123`) so the UI displays live telemetry immediately.
4. An operator or admin can open the **Operator Login** modal from the header to switch to individual credentials or log out.
5. All Axios/fetch calls automatically append `Authorization: Bearer <token>` to request headers.

