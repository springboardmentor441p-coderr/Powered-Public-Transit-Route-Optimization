// Type definitions for RouteRanker API responses

export interface DashboardSummary {
  total_routes: number;
  total_stops: number;
  total_trips: number;
  total_service_ids: number;
  avg_stops_per_route: number;
  avg_trips_per_route: number;
  top_routes_by_trips: { route_id: string; route_short_name: string; trip_count: number }[];
  top_routes_by_stops: { route_id: string; route_short_name: string; stop_count: number }[];
  trip_distribution: { bucket: string; count: number }[];
  multi_route_stops: { stop_count: number; num_stops: number }[];
  service_distribution: { service_id: string; trip_count: number }[];
}

export interface Route {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  route_type: number;
  agency_id: string;
  total_trips: number;
  trip_count: number;
  service_span_hours: number;
  avg_trip_duration_min: number;
  stop_count: number;
  estimated_distance_km: number;
  high_frequency_flag: number;
}

export interface RouteDetail extends Route {
  service_ids: string[];
  directions: number[];
  avg_speed_kmh: number;
  avg_headway_min: number;
  first_departure_time: string;
  last_departure_time: string;
  schedule_derived_notice: string;
}

export interface Stop {
  stop_id: string;
  stop_name: string;
  stop_lat: number;
  stop_lon: number;
}

export interface RouteStop extends Stop {
  stop_sequence: number;
}

export interface Trip {
  trip_id: string;
  route_id: string;
  service_id: string;
  direction_id: number;
}

export interface ScheduleEntry {
  trip_id: string;
  direction_id: number;
  service_id: string;
  departure_time: string;
  stop_id: string;
  stop_name: string;
}

export interface CoverageSummary {
  total_stops: number;
  stops_single_route: number;
  stops_multi_route: number;
  avg_routes_per_stop: number;
  max_routes_per_stop: number;
  top_shared_stops: { stop_id: string; stop_name: string; route_count: number; stop_lat: number; stop_lon: number }[];
  total_transfer_hubs: number;
  max_routes_at_single_stop: number;
  density_distribution: { single_route: number; two_to_four_routes: number; five_to_nine_routes: number; ten_plus_routes: number };
}

export interface CoverageStop extends Stop {
  route_count: number;
  route_names: string[];
}

export interface OverlapPair {
  route_a_id: string;
  route_a_name: string;
  route_b_id: string;
  route_b_name: string;
  shared_stops: number;
  total_stops: number;
  jaccard_similarity: number;
}

export interface RouteOverlap {
  route_id: string;
  route_name: string;
  overlapping_routes: OverlapPair[];
}

export interface FrequencyStats {
  route_id: string;
  route_short_name: string;
  trip_count: number;
  avg_headway_minutes: number | null;
  min_headway_minutes: number | null;
  max_headway_minutes: number | null;
  first_departure: string | null;
  last_departure: string | null;
  service_span_hours: number | null;
  trips_per_hour: number | null;
  total_trips: number;
  headway_cv: number;
  high_frequency_flag: number;
}

export interface ServiceStats {
  service_id: string;
  days: string[];
  trip_count: number;
  route_count: number;
  start_date: string;
  end_date: string;
}

export interface ClusterResult {
  n_clusters: number;
  silhouette_score: number;
  clusters: ClusterInfo[];
  elbow_data: { k: number; inertia: number; silhouette: number }[];
  route_assignments: { route_id: string; route_short_name: string; cluster: number; features: Record<string, number> }[];
}

export interface ClusterInfo {
  cluster_id: number;
  label: string;
  size: number;
  avg_features: Record<string, number>;
}

export interface SimulationRequest {
  route_id: string;
  frequency_multiplier: number;
  stop_consolidation_pct: number;
  scenario_name?: string;
  target_headway_min?: number;
  span_extension_hours?: number;
  layover_ratio?: number;
}

export interface SimulationResult {
  route_id: string;
  route_short_name: string;
  scenario_name: string;
  baseline_trips: number;
  simulated_trips: number;
  baseline_headway_min: number;
  simulated_headway_min: number;
  baseline_trip_duration_min: number;
  simulated_trip_duration_min: number;
  baseline_vehicles_required: number;
  simulated_vehicles_required: number;
  baseline_vehicle_hours: number;
  simulated_vehicle_hours: number;
  baseline_vehicle_km: number;
  simulated_vehicle_km: number;
  baseline_speed_kmh: number;
  simulated_speed_kmh: number;
  comparisons: { metric_name: string; baseline_value: number; simulated_value: number; absolute_change: number; percentage_change: number; unit: string }[];
  schedule_derived_notes: string[];
  is_hypothetical: boolean;
  notes: string;
}

export interface DataQuality {
  quality_score: number;
  passed_validation: boolean;
  agency_count: number;
  route_count: number;
  stop_count: number;
  trip_count: number;
  stop_times_count: number;
  calendar_count: number;
  missing_files: string[];
  times_exceeding_24h_count: number;
  orphan_trips_count: number;
  invalid_coordinates_count: number;
  out_of_bounds_stops_count: number;
  sanitization_count: number;
  sanitization_events: { table: string; column: string; original_value: string; sanitized_value: string; issue_type: string }[];
  validation_issues: { table: string; severity: string; message: string; affected_rows: number }[];
  total_records: Record<string, number>;
  valid_records: Record<string, number>;
  invalid_records: Record<string, number>;
  duplicate_records: Record<string, number>;
  missing_values: Record<string, Record<string, number>>;
  processing_status: string;
  issues: string[];
  available_files: string[];
}

export interface DataStatus {
  status: string;
  message: string;
  last_processed_at: string | null;
  quality_score: number | null;
  raw_files_found: number;
  processed_tables: string[];
}

export interface Insight {
  category: string;
  title: string;
  description: string;
  value: string | number;
  details?: Record<string, unknown>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

