export const NOT_AVAILABLE = "not available";

export function fmtNum(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NOT_AVAILABLE;
  }
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NOT_AVAILABLE;
  }
  return Math.round(value).toLocaleString("en-US");
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NOT_AVAILABLE;
  }
  return `${value.toFixed(digits)}%`;
}

export function fmtSharePct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NOT_AVAILABLE;
  }
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatTimeBandLabel(tb: string): string {
  const map: Record<string, string> = {
    early_morning: "Early Morning (04:00–06:59)",
    morning_peak: "Morning Peak (07:00–09:59)",
    midday: "Midday (10:00–15:59)",
    evening_peak: "Evening Peak (16:00–18:59)",
    night: "Night (19:00–03:59)",
  };
  return map[tb] ?? tb;
}

export function formatReviewCategory(cat: string): string {
  const map: Record<string, string> = {
    fewer_trips_candidate: "Fewer trips review",
    more_trips_candidate: "More trips review (high riders per trip)",
    within_threshold: "Within threshold",
    no_change_watch: "Within threshold (watch)",
    shared_corridor_overlap_watch: "Shared corridor watch",
  };
  return map[cat] ?? cat;
}

export function formatReallocationRole(role: string): string {
  if (role === "donor_trim") return "Fewer trips";
  if (role === "recipient_add") return "More trips";
  return role.replace(/_/g, " ");
}

export function formatMergeVerdict(verdict: string): string {
  const map: Record<string, string> = {
    keep_separate_unique_stops: "Keep separate (unique stops)",
    partial_segment_spacing_only_unique_branches: "Keep separate (unique stops)",
    do_not_merge_coordinate_headways_only: "Do not merge (high demand)",
    candidate_for_offpeak_consolidation_study: "Study off-peak consolidation",
    monitor_shared_corridor_no_merge: "Monitor overlap (no merge)",
  };
  return map[verdict] ?? verdict.replace(/_/g, " ");
}

export function formatDbscanLabel(label: string | null | undefined): string {
  if (!label) return NOT_AVAILABLE;
  if (label.startsWith("Noise")) return "DBSCAN: not in any group";
  return label;
}

export interface ApiEnvelope<T = Record<string, unknown>> {
  period: string;
  source: string;
  count: number;
  rows: T[];
  metadata?: Record<string, unknown> | null;
}

export interface OverviewData {
  period: string;
  source: string;
  version: {
    git_commit: string;
    git_sha: string;
    export_date: string;
    study_window: string;
    data_sources: string;
    official_test_runs_logged: number;
    official_test_log: string[];
    scenario_assumption: string;
    terminology_note: string;
  };
  overview: {
    study_window: Record<string, string>;
    sources: Array<Record<string, unknown>>;
    gtfs_versions: Array<Record<string, unknown>>;
    splits: Array<{
      set: string;
      start_date: string;
      end_date: string;
      rows: number;
      routes: number;
    }>;
    cleaning: {
      raw_rows_jan_sep: number;
      clean_rows_jan_sep: number;
      routes_kept: number;
      zero_ridership_rows_kept: number;
      zero_ridership_share: number;
      validation_issues: Record<string, number>;
      dropped_routes: Array<{
        route: string;
        ridership: number;
        transfers: number;
        decision: string;
        reason: string;
      }>;
      kept_routes: string[];
    };
    exclusions: {
      missing_ridership_dates: string[];
      storm_dates: string[];
      public_holidays: string[];
      holiday_details: Record<string, string>;
      excluded_outage_blocks: Array<{ date: string; hours: string; reason: string }>;
      outlier_route_hours: Array<{ route: string; date: string; hours: string; reason: string }>;
      october_outage_hours_flagged: number;
    };
    row_counts: Record<string, number>;
  };
}

