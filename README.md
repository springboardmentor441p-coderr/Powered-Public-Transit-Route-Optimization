
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

## Features

- **Non-Leaking Historical Replay:** Steps day-by-day through a replay window while enforcing a configurable reporting delay (e.g., recorded boardings available only through `T - 1`).
- **Route Demand Forecasting (`rf-service-v1`):** Generates daily boarding forecasts using exact historical same-weekday lags (`1d`, `7d`, `14d`, `21d`, `28d`) and scheduled GTFS service inputs (`scheduled_trips`, `scheduled_service_hours`).
- **Review Priorities & Corridor Clustering:** Ranks routes by service productivity (`rides / scheduled hour`) across Weekday (`W`), Saturday (`A`), and Sunday/Holiday (`U`) schedules and groups routes into operational corridor clusters.
- **Conditional Service Scenario Simulator (What-If):** Models proposed trip frequency adjustments and demand stress percentages against baseline route profiles.

## Project Structure

```text
route-ranker/
├── analytics/                  # Data reconstruction, feature engineering, training & clustering scripts
│   ├── step2_reconstruct.py    # GTFS schedule expansion & ridership alignment
│   ├── step3_features.py       # Exact lag generation & train/validation/test split assignment
│   ├── step4_train_models.py   # Demand forecasting model training
│   └── step5_profiles_clustering.py # Route productivity metrics & corridor clustering
├── backend/                    # FastAPI REST API for replay sessions, forecasts, rankings & scenarios
│   └── main.py
├── frontend/                   # React + TypeScript + Vite + Recharts dashboard
│   └── src/
│       └── App.tsx
└── data/                       # Raw and processed CTA ridership & GTFS datasets

