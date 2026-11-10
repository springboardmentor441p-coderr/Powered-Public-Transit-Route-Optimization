# RouteRanker development instructions

## Scope and data integrity
- Work only inside this project workspace. Do not create a second project directory.
- Preserve user files and the source archive at `data/raw/mtc-gtfs.zip`. Never rewrite, delete, or extract over source data.
- Treat GTFS as scheduled service data. Do not claim passenger counts, occupancy, actual vehicle positions, traffic conditions, or passenger demand.
- Distinguish observed schedule facts from derived scenarios. Clearly label modeled assumptions and never present hypothetical schedule changes as adopted or real operations.
- Validate records before analysis. Keep source values available for traceability; report anomalies rather than silently repairing or discarding them.
- Escape all untrusted strings at presentation boundaries. In particular, the current feed contains a script-like `service_id` value.

## Engineering conventions
- Keep ingestion, validation, domain analysis, API, and UI responsibilities separate as described in `PROJECT_PLAN.md`.
- Use Python type hints, small functions, explicit schemas, and deterministic transformations. Keep file paths configurable and Windows-friendly (`pathlib`).
- Use DuckDB for repeatable analytical queries; avoid loading the full stop-times table into memory unnecessarily.
- Keep API response models explicit and validate inputs. Do not expose raw HTML from feed fields.
- Keep frontend components and API access modular. Use Leaflet for GTFS stop/route geography only when the required geometry is available; do not invent route polylines.
- Keep configuration and dependencies documented. Do not commit secrets, generated data, virtual environments, caches, or build artifacts.
- Add automated tests for new behavior when implementation begins, especially GTFS validation, time parsing, relationship checks, API schemas, and analytical edge cases.
- Before changing an existing file, inspect it and preserve unrelated content. Avoid broad formatting or cleanup changes.

## Current dataset facts
- Source: `data/raw/mtc-gtfs.zip`; it contains `agency.txt`, `calendar.txt`, `feed_info.txt`, `routes.txt`, `stop_times.txt`, `stops.txt`, and `trips.txt`.
- The feed describes scheduled bus service and contains no passenger or real-time operational observations.
- `shapes.txt` and `calendar_dates.txt` are absent. Do not infer route geometry or calendar exceptions.
- `calendar.txt` contains unused service records, including a script-like identifier. Validate and safely render feed-provided strings.
- `routes.txt` and `stops.txt` include records not referenced by trips/stop_times. Make analysis inclusion rules explicit.
- Use the findings in `PROJECT_PLAN.md` as a point-in-time archive inspection, not as a substitute for rerunning validation against a changed feed.
