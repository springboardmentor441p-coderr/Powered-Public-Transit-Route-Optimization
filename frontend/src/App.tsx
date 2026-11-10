import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const RouteExplorerPage = lazy(() => import('./pages/RouteExplorerPage'));
const SchedulePage = lazy(() => import('./pages/SchedulePage'));
const CoveragePage = lazy(() => import('./pages/CoveragePage'));
const OverlapPage = lazy(() => import('./pages/OverlapPage'));
const ClusteringPage = lazy(() => import('./pages/ClusteringPage'));
const OptimizationPage = lazy(() => import('./pages/OptimizationPage'));
const DataQualityPage = lazy(() => import('./pages/DataQualityPage'));

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="p-8 text-sm text-slate-500" role="status">Loading page…</div>}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="routes" element={<RouteExplorerPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="coverage" element={<CoveragePage />} />
            <Route path="overlap" element={<OverlapPage />} />
            <Route path="clustering" element={<ClusteringPage />} />
            <Route path="optimization" element={<OptimizationPage />} />
            <Route path="data-quality" element={<DataQualityPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
