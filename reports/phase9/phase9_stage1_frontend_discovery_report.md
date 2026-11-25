# Phase 9, Stage 9.1 — Frontend Architecture Discovery Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Date:** 2026-11-25  

---

## 1. Existing Frontend Stack & Configuration
- **Framework:** React `^19.3.1`, TypeScript `~7.0.2` (`erasableSyntaxOnly: true`, `verbatimModuleSyntax: true`), Vite `^8.3.6` (`@vitejs/plugin-react`), Tailwind CSS `^4.3.5` (`@tailwindcss/vite`).
- **Visualization & Mapping:** `recharts` `^3.11.0`, `leaflet` `^1.9.4`, `react-leaflet` `^5.0.0`, `lucide-react` `^1.77.0`.
- **Vite Proxy (`frontend/vite.config.ts`):** Proxies `/api` to `http://127.0.0.1:8000`.
- **Pre-Existing State:** Single starter `src/App.tsx` polling `/api/health` with static placeholder cards; no `/api/v1/*` client, no TypeScript API schemas, no multi-page navigation, and no live charts or maps.

## 2. Backend OpenAPI Alignment
- Inspected `/openapi.json` (17 paths, 41 schemas) to derive exact query parameters, track enums (`BUS_PRIORITY`, `RAIL_PRIORITY`, `UNIFIED_SUPPLY`), corridor cluster types (`buffer`, `frechet`), and Stage 2D historical-only forecasting contracts.
