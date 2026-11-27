
## Contributing Guidelines (For Interns / Collaborators)

All interns added as collaborators to this repository must follow the branch workflow below. **Direct commits or pushes to the `main` branch are not allowed.**

> Note: `main` only contains the `LICENSE` and `README.md` — it is not used for active development. There is no need to pull the latest `main` into your branch at any point.
 



### 1. Branch Naming

- Every intern must create their own branch off `main`, named after themselves.
- Suggested naming convention: `firstname-lastname` (all lowercase, hyphen-separated).
  - Example: `john-doe`, `aisha-khan`

### 2. How to Create Your Branch

**Option A — Clone and push (recommended)**

```bash
# Clone the repository
git clone https://github.com/springboardmentor441p-coder/Powered-Public-Transit-Route-Optimization.git

# Move into the project folder
cd Powered-Public-Transit-Route-Optimization

# Create and switch to your own branch (off main)
git checkout -b your-name

# ... make your changes ...

# Stage, commit, and push your changes to YOUR branch only
git add .
git commit -m "Describe your change here"
git push origin your-name
```

**Option B — GitHub UI upload**

1. Go to the repository on GitHub.
2. Switch the branch dropdown from `main` to your own branch (create it first via **Branch: main → View all branches → New branch**, named after yourself).
3. Once on your branch, use **Add file → Upload files** to upload your code.
4. Commit directly to your branch (not `main`).

### 3. Rules

- ❌ Do **not** push or upload code directly to `main`.
- ❌ Do **not** push code to another intern's branch.
- ✅ Only push/upload code to the branch that carries your own name.
- Keep uploading/pushing your code to your branch regularly as you make progress. No pull requests are required — your branch itself is the deliverable.

### 4. Summary

| Action | Allowed? |
|---|---|
| Push to `main` directly | ❌ No |
| Create your own branch from `main` | ✅ Yes |
| Push/upload code to your own branch | ✅ Yes |
| Push/upload code to someone else's branch | ❌ No |
| Open a Pull Request | Not required |

# RouteRanker — CTA Transit Planning, Replay & Demand Forecasting

RouteRanker is an interactive transit-analytics dashboard and replay simulator for Chicago Transit Authority (CTA) bus routes. It combines historical daily ridership (2001–2026) with reconstructed GTFS schedule snapshots to support non-leaking historical replay, route-level demand forecasting, corridor productivity ranking, and conditional "what-if" service modeling.
Features

    Integrity & Ingestion (01–02): Verifies raw source checksums (SHA-256) and normalizes boardings data with type contracts and zero-boarding preservation.

    Schedule Parsing & Corridor Geometry (03–04): Uses DuckDB for bounded-memory GTFS schedule parsing and computes pairwise Jaccard corridor overlap and stop containment.

    Leakage-Safe Feature Engineering & Modeling (05–06): Builds historical same-weekday lags (t-1, t-7, t-14, etc.) with strict reporting-delay cutoffs and evaluates models chronologically across Train/Validation/Test splits.

    Productivity Ranking, Clustering & Scenarios (07): Computes route efficiency metrics (rides / scheduled hour, rides / scheduled trip), KMeans corridor clusters, review tiers, and frequency/demand scenario comparisons.

    API & Interactive Frontend: Exposes FastAPI endpoints for coverage, routes, rankings, forecasts, and scenarios alongside a React + TypeScript + Leaflet + Recharts planning workspace.

Project Structure
Plaintext

route-ranker/
├── analytics/
│   ├── 01_source_register.py               # SHA-256 integrity verification on raw inputs
│   ├── 02_clean_boardings.py               # Type contracts & zero-boarding preservation
│   ├── 03_parse_gtfs_schedule.py           # DuckDB bounded-memory schedule parser (routes, trips, stops)
│   ├── 04_route_structure_and_overlap.py   # Pairwise Jaccard corridor overlap & containment
│   ├── 05_feature_engineering.py           # Leakage-safe calendar features & historical lags
│   ├── 06_train_evaluate_models.py         # Chronological out-of-time Train/Val/Test evaluation
│   └── 07_route_productivity_ranking.py    # Productivity ratios, KMeans clustering & review tiers
├── backend/
│   └── main.py                             # FastAPI routes (/api/health, /api/data/coverage, /api/routes, /api/rankings, /api/forecasts, /api/scenarios)
├── frontend/
│   └── src/
│       └── App.tsx                         # Network overview, Leaflet route map, replay bar, explorer, comparison, evaluation & scenarios
└── data/
    └── processed/                          # Parquet analytical tables (gitignored for repo size limits)
        ├── boardings_clean.parquet
        ├── gtfs_routes_clean.parquet
        ├── route_scheduled_service.parquet
        ├── route_structure.parquet
        ├── route_overlap.parquet
        ├── model_features.parquet
        ├── model_predictions_test.parquet
        └── productivity_rankings.parquet