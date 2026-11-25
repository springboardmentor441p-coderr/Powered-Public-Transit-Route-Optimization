# 10 — Automated Test Execution Report (Phase J)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Date:** 2026-11-25  

---

| Suite | Command | Discovered | Executed | Passed | Failed | Skipped | Errors | Duration |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Backend Suite | `python -m unittest discover -s backend/tests -v` | 60 | 60 | 60 | 0 | 0 | 0 | 2.788s |
| Full Project Suite | `python -m unittest discover tests` | 205 | 205 | 205 | 0 | 0 | 0 | 8.5s |
| Frontend Lint | `npm --prefix frontend run lint` | 15 files | 15 files | 15 files | 0 | 0 | 0 (14 warn) | 75ms |
| Frontend Build | `npm --prefix frontend run build` | — | — | PASS | 0 | 0 | 0 | 1.13s |

- All 60 backend tests exercise real FastAPI `TestClient(app)` endpoints against canonical artifacts plus isolated synthetic edge-case fixtures (never mocking out core behavior to pass).
- Frontend has no separate Jest/Vitest runner (`I-03`); verified via `oxlint`, `tsc -b`, `vite build`, and live Chrome DevTools E2E inspection.
