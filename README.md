# RouteRanker: CTA reference case

Transit-route analysis for Chicago Transit Authority (CTA) buses. It covers daily ridership forecasting, route grouping,
named ranking indicators, historical replay and service scenarios. The work follows the project technical spec (v3.8, Section 9).

**Status:** Stage 1 (Source foundation) is complete. See `reports/stage1_quality_report.md` and `NOTES.md`.

## Setup (Windows CMD, Python 3.12)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Stage 1: download, register, validate
```
python -I analytics\source\download_sources.py --config analytics\config\sources.json --raw data\raw
python -I analytics\source\build_register.py --config analytics\config\sources.json --raw data\raw --out reports
python -I analytics\source\validate_raw.py --config analytics\config\sources.json --register data\raw\source_register.csv --out reports
```
Raw data (~610 MB) goes to `data/raw/` and is not committed. Raw files are never overwritten.
If the 2026-10-22 reference export becomes available, place it in `data/raw/ridership/` and rerun the last two commands.

## Layout
`data/` raw + processed (gitignored) · `analytics/` pipeline code · `artifacts/` fitted models · `backend/` FastAPI · `frontend/` React · `reports/` quality and evaluation reports

---

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