export interface NetworkDailyRow {
  date: string;
  day_of_week: string;
  day_type: string;
  is_weekend: boolean;
  is_public_holiday: boolean;
  holiday_schedule: boolean;
  is_storm: boolean;
  has_outlier: boolean;
  total_ridership: number | null;
  total_trips_running: number | null;
  total_service_hours: number | null;
  active_routes: number | null;
  is_missing: boolean;
  riders_per_trip: number | null;
  riders_per_service_hour: number | null;
  period_tag: string;
}

export interface NetworkHourlyRow {
  period: string;
  day_type: string;
  hour: number;
  time_band: string;
  n_days: number;
  mean_network_ridership: number | null;
  q25_network_ridership: number | null;
  median_network_ridership: number | null;
  q75_network_ridership: number | null;
  mean_network_trips: number | null;
  mean_network_service_hours: number | null;
  mean_riders_per_trip: number | null;
  mean_riders_per_service_hour: number | null;
}

export interface RouteSummary {
  route: string;
  route_short_name: string;
  route_long_name: string;
  service_type: string;
  stop_count: number | null;
  route_length_km: number | null;
  trips_per_weekday: number | null;
  trips_per_saturday: number | null;
  trips_per_sunday: number | null;
  first_departure: string | null;
  last_departure: string | null;
  morning_peak_avg_gap_min: number | null;
  avg_trip_duration_min: number | null;
  avg_scheduled_speed_kmh: number | null;
  avg_daily_riders: number | null;
  peak_riders_per_trip: number | null;
  total_stops: number | null;
  exclusive_stops: number | null;
  exclusive_stop_share: number | null;
  group_id: number | null;
  group_label: string | null;
  is_outlier_removed_before_kmeans: boolean;
  dbscan_eps180_label: string | null;
  pc1_40: number | null;
  pc2_40: number | null;
  weekday_riders_est: number | null;
  weekend_to_weekday_ratio: number | null;
  morning_peak_share: number | null;
  night_share: number | null;
  peak_riders_per_service_hour: number | null;
  demand_variability: number | null;
  p75_weekday: number | null;
  p75_saturday: number | null;
  p75_sunday: number | null;
}

export interface RouteGeometry {
  route: string;
  center: [number, number] | null;
  polylines: Array<{ direction_id: string; coords: Array<[number, number]> }>;
  directions: Array<{
    direction_id: string;
    start_stop_name: string | null;
    end_stop_name: string | null;
    stop_count: number;
  }>;
  sample_stops: Array<{ stop_id: string; stop_name: string; lat: number; lon: number }>;
}

export interface RouteDetailData {
  period: string;
  source: string;
  route: string;
  profile: RouteSummary;
  thresholds: Array<{ route: string; day_type: string; threshold_p75: number | null }>;
  hourly_patterns: Array<{
    period: string;
    route: string;
    day_type: string;
    hour: number;
    time_band: string;
    n_days: number;
    mean_ridership: number | null;
    q25_ridership: number | null;
    median_ridership: number | null;
    q75_ridership: number | null;
    mean_trips_running: number | null;
    mean_service_hours: number | null;
    mean_riders_per_trip: number | null;
    mean_riders_per_service_hour: number | null;
  }>;
  time_band_performance: Array<{
    route: string;
    day_type: string;
    time_band: string;
    days_count: number;
    total_riders: number | null;
    total_trips: number | null;
    total_service_hours: number | null;
    riders_per_trip: number | null;
    riders_per_service_hour: number | null;
  }>;
  review_cells: ReviewCell[];
  overlaps: Array<{
    route_1: string;
    route_2: string;
    partner_route: string;
    shared_stops_count: number;
    smaller_route_stops: number;
    overlap_share: number;
    jaccard_similarity: number;
    overlap_category: string;
  }>;
  geometry: RouteGeometry | null;
}

