# RouteRanker Professional UI — Implementation

This update restyles the existing RouteRanker React + TypeScript + Vite frontend. It keeps the existing seven application screens, API base URL (`http://127.0.0.1:8000/api`), backend calls, route selection, day-type selection, route map, comparison, historical replay and scenario workflow.

## What changed
- Replaced the top tab bar with a collapsible-style vertical workspace navigation on desktop; on smaller screens it becomes a horizontal scrollable navigation.
- Added a compact product identity area and persistent API connection status.
- Added a page title/context header for each of the seven sections.
- Applied a consistent deep-navy visual system, subtle grid texture, cyan highlights, higher-contrast cards, improved typography and table styling.
- Kept the existing Leaflet map and its dark map treatment.
- Did not add MetroFlow-only functionality. This remains RouteRanker for CTA demand, scheduled service, productivity, route comparison, historical replay and service scenario analysis.

## Step-by-step
1. Make a backup of your current `frontend/src` folder.
2. Extract this ZIP.
3. Copy the extracted `src/App.tsx`, `src/index.css`, and `tsconfig.app.json` into your existing frontend folder, replacing those files.
4. Keep your existing `package.json`, `package-lock.json`, `vite.config.ts`, `index.html`, backend, models and processed data unchanged.
5. Open a terminal in the frontend folder and run `npm install`.
6. Start the backend in a separate terminal using your existing command, for example `uvicorn main:app --reload` from the backend folder.
7. Start the frontend using `npm run dev` and open the Vite URL shown in the terminal (usually `http://localhost:5173`).

## Notes
- API base URL is still `http://127.0.0.1:8000/api`.
- If your backend runs on another host/port, update `API_BASE` at the top of `src/App.tsx`.
- KPI figures and project-specific definitions already present in the original app have not been re-invented by this visual refresh. Verify all figures against your final report before a public demo.
- Build verification could not be completed in this environment because the uploaded Windows `node_modules` contains platform-specific binaries. Run `npm install` on your own machine before `npm run build`.
