import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { LoadingState } from './components/ui'

const OverviewPage = lazy(() => import('./pages/OverviewPage').then((module) => ({ default: module.OverviewPage })))
const RoutesPage = lazy(() => import('./pages/RoutesPage').then((module) => ({ default: module.RoutesPage })))
const StopsPage = lazy(() => import('./pages/StopsPage').then((module) => ({ default: module.StopsPage })))
const NetworkMapPage = lazy(() => import('./pages/NetworkMapPage').then((module) => ({ default: module.NetworkMapPage })))
const InsightsPage = lazy(() => import('./pages/InsightsPage').then((module) => ({ default: module.InsightsPage })))
const ComparePage = lazy(() => import('./pages/ComparePage').then((module) => ({ default: module.ComparePage })))

export function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="grid min-h-screen place-items-center"><LoadingState label="Loading page…" /></div>}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="routes" element={<RoutesPage />} />
            <Route path="stops" element={<StopsPage />} />
            <Route path="map" element={<NetworkMapPage />} />
            <Route path="insights" element={<InsightsPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