export interface RouteForecastData {
  period: string;
  source: string;
  route: string;
  validation_summary: {
    hgb: Record<string, unknown> | null;
    baseline_4wk: Record<string, unknown> | null;
  };
  test_summary: {
    subsets: Array<Record<string, unknown>>;
    primary: Record<string, unknown> | null;
  };
  test_classification: Array<Record<string, unknown>>;
  october_summary: Record<string, unknown> | null;
  october_daily: Array<{
    date: string;
    day_of_week: string;
    day_type: string;
    day_group: string;
    active_hours: number;
    actual_ridership: number | null;
    pred_ridership: number | null;
    baseline_4wk_ridership: number | null;
    actual_high_hours: number | null;
    pred_high_hours: number | null;
  }>;
  october_hourly: Array<Record<string, unknown>>;
  note: string;
}

export interface ReviewCell {
  route: string;
  route_long_name: string;
  service_type: string;
  day_group: string;
  days_count: number;
  days_in_day_group: number;
  dates_covered: string;
  time_band: string;
  time_band_label: string;
  group_id: number;
  route_group: string;
  active_hours: number;
  total_trips_running: number;
  avg_trips_per_day: number;
  total_service_hours: number;
  avg_service_hours_per_day: number;
  pct_of_day_group_service_hours: number;
  total_obs_ridership: number;
  obs_riders_per_trip: number;
  obs_riders_per_service_hour: number;
  hist_jan_jul_riders_per_service_hour: number | null;
  obs_vs_jan_jul_pct: number | null;
  trend_direction: string;
  mean_threshold_p75: number | null;
  high_demand_hours: number;
  high_demand_freq_pct: number;
  exclusive_stop_share: number;
  top_overlap_partner: string | null;
  top_overlap_share: number | null;
  top_overlap_category: string | null;
  top_shared_corridor_partner: string | null;
  top_shared_corridor_share: number | null;
  is_merge_check_candidate: boolean;
  review_category: string;
  recommended_action: string;
  reason: string;
}

export interface ScenarioResult {
  route: string;
  day_group: string;
  days_count: number;
  days_in_day_group: number;
  time_band: string;
  review_category: string;
  group_id: number;
  exclusive_stop_share: number;
  requested_trip_change_pct?: number | null;
  scenario_trip_change_pct: number;
  effective_trip_change_pct: number;
  guardrail_capped?: boolean;
  max_recommended_cut_pct?: number | null;
  guardrail_warning?: string | null;
  base_trips: number;
  new_trips: number;
  delta_trips: number;
  base_service_hours: number;
  new_service_hours: number;
  delta_service_hours: number;
  delta_service_hours_per_day: number | null;
  pct_of_day_group_service_hours: number | null;
  pct_of_window_network_service_hours: number | null;
  constant_obs_ridership: number;
  base_riders_per_trip: number;
  new_riders_per_trip: number | null;
  base_riders_per_service_hour: number;
  new_riders_per_service_hour: number | null;
  base_high_demand_hours: number;
  sim_high_demand_hours: number;
  high_demand_hours_delta: number;
  guardrail_status: string;
}

export interface ScenarioResponse {
  assumption: string;
  assumption_detail: string;
  period: string;
  source: string;
  scenario: ScenarioResult;
}

export interface GroupsData {
  period: string;
  source: string;
  metadata: {
    outlier_route: string;
    selected_k_on_40_routes: number;
    selected_features: string[];
    pca_explained_variance_ratio: number[];
    pca_total_variance_explained: number;
    group_metadata: Record<string, Record<string, unknown>>;
    overlap_note: string;
    k2_vs_k3_decision_note: string;
  };
  pca_variance?: Array<{
    component: string;
    explained_variance_ratio: number;
    explained_variance_pct: number;
    cumulative_variance_ratio: number;
    cumulative_variance_pct: number;
    n_routes: number;
    excluded_outlier: string;
  }>;
  routes: Array<Record<string, unknown>>;
  group_profiles: Array<Record<string, unknown>>;
  k_selection: Array<Record<string, unknown>>;
  k2_vs_k3: Array<Record<string, unknown>>;
  dbscan_summary: Array<Record<string, unknown>>;
  geometries: {
    source_snapshot: string;
    center: [number, number];
    routes: Record<string, RouteGeometry>;
  };
}

