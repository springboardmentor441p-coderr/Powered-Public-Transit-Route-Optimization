import { useCallback, useEffect, useState } from "react";
import { apiClient } from "./api/client";
import { Layout, type NavSectionId } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { CorridorsPage } from "./pages/CorridorsPage";
import { ForecastingPage } from "./pages/ForecastingPage";
import { OverviewPage } from "./pages/OverviewPage";
import { RankingsPage } from "./pages/RankingsPage";
import { RidershipPage } from "./pages/RidershipPage";
import { RoutesPage } from "./pages/RoutesPage";
import { SpatialPage } from "./pages/SpatialPage";
import type { HealthCheckResponse } from "./types/api";

export function App() {
  const [section, setSection] = useState<NavSectionId>("overview");
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const refreshHealth = useCallback((signal?: AbortSignal) => {
    apiClient
      .getHealth(signal)
      .then((res) => {
        setHealth(res);
        setHealthError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setHealth(null);
        setHealthError(err instanceof Error ? err.message : "Offline");
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    refreshHealth(controller.signal);
    return () => controller.abort();
  }, [refreshHealth]);

  const handleOpenRoute = (routeId: string) => {
    setSelectedRouteId(routeId);
    setSection("routes");
  };

  const handleOpenRidership = (routeId: string) => {
    setSelectedRouteId(routeId);
    setSection("ridership");
  };

  return (
    <Layout activeSection={section} onNavigate={setSection} health={health} healthError={healthError}>
      {section === "overview" && (
        <OverviewPage onSelectRoute={handleOpenRoute} onRetrySuccess={() => refreshHealth()} />
      )}
      {section === "routes" && (
        <RoutesPage initialRouteId={selectedRouteId} onOpenRidership={handleOpenRidership} />
      )}
      {section === "rankings" && <RankingsPage />}
      {section === "ridership" && <RidershipPage initialRouteId={selectedRouteId} />}
      {section === "spatial" && <SpatialPage />}
      {section === "corridors" && <CorridorsPage />}
      {section === "forecasting" && <ForecastingPage />}
      {section === "about" && <AboutPage />}
    </Layout>
  );
}

export default App;
