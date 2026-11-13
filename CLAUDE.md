# CLAUDE.md: RouteRanker (CTA reference case)

## Source of truth
- The spec is version 3.8 (in `docs-private/spec.pdf`) and it **overrides the brief** wherever they differ.
- We are building the **CTA reference case** from spec Section 9.
- `docs-private/` holds the mentor's documents. It is gitignored and must **never** be committed, uploaded or quoted into external services.

## How to work with me (I'm learning)
- **Always plan first**, then work in **small steps**.
- Explain every decision simply, with analogies where they help.
- After **every step**, update `NOTES.md` with:
  1. What we built
  2. Why
  3. The key concept
  4. Decisions
  5. Results
  6. One likely interview question with a short answer

## Fixed tech stack (from the spec). Pin every version.
- Frontend: React + TypeScript + Vite, Leaflet (maps), Recharts (charts), Tailwind (styling)
- Backend: FastAPI
- Database: PostgreSQL
- Data: pandas, NumPy, DuckDB (DuckDB for large stop-time processing)
- ML: scikit-learn (Linear Regression, Random Forest, KMeans)
- XGBoost **only** if justified after Random Forest (spec 9.10.1 step 5)
- PyTorch LSTM/GRU/CNN only as **documented extras** for my Deep Learning module
- Pin all versions (`==` in requirements.txt, exact versions in package.json).
- **If anything else seems needed, stop and ask me first.**
- Add dependencies only when the stage that needs them begins.

## Git rules
- Work only on branch `tayyaba-haroon`. **Never** commit to or touch `main`.
- **Show me `git status` before any commit.**
- **Never push without asking me.**

## Layout (spec 9.17.5). The repo root plays the role of `route-ranker/`.
```
data/raw/            immutable source downloads and manifest (gitignored)
data/processed/      versioned daily tables and profiles (gitignored)
analytics/           validation, features, training and evaluation
artifacts/           complete fitted pipelines and metadata (model files gitignored)
backend/             FastAPI, database access and replay/scenarios
frontend/            React and TypeScript screens
reports/             quality, evaluation and demonstration notes
```
Raw storage (spec 9.4.3):
```
data/raw/ridership/<dated_export>.csv
data/raw/gtfs/<snapshot_id>/original.zip
data/raw/gtfs/<snapshot_id>/extracted/*.txt
data/processed/<data_version>/...
```
Raw files are never overwritten. A new export is a new version that sits beside the old one.

## Commands
- Give **Windows CMD** commands (I'm on CMD), e.g. `.venv\Scripts\activate`.
- Run scripts that read downloaded data with `python -I` (isolated mode).
