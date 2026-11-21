# RouteRanker frontend

The React + TypeScript screens for RouteRanker's CTA reference case (Stage 6c, historical-analysis mode).
It shows the FastAPI backend's data: network trend, rankings, route groups, route detail, compare and data
coverage. Every number comes from the API; the frontend never filters dates itself (the backend enforces the
cutoff) and never draws a missing value as 0.

Stack (exact versions in `package.json`): React, Vite, Tailwind, Recharts, Leaflet / react-leaflet,
react-router-dom, vitest, oxlint.

## Run it (Windows CMD)

1. Start the API from the repo root (it needs `backend\.env` with `DATABASE_URL`):

   ```
   .venv\Scripts\activate
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```

2. In a second window, start the frontend:

   ```
   cd frontend
   npm ci
   npm run dev
   ```

3. Open http://localhost:5173 (the style reference is at `/style`).

The backend has no CORS. The browser only talks to Vite, and Vite's proxy (`vite.config.ts`) forwards every
`/api/...` request to `http://127.0.0.1:8000`, so each request is same-origin. `npm run preview` (port 4173)
uses the same proxy. If the API is not running, screens say "the API is not reachable".

## Checks

```
npx tsc -b
npm run lint
npx vitest run
npm run build
```
