import React, { useEffect, useState } from "react";
import {
  api,
  EvaluationData,
  GroupsData,
  NetworkDailyRow,
  NetworkHourlyRow,
  OverviewData,
  ReviewCell,
  RouteSummary,
} from "./api";
import { EvaluationPage } from "./components/EvaluationPage";
import { GtfsUploadPage } from "./components/GtfsUploadPage";
import { OverviewPage } from "./components/OverviewPage";
import { ReviewListPage } from "./components/ReviewListPage";
import { RouteDetailPage } from "./components/RouteDetailPage";
import { RouteGroupsPage } from "./components/RouteGroupsPage";
import { ScenariosPage } from "./components/ScenariosPage";

type TabId =
  | "overview"
  | "route"
  | "groups"
  | "evaluation"
  | "review"
  | "scenarios"
  | "gtfs";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "overview", label: "Overview & Network" },
  { id: "route", label: "Route Detail" },
  { id: "groups", label: "Route Groups" },
  { id: "evaluation", label: "Model Evaluation" },
  { id: "review", label: "Review List" },
  { id: "scenarios", label: "Scenarios" },
  { id: "gtfs", label: "GTFS Upload" },
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [selectedRoute, setSelectedRoute] = useState<string>("M15+");
  const [scenarioInit, setScenarioInit] = useState({
    route: "M15+",
    dayGroup: "weekday",
    timeBand: "morning_peak",
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [dailyRows, setDailyRows] = useState<NetworkDailyRow[]>([]);
  const [hourlyJanSep, setHourlyJanSep] = useState<NetworkHourlyRow[]>([]);
  const [hourlyAugOct, setHourlyAugOct] = useState<NetworkHourlyRow[]>([]);
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [groups, setGroups] = useState<GroupsData | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationData | null>(null);
  const [reviewMeta, setReviewMeta] = useState<{
    period: string;
    source: string;
    rows: ReviewCell[];
  }>({ period: "", source: "", rows: [] });

  useEffect(() => {
    Promise.all([
      api.getOverview(),
      api.getNetworkDaily(),
      api.getNetworkHourly("jan_sep_typical"),
      api.getNetworkHourly("aug_oct_typical"),
      api.getRoutes(),
      api.getGroups(),
      api.getEvaluation(),
      api.getReview(),
    ])
      .then(([ov, daily, h1, h2, rt, grp, ev, rev]) => {
        setOverview(ov);
        setDailyRows(daily.rows);
        setHourlyJanSep(h1.rows);
        setHourlyAugOct(h2.rows);
        setRoutes(rt.rows);
        setGroups(grp);
        setEvaluation(ev);
        setReviewMeta({
          period: rev.period,
          source: rev.source,
          rows: rev.rows,
        });
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load transit API data. Ensure the FastAPI backend is running."
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSelectRoute = (route: string) => {
    setSelectedRoute(route);
    setActiveTab("route");
  };

  const handleOpenScenario = (
    route: string,
    dayGroup: string,
    timeBand: string
  ) => {
    setScenarioInit({ route, dayGroup, timeBand });
    setActiveTab("scenarios");
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-xs font-bold text-white">
              MB
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900">
                Manhattan Bus Network Transit Console
              </div>
              <div className="text-[11px] text-slate-500">
                41 Study Routes · Jan–Oct 2026 Ridership & GTFS Schedule Analysis
              </div>
            </div>
          </div>

          <nav aria-label="Primary Navigation" className="flex flex-wrap gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === t.id
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-600 shadow-sm">
            Loading app_data tables from FastAPI backend...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-800">
            <div className="font-semibold">Backend Connection Error</div>
            <p className="mt-1">{error}</p>
          </div>
        ) : (
          <>
            {activeTab === "overview" && overview ? (
              <OverviewPage
                overview={overview}
                dailyRows={dailyRows}
                hourlyJanSep={hourlyJanSep}
                hourlyAugOct={hourlyAugOct}
                onSelectRoute={handleSelectRoute}
              />
            ) : null}

            {activeTab === "route" ? (
              <RouteDetailPage
                routes={routes}
                selectedRoute={selectedRoute}
                onSelectRoute={setSelectedRoute}
                onOpenScenario={handleOpenScenario}
              />
            ) : null}

            {activeTab === "groups" && groups ? (
              <RouteGroupsPage groups={groups} onSelectRoute={handleSelectRoute} />
            ) : null}

            {activeTab === "evaluation" && evaluation ? (
              <EvaluationPage
                evaluation={evaluation}
                onSelectRoute={handleSelectRoute}
              />
            ) : null}

            {activeTab === "review" ? (
              <ReviewListPage
                cells={reviewMeta.rows}
                period={reviewMeta.period}
                source={reviewMeta.source}
                onSelectRoute={handleSelectRoute}
                onOpenScenario={handleOpenScenario}
              />
            ) : null}

            {activeTab === "scenarios" ? (
              <ScenariosPage
                routes={routes}
                initialRoute={scenarioInit.route}
                initialDayGroup={scenarioInit.dayGroup}
                initialTimeBand={scenarioInit.timeBand}
              />
            ) : null}

            {activeTab === "gtfs" ? <GtfsUploadPage /> : null}
          </>
        )}
      </main>
    </div>
  );
};

export default App;

