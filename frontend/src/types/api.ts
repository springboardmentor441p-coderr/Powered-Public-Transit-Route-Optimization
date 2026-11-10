export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface RouteItem {
  route_id: string
  route_short_name: string | null
  route_long_name: string | null
  route_type?: string | null
  trip_count: number | null
  stop_count: number | null
  template_week_trip_count: number | null
  average_first_stop_headway_seconds: number | null
  first_service_time: string | null
  last_service_time: string | null
  kmeans_cluster_id: number | null
  dbscan_cluster_id: number | null
  fit_status: string | null
}

export interface StopItem {
  stop_id: string
  stop_name: string | null
  stop_lat_value: number | null
  stop_lon_value: number | null
  trip_count: number | null
  route_count: number | null
}

export interface RouteFeature {
  route_id: string
  route_short_name: string | null
  route_long_name: string | null
  route_type: string | null
  total_scheduled_trip_records: number | null
  unique_stop_count: number | null
  average_first_stop_headway_seconds: number | null
  headway_interval_count: number | null
  peak_scheduled_departures_per_template_week: number | null
  off_peak_scheduled_departures_per_template_week: number | null
  first_scheduled_departure_seconds: number | null
  last_scheduled_departure_seconds: number | null
  first_scheduled_departure_time: string | null
  last_scheduled_departure_time: string | null
  scheduled_service_span_seconds: number | null
  shared_stop_count: number | null
  shared_stop_ratio: number | null
  headway_missing: number | null
  service_span_missing: number | null
  shared_stop_ratio_missing: number | null
}

export interface StopRoute {
  route_id: string
  route_short_name: string | null
  route_long_name: string | null
}

export interface ScheduledHour {
  service_hour: number
  scheduled_trip_records: number
}

export interface HeadwaySummary {
  route_id: string | null
  groups_with_estimates: number
  groups_without_estimates: number
  median_of_group_medians_seconds: number | null
  mean_of_group_means_seconds: number | null
  note: string
}

export interface RouteStatistics {
  route_count: number
  routes_with_trips: number
  scheduled_trip_records: number
  median_stops_per_route: number | null
}

export interface StopStatistics {
  stop_count: number
  stops_with_scheduled_trips: number
  stops_served_by_routes: number
  median_routes_per_stop: number | null
}

export interface DatasetStatistics {
  gtfs_quality_status: string | null
  dataset_totals: Record<string, number | string | null>
  scheduled_service_level: Record<string, unknown>
  headway_diagnostics: Record<string, number | null>
  time_of_day: {
    busiest_service_hour?: number
    busiest_hour_trip_records?: number
    hourly_trip_record_counts?: Record<string, number>
  }
  data_quality: Record<string, number>
  limitations: {
    calendar_dates_available?: boolean
    frequencies_available?: boolean
    shapes_available?: boolean
    notes?: string[]
    [key: string]: unknown
  }
  interpretation: string
}

export interface ClusterProfile {
  algorithm: string
  cluster_id: number
  cluster_name: string
  route_count: number
  median_total_scheduled_trip_records: number | null
  median_unique_stop_count: number | null
  median_average_first_stop_headway_seconds: number | null
  headway_missing_rate: number | null
  median_peak_departure_share: number | null
  median_peak_scheduled_departures_per_template_week: number | null
  median_off_peak_scheduled_departures_per_template_week: number | null
  median_scheduled_service_span_hours: number | null
  median_shared_stop_ratio: number | null
  interpretation: string
}

export interface ClusterSummary {
  algorithm: 'KMeans' | 'DBSCAN'
  cluster_id: number
  route_count: number
  is_noise: boolean
  profile: ClusterProfile | null
}

export interface ModelMetric {
  algorithm: string
  n_clusters: number
  silhouette_score: number | null
  silhouette_sample_size: number | null
  davies_bouldin_index: number | null
  noise_count: number
  inlier_count: number
  k: number | null
  eps: number | null
  min_samples: number | null
}

export interface ModelMetadata {
  model: string
  feature_columns: string[]
  training_route_count: number | null
  selected_k: number | null
  eps: number | null
  min_samples: number | null
  new_route_behavior: string
}

export interface SimilarityItem {
  route_id_a: string
  route_id_b: string
  shared_stop_count: number
  route_a_stop_count: number
  route_b_stop_count: number
  jaccard_similarity: number
}

export interface CompareResponse {
  routes: RouteItem[]
  compared_route_ids: string[]
  note: string
}

export interface ApiHealth {
  status: string
}
