import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  HistoryQuery,
  ReplayState,
  EvaluationData,
  GroupsData,
  NetworkDailyRow,
  NetworkHourlyRow,
  OverviewData,
  ReviewCell,
  RouteSummary,
} from "./api";
import { ComparePage } from "./components/ComparePage";
import {
  ContextBar,
  DEFAULT_CONTEXT,
  ProvenanceLegend,
  ReplayBanner,
  ViewContext,
} from "./components/ContextBar";
import { DayScenarioPanel } from "./components/DayScenarioPanel";
import { EvaluationPage } from "./components/EvaluationPage";
import { ForecastIssuePanel } from "./components/ForecastIssuePanel";
import { NetworkMapPanel } from "./components/NetworkMapPanel";
import { RankingSection } from "./components/RankingSection";
import { ReplayPage } from "./components/ReplayPage";
import { RouteDailyPanel } from "./components/RouteDailyPanel";
import { GtfsUploadPage } from "./components/GtfsUploadPage";
import { OverviewPage } from "./components/OverviewPage";
import { ReviewListPage } from "./components/ReviewListPage";
import { RouteDetailPage } from "./components/RouteDetailPage";
import { RouteGroupsPage } from "./components/RouteGroupsPage";
import { ScenariosPage } from "./components/ScenariosPage";

type TabId =
  | "overview"
  | "route"
  | "compare"
  | "review"
  | "groups"
  | "evaluation"
  | "replay"
  | "scenarios"
  | "gtfs";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "overview", label: "Overview & Network" },
  { id: "route", label: "Route Detail" },
  { id: "compare", label: "Compare Routes" },
  { id: "review", label: "Review & Ranking" },
  { id: "groups", label: "Route Groups" },
  { id: "evaluation", label: "Forecasts & Evaluation" },
  { id: "replay", label: "Replay" },
  { id: "scenarios", label: "Scenarios" },
  { id: "gtfs", label: "GTFS Upload" },
];

const REPLAY_KEY = "routeranker.replaySession";

function readStoredReplay(): string | null {
  try {
    return window.localStorage.getItem(REPLAY_KEY);
  } catch {
    return null;
  }
}

