// Response types for the Stage 6 API, mirroring backend/app/routers/*.py field by field.
// Dates are ISO strings ("2026-07-31"). A value the API may leave missing is typed `| null`, so the compiler
// forces every screen to decide what "missing" looks like (it is never silently 0).

export type ISODate = string
export type DayType = 'W' | 'A' | 'U'
export type RankingMetric = 'observed_daily_demand' | 'rides_per_scheduled_trip' | 'rides_per_scheduled_hour'
export type Metric = RankingMetric | 'route_overlap_review'
export type PeriodName = 'full_matched_window' | 'development'

export type CutoffBlock = { requested: ISODate | null; applied: boolean; permitted_through: ISODate }
export type Envelope = { data_version: string; mode: 'historical_analysis'; mode_label: string; cutoff: CutoffBlock }

export type Units = {
  rides: string; scheduled_trips: string; scheduled_service_hours: string
  rides_per_scheduled_trip: string; rides_per_scheduled_hour: string
}

// ---- GET /api/data/coverage
export type MissingGroup = {
  reason: string; rows: number; routes: number; route_list: string[]; first_date: ISODate; last_date: ISODate
}
export type Archive = {
  geometry_version: string; captured_date: ISODate; applied_start: ISODate; applied_end: ISODate
  applied_days: number; bus_routes: number; scheduled_routes: number; map_lines: number
}
export type Coverage = Envelope & {
  observations: {
    label: string; first_date: ISODate; last_date: ISODate; rows: number; route_identifiers: number
    recorded_zero_rows: number
    ridership_cutoff?: ISODate; excluded_after_ridership_cutoff?: number   // only without a cutoff
  }
  schedule: {
    label: string; first_date: ISODate | null; last_date: ISODate | null; rows: number; dates: number; routes: number
    incomplete_duration_rows: number; note: string
  }
  analysis_window: { start: ISODate; end: ISODate }
  archives: Archive[]
  matching: {
    ridership_rows_in_window: number; schedule_rows: number; matched_rows: number; matched_dates: number
    matched_routes: number; schedule_conditioned_coverage_pct: number | null
    ridership_without_schedule: MissingGroup[]; schedule_without_ridership: MissingGroup[]
  }
  quality: { import_identities: Record<string, number>; import_identities_hold: boolean; note: string }
  details: {
    import_git_commit: string; built_git_commit: string; schema_sha256: string
    archive_sha256: Record<string, string>
    imported_at?: string; inputs?: unknown                                  // only without a cutoff
  }
}

// ---- GET /api/routes
export type GroupVersion = {
  group_version: string; profile_start: ISODate; profile_end: ISODate; artifact_version: string
  default_overlap_version: string
}
export type ServiceStatus = 'available' | 'no_scheduled_service' | 'insufficient_observations'
export type RouteRow = {
  route: string; route_long_name: string | null; name_geometry_version: string | null
  first_ride_date: ISODate; last_ride_date: ISODate; recorded_days: number; matched_days: number
  in_any_archive: boolean; in_group_population: boolean
  group_id: number | null; group_name: string | null; ungrouped_reason: string | null
  saturday_service_status: ServiceStatus | null; sunday_holiday_service_status: ServiceStatus | null
}
export type RoutesResponse = Envelope & {
  group_version: GroupVersion | null; groups_note: string | null
  filters: Record<string, unknown>; count: number; routes: RouteRow[]
}

// ---- GET /api/routes/{route}/history
export type DayStatus = 'matched' | 'ridership_without_schedule' | 'schedule_without_ridership'
  | 'no_service_no_record' | 'recorded_rides_only' | 'no_record'
export type HistoryDay = {
  service_date: ISODate; daytype: DayType | null; rides: number | null; selected_snapshot_id: string | null
  scheduled_trips: number | null; scheduled_service_hours: number | null; duration_complete: boolean | null
  trips_missing_duration: number | null
  rides_per_scheduled_trip: number | null; rides_per_scheduled_hour: number | null
  status: DayStatus; reason: string | null; reason_code: string | null; has_record: boolean; has_schedule: boolean
}
export type HistoryResponse = Envelope & {
  route: string; route_long_name: string | null; name_geometry_version: string | null
  range: { start: ISODate; end: ISODate; clipped_to_cutoff: boolean; schedule_window: { start: ISODate; end: ISODate } }
  labels: { rides: string; scheduled_trips: string; scheduled_service_hours: string }
  units: Units; summary: Partial<Record<DayStatus, number>>; count: number; days: HistoryDay[]
}

// ---- GET /api/network/trend
export type TrendStatus = 'recorded' | 'recorded_rides_only' | 'no_record'
export type TrendDay = {
  service_date: ISODate; daytype: DayType | null; rides: number | null; routes_reporting: number
  scheduled_trips: number | null; routes_scheduled: number | null; status: TrendStatus; reason: string | null
}
export type TrendSummary = {
  daytype: DayType; daytype_label: string; days: number
  mean_rides: number | null; median_rides: number | null; reason: string | null
}
export type TrendResponse = Envelope & {
  range: { start: ISODate; end: ISODate; clipped_to_cutoff: boolean; schedule_window: { start: ISODate; end: ISODate } }
  labels: { rides: string; scheduled_trips: string }; units: { rides: string; scheduled_trips: string }
  total_note: string; status_counts: Partial<Record<TrendStatus, number>>
  summary: TrendSummary[]; count: number; days: TrendDay[]
}

