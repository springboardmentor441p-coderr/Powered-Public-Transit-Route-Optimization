# RouteRanker: Route Matching & Legacy Classification Report

This report documents the cross-referencing audit between historical CTA bus routes in ridership records and the active GTFS schedule specifications.

---

## 1. Summary of Route Matching

- **Unique Routes in Historical Records (2023–2026)**: 131
- **Routes in Active GTFS (`routes.txt`)**: 132 (124 Bus routes + 8 Rail lines)
- **Active Routes Matched Directly**: **124 bus routes** (94.7% match rate)
- **Unmatched Routes**: **7 historical bus routes** (5.3%)

---

## 2. Investigation of the 7 Unmatched Historical Routes

Transit agencies periodically adjust networks: express routes are restructured, seasonal shuttles only run during stadium events, and experimental pilot services conclude.

The 7 unmatched routes were investigated:

| Route ID | Name / Service Role | Historical Status | Current GTFS Status | RouteRanker Handling Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **`128`** | Soldier Field Express | Special Event Shuttle | Not in daily GTFS schedule | Preserved in historical queries; labeled as *"Special Event Express (Soldier Field)"*. Excluded from routine daily graph routing. |
| **`19`** | United Center Express | Special Event Shuttle | Not in daily GTFS schedule | Preserved in historical queries; labeled as *"Special Event Express (United Center)"*. |
| **`X98`** | Avon Express | Specialized contract express | Discontinued contract route | Preserved in historical queries; labeled as *"Discontinued Express"*. |
| **`130`** | Museum Campus Downtown | Seasonal connector | Merged into seasonal schedules | Preserved in historical queries; labeled as *"Seasonal Connector"*. |
| **`5`** | South Shore Night Owl | Historic service line | Absorbed into standard 24h corridors | Labeled as *"Historic / Merged Line"*. |
| **`643`** | Suburban feeder line | Contracted local link | Inactive in standard CTA timetable | Labeled as *"Legacy Feeder"*. |
| **`1001`** | CTA internal test/pilot | Non-revenue / trial route | Internal diagnostic code | Labeled as *"Experimental Trial Code"*. |

---

## 3. Engineering Safeguards

1. **Explicit Route Status Flag**:
   In `cleaned_bus_route_ridership.csv`, each record contains:
   - `is_active_gtfs` (boolean): `True` for active routes, `False` for legacy/seasonal routes.
   - `route_status` (string): Explains the exact historical status.
2. **Graph Construction Integrity**:
   Only active GTFS routes (`is_active_gtfs == True`) are converted into NetworkX graph edges for route planning and frequency simulations, preventing users from being routed onto discontinued bus lines.