function storeReplay(id: string): void {
  try {
    window.localStorage.setItem(REPLAY_KEY, id);
  } catch {
    // storage blocked; the session still works until the page reloads
  }
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [ctx, setCtx] = useState<ViewContext>(DEFAULT_CONTEXT);
  const selectedRoute = ctx.route;
  const setSelectedRoute = useCallback(
    (route: string) => setCtx((c) => ({ ...c, route })),
    []
  );

  const [dayScenarioInit, setDayScenarioInit] = useState<{
    date: string;
    source: "observed" | "forecast";
  }>({ date: "2026-10-20", source: "observed" });
  const openDayScenario = (route: string, date: string, source: "observed" | "forecast") => {
    setCtx((c) => ({ ...c, route }));
    setDayScenarioInit({ date, source });
    setActiveTab("scenarios");
  };

  const [replayId, setReplayId] = useState<string | null>(null);
  const [replayState, setReplayState] = useState<ReplayState | null>(null);
  const [replayBusy, setReplayBusy] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);
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

  // Opening the Replay tab turns on replay mode.
  useEffect(() => {
    if (activeTab === "replay" && ctx.mode !== "replay") {
      setCtx((c) => ({ ...c, mode: "replay" }));
    }
  }, [activeTab, ctx.mode]);

  // Find or create a replay session the first time replay mode is used.
  useEffect(() => {
    if (ctx.mode !== "replay" || replayId) return;
    let cancelled = false;
    const pick = async (): Promise<ReplayState> => {
      const stored = readStoredReplay();
      if (stored) {
        try {
          return await api.getReplay(stored, ctx.route);
        } catch {
          // stored session is gone; fall through
        }
      }
      const list = await api.listReplays();
      const latest = list.rows.find((r) => !r.replaced_by);
      if (latest) return api.getReplay(latest.session_id, ctx.route);
      return api.createReplay({ start_date: "2026-10-18", delay_days: 1, speed_seconds: 5 });
    };
    pick()
      .then((st) => {
        if (cancelled) return;
        setReplayId(st.session.session_id);
        storeReplay(st.session.session_id);
        setReplayState(st);
        setReplayError(null);
      })
      .catch((e) => !cancelled && setReplayError(e instanceof Error ? e.message : "Could not start a replay."));
    return () => {
      cancelled = true;
    };
  }, [ctx.mode, replayId, ctx.route]);

  // Refresh replay state: once when the route changes, and every second while playing.
  const playing = replayState?.session.status === "playing";
  useEffect(() => {
    if (ctx.mode !== "replay" || !replayId) return;
    let cancelled = false;
    const load = () =>
      api
        .getReplay(replayId, ctx.route)
        .then((st) => !cancelled && setReplayState(st))
        .catch((e) => !cancelled && setReplayError(e instanceof Error ? e.message : "Replay update failed."));
    load();
    if (!playing) return () => {
      cancelled = true;
    };
    const t = window.setInterval(load, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [ctx.mode, replayId, ctx.route, playing]);

  const controlReplay = (body: {
    action: string;
    speed_seconds?: number;
    start_date?: string;
    delay_days?: number;
  }) => {
    if (!replayId) return;
    setReplayBusy(true);
    api
      .controlReplay(replayId, body, ctx.route)
      .then((st) => {
        setReplayState(st);
        setReplayError(null);
        if (st.session.session_id !== replayId) {
          setReplayId(st.session.session_id);
          storeReplay(st.session.session_id);
        }
      })
      .catch((e) => setReplayError(e instanceof Error ? e.message : "Replay control failed."))
      .finally(() => setReplayBusy(false));
  };

  const inReplay = ctx.mode === "replay";
  const revealedThrough = inReplay ? replayState?.information_policy.latest_revealed_date ?? null : null;
  const historyQuery: HistoryQuery = useMemo(
    () => ({
      start: ctx.start,
      end: ctx.end,
      dayType: ctx.dayType,
      replayId: inReplay ? replayId : null,
      revealedThrough,
    }),
    [ctx.start, ctx.end, ctx.dayType, inReplay, replayId, revealedThrough]
  );

  const groupOptions = useMemo(() => {
    const seen = new Map<number, string>();
    routes.forEach((r) => {
      if (r.group_id !== null && r.group_label) seen.set(r.group_id, r.group_label.split(":")[0]);
    });
    return Array.from(seen.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([id, label]) => ({ id, label }));
  }, [routes]);

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
        {inReplay ? (
          <ReplayBanner
            state={replayState}
            busy={replayBusy}
            error={replayError}
            onControl={(action) => controlReplay({ action })}
            onOpen={() => setActiveTab("replay")}
          />
        ) : null}
      </header>
      {!loading && !error ? <ContextBar ctx={ctx} routes={routes} onChange={setCtx} /> : null}

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
                topSlot={
                  groups ? (
                    <NetworkMapPanel
                      geometries={groups.geometries}
                      routes={routes}
                      selectedRoute={selectedRoute}
                      onPickRoute={setSelectedRoute}
                      onOpenRoute={handleSelectRoute}
                    />
                  ) : null
                }
              />
            ) : null}

            {activeTab === "route" ? (
              <RouteDetailPage
                routes={routes}
                selectedRoute={selectedRoute}
                onSelectRoute={setSelectedRoute}
                onOpenScenario={handleOpenScenario}
                topSlot={
                  <RouteDailyPanel
                    route={selectedRoute}
                    query={historyQuery}
                    geometryVersion={groups?.geometries.source_snapshot ?? null}
                  />
                }
              />
            ) : null}

            {activeTab === "compare" ? (
              <ComparePage
                routes={routes}
                primaryRoute={selectedRoute}
                query={historyQuery}
                onSelectRoute={handleSelectRoute}
              />
            ) : null}

            {activeTab === "groups" && groups ? (
              <RouteGroupsPage groups={groups} onSelectRoute={handleSelectRoute} />
            ) : null}

            {activeTab === "evaluation" && evaluation ? (
              <EvaluationPage
                evaluation={evaluation}
                onSelectRoute={handleSelectRoute}
                topSlot={
                  <ForecastIssuePanel
                    inReplay={inReplay}
                    state={replayState}
                    route={selectedRoute}
                    onStartReplay={() => setCtx((c) => ({ ...c, mode: "replay" }))}
                    onUseInScenario={(route, date) => openDayScenario(route, date, "forecast")}
                  />
                }
              />
            ) : null}

            {activeTab === "review" ? (
              <ReviewListPage
                cells={reviewMeta.rows}
                period={reviewMeta.period}
                source={reviewMeta.source}
                onSelectRoute={handleSelectRoute}
                onOpenScenario={handleOpenScenario}
                topSlot={
                  <RankingSection
                    query={historyQuery}
                    groupOptions={groupOptions}
                    onSelectRoute={handleSelectRoute}
                  />
                }
              />
            ) : null}

            {activeTab === "replay" ? (
              <ReplayPage
                state={replayState}
                busy={replayBusy}
                error={replayError}
                route={selectedRoute}
                onControl={controlReplay}
                onCompare={() => setActiveTab("compare")}
                onScenario={(date) => openDayScenario(selectedRoute, date, "forecast")}
              />
            ) : null}

            {activeTab === "scenarios" ? (
              <ScenariosPage
                routes={routes}
                initialRoute={scenarioInit.route}
                initialDayGroup={scenarioInit.dayGroup}
                initialTimeBand={scenarioInit.timeBand}
                topSlot={
                  <DayScenarioPanel
                    routes={routes}
                    initialRoute={selectedRoute}
                    initialDate={dayScenarioInit.date}
                    initialSource={dayScenarioInit.source}
                  />
                }
              />
            ) : null}

            {activeTab === "gtfs" ? <GtfsUploadPage /> : null}
          </>
        )}
      </main>
      <ProvenanceLegend />
    </div>
  );
};

export default App;