// ---- a period as sent with rankings and compare ("label" is the plain-words name to show)
export type Period = {
  name: 'full_matched_window' | 'development' | 'custom'; label: string
  start: ISODate; end: ISODate; clipped_to_cutoff: boolean
}

// ---- GET /api/rankings (three named rankings)
export type RankingRow = {
  rank: number | null; route: string; eligible: boolean; reason: string | null; observed_days: number
  scheduled_service_days: number | null; incomplete_duration_days: number
  numerator: number | null; denominator: number | null; value: number | null
}
export type RankingResponse = Envelope & {
  metric: {
    key: RankingMetric; label: string; unit: string; meaning: string; caveat: string; numerator: string; denominator: string
    numerator_label: string; denominator_label: string; spec_reference: string
  }
  period: Period
  daytype: DayType
  configuration: {
    min_observed_days: number; reference_min_observed_days: number; non_reference_gate: boolean; gate_label: string
    direction: string; ties: unknown; ratio_rule: unknown
  }
  group: { group_id: number; group_version: string } | null
  counts: { routes: number; ranked: number; unranked: number }
  rows: RankingRow[]
}

// ---- GET /api/rankings?metric=route_overlap_review
export type OverlapRow = {
  rank: number; route_a: string; route_b: string; shared_stop_count: number
  route_a_stop_count: number; route_b_stop_count: number
  jaccard_stop_overlap: number; smaller_route_stop_overlap: number
  route_a_exclusive_fraction: number; route_b_exclusive_fraction: number; interpretation: string
}
export type OverlapResponse = Envelope & {
  metric: { key: 'route_overlap_review'; label: string; meaning: string; caveat: string | null; spec_reference: string }
  geometry_version: string; default_geometry_version: string; available_geometry_versions: string[]
  counts: { pairs: number }; rows: OverlapRow[]
}

// ---- lines (compare and map)
export type LineString = { type: 'LineString'; coordinates: [number, number][] }   // [lon, lat]
export type RouteLine = {
  route: string; direction_id: number; direction_label: string; shape_id: string; tied_top_shapes: number
  line_geojson: LineString; tie_label: string | null
}
export type NoLines = { route: string; reason: string }

// ---- GET /api/routes/compare
export type Indicator = {
  label: string; unit: string; value: number | null; network_rank: number | null; eligible: boolean
  reason: string | null; numerator: number | null; denominator: number | null
}
export type CompareRoute = {
  route: string
  indicators: Record<RankingMetric, Indicator> | null
  no_matched_days_reason: string | null
  service: { mean_scheduled_trips: number | null; mean_scheduled_service_hours: number | null } | null
  coverage: {
    observed_days: number; scheduled_service_days: number | null; incomplete_duration_days: number
    recorded_days_without_schedule: number; scheduled_days_without_record: number
  }
  group?: { route: string; group_id: number | null; group_name: string | null; ungrouped_reason: string | null }
  map_lines: number
}
export type CompareResponse = Envelope & {
  period: Period
  daytype: DayType; units: Units; caveat: string
  configuration: { min_observed_days: number; gate_label: string; ranks: string }
  common_matched_days: number; comparable_note: string | null; groups_note: string | null
  routes: CompareRoute[]
  map: { geometry_version: string | null; label: string; lines: RouteLine[]; routes_without_lines: NoLines[] }
  overlap: {
    route_a: string; route_b: string; shared_stop_count: number; jaccard_stop_overlap: number
    smaller_route_stop_overlap: number; overlap_review_rank: number; interpretation: string
  }[]
}

// ---- GET /api/route-groups
export type GroupFeature = {
  feature: string; label: string; unit: string; selected_for_clustering: boolean; median: number; mean: number; min: number; max: number
}
export type RouteGroup = {
  group_id: number; name: string; size: number; routes: string[]; features: GroupFeature[]
  weekend_service: Record<string, number>
}
/** A route's own profile value. null = unavailable (with reason), never 0 and never a filled-in median.
 *  status no_scheduled_service = a structural zero: value is 0 and is plotted at 0. */
export type ProfileValueStatus = 'available' | 'no_scheduled_service' | 'insufficient_observations' | 'unavailable'
export type RouteProfileValue = {
  feature: string; label: string; unit: string; value: number | null; status: ProfileValueStatus; reason: string | null
}
export type RouteValues = {
  route: string; group_id: number | null; weekday_observed_days: number; values: RouteProfileValue[]
}
export type GroupsResponse = Envelope & (
  | { available: false; reason: string }
  | {
      available: true; group_version: string; artifact_version: string; artifact_sha256: string; built_git_commit: string
      profile_period: { start: ISODate; end: ISODate; note: string }
      method: { k: number; selected_features: string[]; selected_feature_labels: string[]; algorithm: string; k_rule: string; k_table: string }
      caveats: string[]; groups: RouteGroup[]; ungrouped: { route: string; reason: string }[]
      route_values_note: string; route_values: RouteValues[]
    }
)

// ---- GET /api/map/lines
export type MapLine = RouteLine & { route_long_name: string | null; point_count: number; points_sent: number; group_id: number | null }
export type MapLinesResponse = Envelope & {
  geometry_version: string; applied: { start: ISODate; end: ISODate }; label: string
  display: { simplify_m: number; note: string; points_stored: number; points_sent: number }
  groups_note: string | null; count: number; lines: MapLine[]; routes_without_lines: NoLines[]
}