export interface EvaluationData {
  period: string;
  source: string;
  validation: {
    period: string;
    forecast_comparison: Array<Record<string, unknown>>;
    forecast_weekly: Array<Record<string, unknown>>;
    classification_comparison: Array<Record<string, unknown>>;
    notes: string[];
  };
  test: {
    period: string;
    forecast_overall: Array<Record<string, unknown>>;
    forecast_by_week: Array<Record<string, unknown>>;
    forecast_by_day_type: Array<Record<string, unknown>>;
    forecast_by_time_band: Array<Record<string, unknown>>;
    forecast_by_route: Array<Record<string, unknown>>;
    classification_overall: Array<Record<string, unknown>>;
    notes: string[];
  };
  october: {
    period: string;
    headline: string;
    forecast_summary: Array<Record<string, unknown>>;
    forecast_by_day: Array<Record<string, unknown>>;
    forecast_by_route: Array<Record<string, unknown>>;
    classification_summary: Array<Record<string, unknown>>;
    diagnostic_checks: Array<Record<string, unknown>>;
    limitations: string[];
  };
  official_test_runs_logged: number;
  official_test_log: string[];
}

export interface GtfsUploadResponse {
  filename: string;
  file_size_mb: number;
  period: string;
  source: string;
  integrity: Record<string, unknown>;
  summary: {
    routes_in_feed: number;
    routes_with_trips: number;
    study_routes_matched: number;
    non_study_routes_schedule_only: number;
    overlapping_pairs_total: number;
    calendar_exceptions_count: number;
    representative_weekday_date: string;
  };
  network_hourly_schedule: Array<{
    hour: number;
    trips_starting: number;
    trips_running: number;
    service_hours: number;
  }>;
  routes: Array<{
    route_id: string;
    route_short_name: string;
    route_long_name: string;
    service_type: string;
    stop_count: number;
    exclusive_stops: number;
    exclusive_stop_share: number | null;
    trips_per_weekday: number;
    trips_per_saturday: number;
    trips_per_sunday: number;
    first_departure: string | null;
    last_departure: string | null;
    avg_trip_duration_min: number | null;
    route_length_km: number | null;
    avg_scheduled_speed_kmh: number | null;
    has_ridership_history: boolean;
    study_group_label: string | null;
    study_avg_daily_riders: number | null;
    study_peak_riders_per_trip: number | null;
    status_note: string;
  }>;
  top_overlaps: Array<Record<string, unknown>>;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const errBody = (await res.json()) as {
        detail?: string | Array<{ msg?: string; loc?: unknown[] }>;
      };
      if (typeof errBody.detail === "string") {
        detail = errBody.detail;
      } else if (Array.isArray(errBody.detail) && errBody.detail.length > 0) {
        detail = errBody.detail
          .map((item) => {
            const loc = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
            return loc ? `${loc}: ${item.msg ?? "invalid"}` : (item.msg ?? "Invalid request");
          })
          .join("; ");
      }
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  getOverview: () => fetchJson<OverviewData>("/api/overview"),
  getNetworkDaily: (params?: { start_date?: string; end_date?: string; period_tag?: string }) => {
    const q = new URLSearchParams();
    if (params?.start_date) q.set("start_date", params.start_date);
    if (params?.end_date) q.set("end_date", params.end_date);
    if (params?.period_tag) q.set("period_tag", params.period_tag);
    const qs = q.toString();
    return fetchJson<ApiEnvelope<NetworkDailyRow>>(`/api/network/daily${qs ? `?${qs}` : ""}`);
  },
  getNetworkHourly: (period: "jan_sep_typical" | "aug_oct_typical" = "jan_sep_typical") =>
    fetchJson<ApiEnvelope<NetworkHourlyRow>>(`/api/network/hourly?period=${period}`),
  getRoutes: () => fetchJson<ApiEnvelope<RouteSummary>>("/api/routes"),
  getRouteDetail: (route: string) =>
    fetchJson<RouteDetailData>(`/api/routes/${encodeURIComponent(route)}`),
  getRouteForecast: (route: string) =>
    fetchJson<RouteForecastData>(`/api/routes/${encodeURIComponent(route)}/forecast`),
  getReview: (params?: {
    day_group?: string;
    review_category?: string;
    time_band?: string;
    route?: string;
    group_id?: string;
    sort_by?: string;
    sort_dir?: string;
  }) => {
    const q = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== "") q.set(k, v);
      });
    }
    const qs = q.toString();
    return fetchJson<ApiEnvelope<ReviewCell>>(`/api/review${qs ? `?${qs}` : ""}`);
  },
  getScenariosPlan: () => fetchJson<ApiEnvelope<Record<string, unknown>>>("/api/scenarios/plan"),
  runScenario: (payload: {
    route: string;
    day_group: string;
    time_band: string;
    trip_change_pct: number;
  }) =>
    fetchJson<ScenarioResponse>("/api/scenarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getGroups: () => fetchJson<GroupsData>("/api/groups"),
  getEvaluation: () => fetchJson<EvaluationData>("/api/evaluation"),
  uploadGtfs: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetchJson<GtfsUploadResponse>("/api/gtfs/upload", {
      method: "POST",
      body: form,
    });
  },

  // ---- Observed history, comparison and rankings -------------------------
  getRouteDaily: (route: string, ctx: HistoryQuery) =>
    fetchJson<RouteDailyData>(
      `/api/routes/${encodeURIComponent(route)}/daily?${historyQs(ctx)}`
    ),
  compareRoutes: (routes: string[], ctx: HistoryQuery) =>
    fetchJson<CompareData>(
      `/api/compare?routes=${routes.map(encodeURIComponent).join(",")}&${historyQs(ctx)}`
    ),
  getRankings: (params: {
    indicator: string;
    direction: "asc" | "desc";
    day_type: string;
    min_days?: number;
    group_id?: number | null;
    ctx: HistoryQuery;
  }) => {
    const q = new URLSearchParams({
      indicator: params.indicator,
      direction: params.direction,
      day_type: params.day_type,
    });
    if (params.min_days) q.set("min_days", String(params.min_days));
    if (params.group_id !== null && params.group_id !== undefined) q.set("group_id", String(params.group_id));
    return fetchJson<RankingData>(`/api/rankings?${q.toString()}&${historyQs({ ...params.ctx, dayType: "all" })}`);
  },

  // ---- Replay -------------------------------------------------------------
  listReplays: () => fetchJson<{ rows: ReplaySession[]; count: number }>("/api/replays?limit=5"),
  createReplay: (payload: { start_date: string; delay_days: number; speed_seconds: number }) =>
    fetchJson<ReplayState>("/api/replays", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getReplay: (id: string, route?: string) =>
    fetchJson<ReplayState>(
      `/api/replays/${encodeURIComponent(id)}${route ? `?route=${encodeURIComponent(route)}` : ""}`
    ),
  controlReplay: (
    id: string,
    body: { action: string; speed_seconds?: number; start_date?: string; delay_days?: number },
    route?: string
  ) =>
    fetchJson<ReplayState>(
      `/api/replays/${encodeURIComponent(id)}/control${route ? `?route=${encodeURIComponent(route)}` : ""}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    ),
  getReplayForecasts: (id: string, route: string, targetDate: string) =>
    fetchJson<{ count: number; rows: ReplayForecastRecord[]; provenance: string }>(
      `/api/replays/${encodeURIComponent(id)}/forecasts?route=${encodeURIComponent(route)}&target_date=${targetDate}`
    ),

  // ---- Single-day scenarios ----------------------------------------------
  runDayScenario: (payload: DayScenarioRequest) =>
    fetchJson<DayScenarioResponse>("/api/scenarios/day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getSavedScenarios: () =>
    fetchJson<{ count: number; rows: SavedScenario[]; source: string }>("/api/scenarios/saved"),
};

// ---------------------------------------------------------------------------
// Shared view context (mode, route, dates, day type) used by several screens.
// ---------------------------------------------------------------------------

export const OBS_START = "2026-08-01";
export const OBS_END = "2026-10-31";
export const REPLAY_START = "2026-10-18";
export const REPLAY_END = "2026-10-31";
export const DAY_TYPES = ["Typical Weekday", "Typical Saturday", "Typical Sunday"] as const;

export interface HistoryQuery {
  start: string;
  end: string;
  dayType: string; // "all" or one of DAY_TYPES
  replayId?: string | null;
  revealedThrough?: string | null; // not sent; lets screens refetch when the replay reveals more days
}

function historyQs(ctx: HistoryQuery): string {
  const q = new URLSearchParams({ start: ctx.start, end: ctx.end });
  if (ctx.dayType && ctx.dayType !== "all") q.set("day_type", ctx.dayType);
  if (ctx.replayId) q.set("replay_id", ctx.replayId);
  return q.toString();
}

export interface ExcludedDate {
  date: string;
  reason: string;
}

export interface PeriodMetrics {
  observed_days: number;
  observed_hours: number;
  total_boardings: number | null;
  total_service_hours: number | null;
  total_trips_running: number | null;
  mean_daily_boardings: number | null;
  riders_per_service_hour: number | null;
  riders_per_trip: number | null;
  share_hours_above_p75: number | null;
  avg_trips_running_per_day: number | null;
}

export interface ReplayCap {
  replay_id: string;
  latest_revealed_date: string;
}

export interface RouteDailyData {
  route: string;
  period: string;
  source: string;
  provenance: string;
  replay: ReplayCap | null;
  excluded_dates: ExcludedDate[];
  summary: PeriodMetrics | null;
  rows: Array<{
    date: string;
    day_type: string;
    boardings: number;
    service_hours: number;
    trips_running: number;
    active_hours: number;
    riders_per_service_hour: number | null;
  }>;
}

export interface CompareRoute {
  route: string;
  profile: Record<string, string | number | null> | null;
  metrics: PeriodMetrics | null;
  time_bands: Array<PeriodMetrics & { time_band: string }>;
  hourly: Array<{ hour: number; mean_boardings: number }>;
  daily: Array<{ date: string; boardings: number }>;
  geometry: RouteGeometry | null;
}

export interface CompareData {
  period: string;
  source: string;
  provenance: string;
  geometry_version: string | null;
  replay: ReplayCap | null;
  excluded_dates: ExcludedDate[];
  routes: CompareRoute[];
  shared_stops: Array<{
    route_1: string;
    route_2: string;
    shared_stops_count: number;
    overlap_share: number;
    jaccard_similarity: number;
    overlap_category: string;
  }>;
}

export interface IndicatorDefinition {
  label: string;
  numerator: string;
  denominator: string;
  default_direction: "asc" | "desc";
  meaning: string;
}

export interface RankingRow extends PeriodMetrics {
  route: string;
  route_long_name: string | null;
  group_id: number | null;
  group_label: string | null;
  eligible: boolean;
  ineligible_reason: string | null;
  rank: number | null;
}

export interface RankingData {
  period: string;
  source: string;
  provenance: string;
  replay: ReplayCap | null;
  excluded_dates: ExcludedDate[];
  resolved_config: {
    config_version: string;
    indicator: string;
    indicator_definition: IndicatorDefinition;
    direction: string;
    day_type: string;
    min_observed_days: number;
    min_observed_days_reason: string;
    min_avg_trips_running_per_day: number;
    group_id: number | null;
    ties: string;
  };
  indicators: Record<string, IndicatorDefinition>;
  count: number;
  eligible_count: number;
  rows: RankingRow[];
  sensitivity: Array<{ min_days: number; eligible_routes: number; top_5: string[] }>;
}

export interface ReplaySession {
  session_id: string;
  created_at: string;
  start_date: string;
  end_date: string;
  clock_date: string;
  delay_days: number;
  speed_seconds: number;
  status: "paused" | "playing" | "completed";
  status_label?: string;
  model_version: string;
  schedule_snapshot: string;
  data_version: string;
  replaced_by: string | null;
}

export interface ReplayDailyRow {
  date: string;
  forecast_boardings: number;
  baseline_boardings: number | null;
  actual_boardings: number | null;
  revealed: boolean;
  hours: number;
  scheduled_departures: number | null;
}

export interface ReplayScores {
  revealed_days: number;
  scored_hours: number;
  model_wape_pct: number | null;
  baseline_wape_pct: number | null;
  unscored_hours_missing_baseline?: number;
}

export interface ReplayState {
  mode: string;
  session: ReplaySession;
  virtual_date: string;
  completed: boolean;
  supported_range: { start: string; end: string };
  allowed_delays: number[];
  information_policy: {
    issue_time: string;
    horizon: string;
    delay_days: number;
    latest_ridership_date_used: string;
    latest_revealed_date: string;
    schedule_snapshot: string;
    model_version: string;
    note: string;
  };
  network_daily: ReplayDailyRow[];
  network_scores: ReplayScores;
  forecast_record_count: number;
  route_detail: {
    route: string;
    daily: ReplayDailyRow[];
    scores: ReplayScores;
    current_day: string;
    current_day_hourly: Array<{
      hour: number;
      pred_boardings: number;
      baseline_boardings: number | null;
      trips_running: number;
      trips_starting: number | null;
      service_hours: number;
      lags_available_count: number;
      status: string;
      issued_at: string;
      latest_ridership_date_used: string;
    }>;
    last_revealed_date: string | null;
    last_revealed_hourly: Array<{
      hour: number;
      pred_boardings: number;
      baseline_boardings: number | null;
      actual_ridership: number | null;
      trips_running: number;
    }>;
  } | null;
  source: string;
}

export interface ReplayForecastRecord {
  session_id: string;
  target_date: string;
  route: string;
  hour: number;
  issued_at: string;
  saved_at_wall: string;
  latest_ridership_date_used: string;
  delay_days: number;
  model_version: string;
  schedule_snapshot: string;
  trips_running: number;
  service_hours: number;
  lags_available_count: number;
  pred_boardings: number;
  baseline_boardings: number | null;
  status: string;
}

export interface DayScenarioRequest {
  route: string;
  date: string;
  demand_source: "observed" | "forecast";
  trip_change_pct: number;
  demand_multiplier: number;
  apply_guardrail_cap: boolean;
  save: boolean;
  label?: string;
}

export interface DayMetrics {
  boardings: number;
  trips_running: number;
  service_hours: number;
  riders_per_service_hour: number | null;
  riders_per_trip: number | null;
  hours_above_p75: number;
  active_hours: number;
  max_hour_riders_per_trip: number | null;
  scheduled_departures: number | null;
}

export interface DayScenarioResponse {
  provenance: string;
  demand_label: string;
  baseline_version: { demand: string; schedule: string };
  inputs: {
    route: string;
    date: string;
    day_type: string;
    demand_source: string;
    trip_change_pct_requested: number;
    trip_change_pct_applied: number;
    demand_multiplier: number;
    apply_guardrail_cap: boolean;
  };
  changed_parameters: string[];
  assumptions: string[];
  result: {
    baseline: DayMetrics;
    stress_only: DayMetrics;
    scenario: DayMetrics;
    guardrail_capped: boolean;
    warnings: string[];
  };
  hourly: Array<{
    hour: number;
    baseline_trips: number;
    scenario_trips: number;
    baseline_boardings: number;
    scenario_boardings: number;
    baseline_riders_per_trip: number | null;
    scenario_riders_per_trip: number | null;
    threshold_p75: number;
  }>;
  scenario_id: string | null;
  saved_at: string | null;
}

export interface SavedScenario {
  scenario_id: string;
  created_at: string;
  label: string | null;
  inputs: DayScenarioResponse["inputs"] & { demand_label: string; changed_parameters: string[] };
  result: DayScenarioResponse["result"];
}

