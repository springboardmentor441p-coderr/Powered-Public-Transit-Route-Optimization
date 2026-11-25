"""
AI_RouteRanker - Phase 6.2 Route Connectivity Module
Implements shared-stop Jaccard overlap and network connectivity analysis
across route-direction patterns using active scheduled stop sequences.
"""

from typing import Dict, List, Optional, Tuple, Set, Any
import numpy as np
import pandas as pd


class RouteConnectivityAnalyzer:
    """
    Analyzes physical stop sharing and network connectivity between route-direction patterns.
    """

    @staticmethod
    def extract_route_direction_stop_sets(
        stop_times_df: pd.DataFrame,
    ) -> Dict[str, Set[str]]:
        """
        Extracts the set of unique physical boarding stop IDs served by each route-direction.

        Args:
            stop_times_df: DataFrame with ['route_id', 'direction_id', 'stop_id'].

        Returns:
            Dict mapping 'route_id__dir_{direction_id}' -> Set of stop_ids.
        """
        df = stop_times_df.dropna(subset=["route_id", "direction_id", "stop_id"]).copy()
        df["direction_id"] = df["direction_id"].astype(int)

        stop_sets = {}
        for (route_id, direction_id), group in df.groupby(["route_id", "direction_id"]):
            key = f"{route_id}__dir_{direction_id}"
            stops = set(group["stop_id"].astype(str).unique())
            stop_sets[key] = stops

        return stop_sets

    @staticmethod
    def compute_jaccard_similarity(
        stops_a: Set[str],
        stops_b: Set[str],
    ) -> float:
        """
        Computes Jaccard stop similarity:
          J(A, B) = |A ∩ B| / |A ∪ B|
        Handles empty stop sets explicitly (returns 0.0).
        """
        if not stops_a or not stops_b:
            return 0.0

        intersection = stops_a.intersection(stops_b)
        union = stops_a.union(stops_b)

        if len(union) == 0:
            return 0.0

        return float(len(intersection) / len(union))

    @classmethod
    def compute_pairwise_connectivity_matrix(
        cls,
        route_stop_sets: Dict[str, Set[str]],
    ) -> Dict[str, Any]:
        """
        Computes pairwise Jaccard stop similarity matrix and shared stop count matrix.

        Args:
            route_stop_sets: Dict mapping pattern_id -> set of stop_ids.

        Returns:
            Dictionary with:
              - 'pattern_ids': List of pattern IDs.
              - 'jaccard_similarity_matrix': (P, P) float array in [0, 1].
              - 'shared_stops_matrix': (P, P) integer count array.
              - 'total_stops_per_pattern': Dict mapping pattern_id -> count.
        """
        pattern_ids = sorted(list(route_stop_sets.keys()))
        p = len(pattern_ids)

        jaccard_mat = np.zeros((p, p), dtype=float)
        shared_mat = np.zeros((p, p), dtype=int)
        total_stops = {}

        for i in range(p):
            p_i = pattern_ids[i]
            s_i = route_stop_sets[p_i]
            total_stops[p_i] = len(s_i)
            jaccard_mat[i, i] = 1.0 if len(s_i) > 0 else 0.0
            shared_mat[i, i] = len(s_i)

            for j in range(i + 1, p):
                p_j = pattern_ids[j]
                s_j = route_stop_sets[p_j]

                shared_cnt = len(s_i.intersection(s_j))
                jac = cls.compute_jaccard_similarity(s_i, s_j)

                shared_mat[i, j] = shared_cnt
                shared_mat[j, i] = shared_cnt

                jaccard_mat[i, j] = jac
                jaccard_mat[j, i] = jac

        return {
            "pattern_ids": pattern_ids,
            "jaccard_similarity_matrix": jaccard_mat,
            "shared_stops_matrix": shared_mat,
            "total_stops_per_pattern": total_stops,
        }

    @staticmethod
    def extract_route_direction_stop_sequences(
        stop_times_df: pd.DataFrame,
    ) -> Dict[str, List[str]]:
        """
        Extracts representative ordered list of physical boarding stop IDs served
        by each route-direction pattern.

        Args:
            stop_times_df: DataFrame with ['route_id', 'direction_id', 'stop_id'] and
                           optionally ['trip_id', 'stop_sequence'].

        Returns:
            Dict mapping 'route_id__dir_{direction_id}' -> List of ordered stop_ids.
        """
        df = stop_times_df.dropna(subset=["route_id", "direction_id", "stop_id"]).copy()
        df["direction_id"] = df["direction_id"].astype(int)
        df["stop_id"] = df["stop_id"].astype(str)

        sequences = {}
        for (route_id, direction_id), group in df.groupby(["route_id", "direction_id"]):
            key = f"{route_id}__dir_{direction_id}"
            if "trip_id" in group.columns:
                trip_counts = group.groupby("trip_id").size()
                if len(trip_counts) > 0:
                    best_trip = trip_counts.idxmax()
                    trip_df = group[group["trip_id"] == best_trip]
                else:
                    trip_df = group
            else:
                trip_df = group

            if "stop_sequence" in trip_df.columns:
                trip_df = trip_df.sort_values("stop_sequence")

            seq = trip_df["stop_id"].tolist()
            sequences[key] = seq

        return sequences

    @classmethod
    def find_shared_consecutive_stop_sequences(
        cls,
        route_stop_sequences: Dict[str, List[str]],
        min_sequence_length: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Finds contiguous shared consecutive stop sequences between pairs of route-directions
        using physical boarding stops, preserving actual ordered sequence, handling repeated
        stop IDs, and returning route-direction pair, shared sequence, and sequence length.

        Args:
            route_stop_sequences: Dict mapping pattern_id -> List of stop_ids.
            min_sequence_length: Minimum number of consecutive shared stops (default 2).

        Returns:
            List of Dicts:
              [{'pattern_a': str, 'pattern_b': str, 'shared_sequence': List[str], 'sequence_length': int}, ...]
        """
        pattern_ids = sorted(list(route_stop_sequences.keys()))
        p = len(pattern_ids)
        results = []

        for i in range(p):
            p_a = pattern_ids[i]
            seq_a = route_stop_sequences[p_a]
            n = len(seq_a)
            if n < min_sequence_length:
                continue

            for j in range(i + 1, p):
                p_b = pattern_ids[j]
                seq_b = route_stop_sequences[p_b]
                m = len(seq_b)
                if m < min_sequence_length:
                    continue

                # Dynamic programming table for contiguous common substrings
                # L[x][y] = length of common contiguous suffix ending at seq_a[x-1] and seq_b[y-1]
                L = [[0] * (m + 1) for _ in range(n + 1)]
                for x in range(1, n + 1):
                    for y in range(1, m + 1):
                        if seq_a[x - 1] == seq_b[y - 1]:
                            L[x][y] = L[x - 1][y - 1] + 1
                        else:
                            L[x][y] = 0

                # Extract maximal contiguous matches
                seen_matches = set()
                for x in range(1, n + 1):
                    for y in range(1, m + 1):
                        k = L[x][y]
                        if k >= min_sequence_length:
                            is_maximal = (x == n or y == m or seq_a[x] != seq_b[y])
                            if is_maximal:
                                subseq = seq_a[x - k: x]
                                subseq_tuple = tuple(subseq)
                                if subseq_tuple not in seen_matches:
                                    seen_matches.add(subseq_tuple)
                                    results.append({
                                        "pattern_a": p_a,
                                        "pattern_b": p_b,
                                        "shared_sequence": subseq,
                                        "sequence_length": k,
                                    })

        return results

