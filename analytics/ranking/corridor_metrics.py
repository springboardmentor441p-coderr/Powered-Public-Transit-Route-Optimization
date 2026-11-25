"""
AI_RouteRanker - Phase 6.3 Corridor Metrics Module
Extracts route-level corridor co-routing, arterial infrastructure sharing,
and regional partition metrics using Phase 6.2 spatial corridor clustering outputs.
"""

from typing import Dict, List, Optional, Set, Any
import pandas as pd
import numpy as np

from analytics.ranking.config import RankerConfig


def compute_corridor_metrics(
    overlap_matrix: pd.DataFrame,
    shared_sequences_df: Optional[pd.DataFrame] = None,
    corridor_assignments_df: Optional[pd.DataFrame] = None,
    route_metadata_df: Optional[pd.DataFrame] = None,
    alpha: float = RankerConfig.CORRIDOR_WEIGHT_MAX_OVERLAP,
    beta: float = RankerConfig.CORRIDOR_WEIGHT_TOP5_MEAN,
    gamma: float = RankerConfig.CORRIDOR_WEIGHT_SHARED_RATIO,
) -> pd.DataFrame:
    """
    Computes route-level corridor co-routing, shared sequence, and regional partition metrics.

    Parameters
    ----------
    overlap_matrix : pd.DataFrame
        Square similarity matrix of pairwise 100m buffer overlaps between route-direction patterns
        (e.g., 261 x 261, with pattern_ids as index and columns).
    shared_sequences_df : Optional[pd.DataFrame]
        Phase 6.2 shared consecutive stop sequences (>=2 contiguous stops).
        Contains columns such as ['pattern_id_1', 'pattern_id_2'] or ['route_id_1', 'route_id_2']
        and shared stop counts / stop lists.
    corridor_assignments_df : Optional[pd.DataFrame]
        Phase 6.2 corridor cluster assignments (e.g., Frechet K=2 regional partition).
        Contains ['pattern_id'] and cluster column ('corridor_cluster_k2', 'corridor_cluster', or 'cluster').
    route_metadata_df : Optional[pd.DataFrame]
        Route-level operational metadata containing ['route_id', 'unique_stops_count'].
    alpha : float
        Weight for maximum corridor overlap (default 0.40).
    beta : float
        Weight for mean top-5 corridor overlap (default 0.30).
    gamma : float
        Weight for corridor duplication ratio (default 0.30).

    Returns
    -------
    pd.DataFrame
        DataFrame with unique 'route_id' and columns:
        ['route_id', 'max_corridor_overlap', 'mean_corridor_overlap',
         'shared_consecutive_stop_count', 'corridor_duplication_ratio',
         'regional_partition', 'corridor_duplication_index']
    """
    if overlap_matrix is None or overlap_matrix.empty:
        return pd.DataFrame(columns=[
            "route_id", "max_corridor_overlap", "mean_corridor_overlap",
            "shared_consecutive_stop_count", "corridor_duplication_ratio",
            "regional_partition", "corridor_duplication_index"
        ])

    # Extract all pattern IDs and their corresponding route IDs
    pattern_ids = [str(p) for p in overlap_matrix.index]
    pattern_to_route: Dict[str, str] = {}
    if (corridor_assignments_df is not None and not corridor_assignments_df.empty and
            "pattern_id" in corridor_assignments_df.columns and "route_id" in corridor_assignments_df.columns):
        pattern_to_route = dict(zip(
            corridor_assignments_df["pattern_id"].astype(str),
            corridor_assignments_df["route_id"].astype(str)
        ))

    for pid in pattern_ids:
        if pid not in pattern_to_route:
            if "__dir_" in pid:
                route_id = pid.split("__dir_")[0]
            elif "_" in pid:
                route_id = pid.rsplit("_", 1)[0]
            else:
                route_id = pid
            pattern_to_route[pid] = route_id

    # Group patterns by route
    all_routes = sorted(list(set(pattern_to_route.values())))

    # Mapping of unique stops per route
    unique_stops_map: Dict[str, int] = {}
    if route_metadata_df is not None and not route_metadata_df.empty:
        rm_df = route_metadata_df.copy()
        if "route_id" in rm_df.columns and "unique_stops_count" in rm_df.columns:
            for _, row in rm_df.iterrows():
                unique_stops_map[str(row["route_id"])] = int(row["unique_stops_count"])

    # Regional partition mapping from corridor_assignments_df
    # In Phase 6.2, cluster 0 represents North Chicago and cluster 1 represents South Chicago
    route_regional_map: Dict[str, str] = {}
    if corridor_assignments_df is not None and not corridor_assignments_df.empty:
        ca_df = corridor_assignments_df.copy()
        ca_df["pattern_id"] = ca_df["pattern_id"].astype(str)
        cluster_col = None
        for col_cand in ["cluster_frechet_k2", "corridor_cluster_k2", "corridor_cluster", "cluster", "regional_partition"]:
            if col_cand in ca_df.columns:
                cluster_col = col_cand
                break

        if cluster_col is not None:
            pattern_cluster = dict(zip(ca_df["pattern_id"], ca_df[cluster_col]))
            # Group clusters by route and take majority vote
            route_cluster_votes: Dict[str, List[Any]] = {}
            for pid, clust in pattern_cluster.items():
                rid = pattern_to_route.get(pid, pid.split("__dir_")[0] if "__dir_" in pid else (pid.rsplit("_", 1)[0] if "_" in pid else pid))
                route_cluster_votes.setdefault(rid, []).append(clust)

            for rid, votes in route_cluster_votes.items():
                majority_val = max(set(votes), key=votes.count)
                # Map 0 -> 'North Chicago', 1 -> 'South Chicago' if numeric
                if str(majority_val) in ("0", "North", "North Chicago"):
                    route_regional_map[rid] = "North Chicago"
                elif str(majority_val) in ("1", "South", "South Chicago"):
                    route_regional_map[rid] = "South Chicago"
                else:
                    route_regional_map[rid] = str(majority_val)

    # Shared consecutive stop count per route from shared_sequences_df
    route_shared_stops: Dict[str, Set[str]] = {}
    if shared_sequences_df is not None and not shared_sequences_df.empty:
        ss_df = shared_sequences_df.copy()
        # Find route/pattern columns
        r1_col = "pattern_a" if "pattern_a" in ss_df.columns else (
            "route_id_1" if "route_id_1" in ss_df.columns else (
                "pattern_id_1" if "pattern_id_1" in ss_df.columns else None
            )
        )
        r2_col = "pattern_b" if "pattern_b" in ss_df.columns else (
            "route_id_2" if "route_id_2" in ss_df.columns else (
                "pattern_id_2" if "pattern_id_2" in ss_df.columns else None
            )
        )

        stops_col = None
        for cand in ["shared_stops_json", "shared_stop_ids", "stop_ids", "sequence_stops", "shared_stops"]:
            if cand in ss_df.columns:
                stops_col = cand
                break

        length_col = "sequence_length" if "sequence_length" in ss_df.columns else ("stop_count" if "stop_count" in ss_df.columns else None)

        if r1_col and r2_col:
            for _, row in ss_df.iterrows():
                p1, p2 = str(row[r1_col]), str(row[r2_col])
                rid1 = pattern_to_route.get(p1, p1.split("__dir_")[0] if "__dir_" in p1 else (p1.rsplit("_", 1)[0] if "_" in p1 else p1))
                rid2 = pattern_to_route.get(p2, p2.split("__dir_")[0] if "__dir_" in p2 else (p2.rsplit("_", 1)[0] if "_" in p2 else p2))

                if stops_col and isinstance(row[stops_col], (list, set)):
                    st_set = set(str(s) for s in row[stops_col])
                    route_shared_stops.setdefault(rid1, set()).update(st_set)
                    route_shared_stops.setdefault(rid2, set()).update(st_set)
                elif stops_col and isinstance(row[stops_col], str):
                    try:
                        import json as _json
                        parsed = _json.loads(row[stops_col])
                        if isinstance(parsed, list):
                            st_set = set(str(s) for s in parsed)
                        else:
                            st_set = set(s.strip() for s in row[stops_col].replace(";", ",").split(",") if s.strip())
                    except Exception:
                        st_set = set(s.strip() for s in row[stops_col].replace(";", ",").split(",") if s.strip())
                    route_shared_stops.setdefault(rid1, set()).update(st_set)
                    route_shared_stops.setdefault(rid2, set()).update(st_set)
                    route_shared_stops.setdefault(rid2, set()).update(st_set)
                elif length_col and pd.notna(row[length_col]):
                    # Estimate stop count if exact stop IDs not listed
                    cnt = int(row[length_col])
                    # Add dummy unique stop IDs for counting
                    for k in range(cnt):
                        route_shared_stops.setdefault(rid1, set()).add(f"seq_{rid1}_{rid2}_{k}")
                        route_shared_stops.setdefault(rid2, set()).add(f"seq_{rid1}_{rid2}_{k}")

    # Convert overlap_matrix to numpy array for fast lookups
    mat_df = overlap_matrix.copy()
    mat_df.index = [str(idx) for idx in mat_df.index]
    mat_df.columns = [str(col) for col in mat_df.columns]

    records = []
    for route_id in all_routes:
        # Find all patterns belonging to this route
        route_pids = [pid for pid, r in pattern_to_route.items() if r == route_id and pid in mat_df.index]
        other_pids = [pid for pid, r in pattern_to_route.items() if r != route_id and pid in mat_df.columns]

        if not route_pids or not other_pids:
            records.append({
                "route_id": route_id,
                "max_corridor_overlap": 0.0,
                "mean_corridor_overlap": 0.0,
                "shared_consecutive_stop_count": 0,
                "corridor_duplication_ratio": 0.0,
                "regional_partition": route_regional_map.get(route_id, "North Chicago"),
                "corridor_duplication_index": 0.0,
            })
            continue

        # Extract sub-matrix between route patterns and other patterns
        sub_mat = mat_df.loc[route_pids, other_pids].values
        # Flatten all pairwise values with other routes
        other_overlaps = sub_mat.flatten()
        other_overlaps = other_overlaps[~np.isnan(other_overlaps)]

        if len(other_overlaps) == 0:
            max_overlap = 0.0
            mean_top5 = 0.0
        else:
            # We want the max overlap with ANY other route
            max_overlap = float(np.max(other_overlaps))
            # For top-5 mean: to avoid one multi-pattern route dominating all 5,
            # we group maximum overlap per other route
            route_max_overlaps = []
            for other_route in set(pattern_to_route[p] for p in other_pids):
                other_r_pids = [p for p in other_pids if pattern_to_route[p] == other_route]
                val = float(np.max(mat_df.loc[route_pids, other_r_pids].values))
                route_max_overlaps.append(val)

            route_max_overlaps.sort(reverse=True)
            top5_vals = route_max_overlaps[:5]
            mean_top5 = float(np.mean(top5_vals)) if top5_vals else 0.0

        # Shared consecutive stop count
        shared_count = len(route_shared_stops.get(route_id, set()))
        unique_stops = unique_stops_map.get(route_id, 0)
        dup_ratio = float(shared_count / unique_stops) if unique_stops > 0 else 0.0
        dup_ratio = float(np.clip(dup_ratio, 0.0, 1.0))

        # Composite corridor duplication index
        dup_index = float(np.clip(
            alpha * max_overlap + beta * mean_top5 + gamma * dup_ratio,
            0.0, 1.0
        ))

        records.append({
            "route_id": route_id,
            "max_corridor_overlap": float(np.clip(max_overlap, 0.0, 1.0)),
            "mean_corridor_overlap": float(np.clip(mean_top5, 0.0, 1.0)),
            "shared_consecutive_stop_count": int(shared_count),
            "corridor_duplication_ratio": dup_ratio,
            "regional_partition": route_regional_map.get(route_id, "North Chicago"),
            "corridor_duplication_index": dup_index,
        })

    return pd.DataFrame(records)
