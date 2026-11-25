/** TypeScript interfaces strictly aligned with Milestone 8 FastAPI OpenAPI schemas. */

export interface HealthCheckResponse {
  status: string;
  message: string;
  project: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface PaginationMeta {
  total: number;
  offset: number;
  limit: number;
  returned: number;
  has_more: boolean;
}

export interface RouteSummaryItem {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  route_type: number;
  is_rail: boolean;
  operational_cluster: number | null;
  regional_partition: string | null;
  scheduled_trips: number;
  service_span_hours: number;
  am_headway_min: number | null;
  forecasted_daily_demand: number | null;
}

export interface RouteListResponse {
  data: RouteSummaryItem[];
  pagination: PaginationMeta;
  filters?: Record<string, unknown>;
}

export interface RouteOperationalMetrics {
  scheduled_trips: number;
  service_span_hours: number;
  am_headway_min: number | null;
  route_length_km: number;
  unique_stops_count: number;
  operational_cluster_k3: number | null;
  operational_cluster_label: string | null;
}

export interface RouteDemandMetrics {
  demand_metrics_available: boolean;
  historical_mean_daily_rides: number | null;
  forecasted_daily_demand: number | null;
  rides_per_trip: number | null;
  load_intensity_factor: number | null;
}

export interface RouteHubMetrics {
  hub_stop_count: number;
  hub_stop_ratio: number;
  hub_weighted_importance: number;
  hub_connectivity_index: number;
}

export interface RouteCorridorMetrics {
  max_corridor_overlap: number;
  mean_corridor_overlap: number;
  shared_consecutive_stop_count: number;
  corridor_duplication_ratio: number;
  corridor_duplication_index: number;
}

export interface RouteDetailResponse {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  route_type: number;
  is_rail: boolean;
  regional_partition: string | null;
  operational: RouteOperationalMetrics;
  demand: RouteDemandMetrics;
  hubs: RouteHubMetrics;
  corridor: RouteCorridorMetrics;
}

export interface RankingPillars {
  demand_pressure: number;
  service_provision: number;
  network_hubs: number;
  corridor_structure: number;
}

export interface RankingItem {
  rank: number;
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  is_rail: boolean;
  track: string;
  profile: string;
  overall_score: number;
  percentile_rank: number;
  topsis_score: number;
  topsis_rank: number;
  scheduled_trips: number;
  service_span_hours: number;
  am_headway_min: number | null;
  corridor_duplication_index: number;
  operational_cluster: number | null;
  regional_partition: string | null;
  pillars: RankingPillars;
  contributions: Record<string, number | null>;
  original_weights: Record<string, number>;
  effective_weights: Record<string, number>;
  valid_weight_coverage: number;
  is_headway_missing: boolean;
  missing_criteria: string[];
}

export interface RankingListResponse {
  track: string;
  profile: string;
  total_routes: number;
  data: RankingItem[];
  pagination: PaginationMeta;
  filters?: Record<string, unknown>;
}

export interface FeatureDriver {
  criterion: string;
  contribution: number;
  effective_weight: number;
}

export interface RouteExplanationResponse {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  is_rail: boolean;
  operational_cluster_label: string | null;
  regional_partition: string | null;
  track: string;
  profile: string;
  overall_score: number;
  rank: number;
  total_routes: number;
  percentile_rank: number;
  topsis_score: number;
  topsis_rank: number;
  pillars: RankingPillars;
  criterion_scores: Record<string, number | null>;
  original_weights: Record<string, number>;
  effective_weights: Record<string, number>;
  contributions: Record<string, number | null>;
  missing_criteria: string[];
  is_headway_missing: boolean;
  valid_weight_coverage: number;
  top_positive_drivers: FeatureDriver[];
  top_negative_drivers: FeatureDriver[];
  narrative: string;
}

export interface SensitivityScenarioItem {
  scenario_id: string;
  track: string;
  target_criterion: string;
  delta: number;
  spearman_rho: number;
  mean_absolute_rank_shift: number;
  max_rank_shift: number;
  top_10_overlap: number;
  top_20_overlap: number;
}

export interface SensitivityListResponse {
  total_scenarios: number;
  data: SensitivityScenarioItem[];
  filters?: Record<string, unknown>;
}

export interface DateRangeMeta {
  start_date: string;
  end_date: string;
}

export interface RidershipMethodologyMeta {
  source_table?: string;
  granularity: string;
  metric_definition?: string;
  missing_dates_policy?: string;
}

export interface RidershipObservation {
  period: string;
  total_rides: number | null;
  observation_days: number | null;
  weekday_avg_rides: number | null;
  saturday_avg_rides: number | null;
  sunday_avg_rides: number | null;
  daytype: string | null;
  day_of_week: number | null;
  is_weekend: boolean | null;
  rides: number | null;
}

export interface RidershipTimeseriesResponse {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  route_type: number;
  is_rail: boolean;
  ridership_available: boolean;
  unavailable_reason: string | null;
  requested_date_range: DateRangeMeta;
  actual_date_range: DateRangeMeta | null;
  observation_count: number;
  total_observations: number;
  offset: number;
  limit: number | null;
  has_more: boolean;
  methodology: RidershipMethodologyMeta;
  data: RidershipObservation[];
}

export interface CoordinatePair {
  lat: number | null;
  lon: number | null;
  coordinates_available: boolean;
}

export interface SpatialMethodologyMeta {
  source_artifact: string;
  demand_proxy_note?: string;
}

export interface HubRankingItem {
  rank: number;
  stop_id: string;
  stop_name: string;
  coordinates: CoordinatePair;
  config: string;
  hub_score: number;
  total_visits: number;
  routes_served: number;
  attributed_demand_proxy: number;
  demand_intensity: number;
}

export interface TopHubsResponse {
  config: string;
  total_top_hubs: number;
  data: HubRankingItem[];
  pagination: PaginationMeta;
  methodology: SpatialMethodologyMeta;
}

export interface SpatialStopHubItem {
  stop_id: string;
  stop_name: string;
  coordinates: CoordinatePair;
  dbscan_cluster: number;
  is_noise_point: boolean;
  hub_ranking_eligible: boolean;
  rank: number | null;
  hub_score: number | null;
  total_visits: number | null;
  routes_served: number | null;
  attributed_demand_proxy: number | null;
  demand_intensity: number | null;
}

export interface BoundingBoxMeta {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
}

export interface SpatialHubsListResponse {
  config: string;
  data: SpatialStopHubItem[];
  pagination: PaginationMeta;
  bounding_box: BoundingBoxMeta | null;
  filters?: Record<string, unknown>;
  methodology: SpatialMethodologyMeta;
}

export interface ClusterSummaryResponse {
  snapshot_id: string;
  representative_service_date: string;
  demand_attribution_period: string;
  boarding_stops_input_count: number;
  active_stop_visits_count: number;
  dbscan_parameters: Record<string, unknown>;
  dbscan_cluster_count: number;
  dbscan_noise_stop_count: number;
  dbscan_chained_cluster_count: number;
  kmeans_parameters: Record<string, unknown>;
  kmeans_eligible_stops_count: number;
  hub_ranking_sensitivity: Record<string, unknown>;
  coverage_metrics: Record<string, unknown>;
  methodology: SpatialMethodologyMeta;
}

export interface CorridorMethodologyMeta {
  source_artifacts?: string[];
  metric_distinctions?: string;
  [key: string]: unknown;
}

export interface CorridorClusterItem {
  pattern_id: string;
  route_id: string;
  direction_id: number;
  route_short_name: string | null;
  route_long_name: string | null;
  is_rail: boolean | null;
  operational_cluster_label: string | null;
  k: number;
  cluster_type: string;
  cluster_id: number;
  buffer_cluster_id: number | null;
  frechet_cluster_id: number | null;
  length_km: number | null;
  scheduled_trip_count: number | null;
  hub_stop_count: number | null;
  hub_stop_ratio: number | null;
}

export interface CorridorClusterListResponse {
  k: number;
  cluster_type: string;
  data: CorridorClusterItem[];
  pagination: PaginationMeta;
  filters?: Record<string, unknown>;
  methodology: CorridorMethodologyMeta;
}

export interface CoRoutingPeerItem {
  peer_pattern_id: string;
  peer_route_id: string;
  peer_direction_id: number | null;
  similarity_score: number | null;
  metric_type: string;
}

export interface SharedStopSequenceItem {
  pattern_a: string;
  pattern_b: string;
  peer_pattern_id: string;
  peer_route_id: string;
  sequence_length: number;
  start_stop_id: string;
  end_stop_id: string;
  shared_stops: string[];
}

export interface PatternCoRoutingProfile {
  pattern_id: string;
  route_id: string;
  direction_id: number;
  length_km: number | null;
  scheduled_trip_count: number | null;
  hub_stop_count: number | null;
  hub_stop_ratio: number | null;
  buffer_cluster_k3: number | null;
  frechet_cluster_k3: number | null;
  missing_buffer_entries_count: number;
  missing_jaccard_entries_count: number;
  geographic_overlap_peers: CoRoutingPeerItem[];
  stop_jaccard_peers: CoRoutingPeerItem[];
  shared_consecutive_sequences: SharedStopSequenceItem[];
}

export interface RouteCoRoutingResponse {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  is_rail: boolean;
  operational_cluster_label: string | null;
  corridor_duplication_index: number | null;
  patterns: PatternCoRoutingProfile[];
  methodology: CorridorMethodologyMeta;
}

export interface HistoricalPredictionItem {
  route_id: string;
  date: string;
  daytype: string;
  actual_rides: number | null;
  predicted_rides: number | null;
  absolute_error: number | null;
  percentage_error: number | null;
  baseline_seasonal_naive_prediction: number | null;
  baseline_b_strategy: string | null;
  fallback_baseline_b: boolean | null;
}

export interface HistoricalForecastResponse {
  forecast_scope: "historical_evaluation_only";
  future_forecasting_supported: false;
  future_forecasting_note: string;
  tier: "tier1" | "tier2";
  period: "validation" | "test" | "august_holdout";
  model_identifier: string;
  evaluation_start: string;
  evaluation_end: string;
  total_records: number;
  returned_records: number;
  pagination: PaginationMeta;
  filters: Record<string, unknown>;
  data: HistoricalPredictionItem[];
}

export interface TierPeriodEvaluationSummary {
  tier: "tier1" | "tier2";
  period: "validation" | "test" | "august_holdout";
  model_identifier: string;
  evaluation_start: string;
  evaluation_end: string;
  rows_evaluated: number;
  total_prediction_records: number;
  evaluation_population_note: string | null;
  wape: number;
  mae: number;
  rmse: number;
  r2: number;
  baseline_b_wape: number | null;
  baseline_b_mae: number | null;
  baseline_b_rmse: number | null;
  baseline_b_r2: number | null;
}

export interface HistoricalForecastSummaryResponse {
  forecast_scope: "historical_evaluation_only";
  future_forecasting_supported: false;
  future_forecasting_note: string;
  supported_combinations: string[];
  summaries: TierPeriodEvaluationSummary[];
}
