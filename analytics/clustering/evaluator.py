"""
AI_RouteRanker - Phase 6.1 Clustering Evaluator Module
Implements:
  1. Deterministic 5-seed sampled silhouette evaluation with noise exclusion (label -1),
     represented-population weighting, largest remainder sample allocation, and NOT COMPUTABLE handling.
  2. Hub sensitivity analysis across Configs A, B, and C over an identical eligible stop population.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr
from sklearn.metrics import silhouette_samples


class ClusteringEvaluator:
    """
    Evaluates clustering quality and sensitivity metrics in strict compliance with
    Phase 6.1 mathematical specifications.
    """

    APPROVED_SEEDS: List[int] = [42, 101, 2024, 777, 9999]
    MAX_SAMPLE_SIZE: int = 3000
    FEASIBILITY_RELAX_THRESHOLD: int = 1000
    MAX_REPRESENTABLE_CLUSTERS: int = 1500

    @classmethod
    def evaluate_sampled_silhouette(
        cls,
        X: np.ndarray,
        labels: np.ndarray,
        sample_size: int = MAX_SAMPLE_SIZE,
        seeds: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Computes the Approximate Represented-Population-Weighted Sampled Silhouette Score
        across 5 fixed deterministic pseudo-random seeds.
        
        Strict Rules:
          - Noise points (label == -1) are strictly excluded from sampling and scoring.
          - Clusters with N_c < 2 are excluded from valid clusters.
          - If valid clusters < 2, returns NOT COMPUTABLE (NaN) with diagnostic reason.
          - Never substitutes 0.0 or any synthetic score.
          - If valid clusters > 1,500, evaluates largest 1,500 clusters; weighting denominator
            uses strictly N_represented = sum_{c in evaluated} N_c.
          - Integer allocation via Hamilton-Hare Largest Remainder Method with deterministic tie-breaking.
        """
        seed_list = seeds if seeds is not None else cls.APPROVED_SEEDS
        max_m = int(sample_size)

        # 1. Filter out noise points (label == -1)
        valid_mask = labels != -1
        X_clean = X[valid_mask]
        labels_clean = labels[valid_mask]
        n_noise = int(np.sum(~valid_mask))

        if len(labels_clean) == 0:
            return {
                "status": "NOT COMPUTABLE",
                "reason": "REASON_ALL_POINTS_NOISE",
                "mean_score": np.nan,
                "score_std": np.nan,
                "score_range": (np.nan, np.nan),
                "n_noise_stops": n_noise,
                "n_valid_clusters": 0,
                "n_represented_stops": 0,
            }

        # 2. Identify valid non-noise clusters with N_c >= 2
        unique_labels, cluster_counts = np.unique(labels_clean, return_counts=True)
        valid_clusters_mask = cluster_counts >= 2
        valid_clusters = unique_labels[valid_clusters_mask]
        valid_counts = cluster_counts[valid_clusters_mask]
        k_valid = len(valid_clusters)

        if k_valid < 2:
            return {
                "status": "NOT COMPUTABLE",
                "reason": "REASON_FEWER_THAN_TWO_VALID_CLUSTERS",
                "mean_score": np.nan,
                "score_std": np.nan,
                "score_range": (np.nan, np.nan),
                "n_noise_stops": n_noise,
                "n_valid_clusters": k_valid,
                "n_represented_stops": int(np.sum(valid_counts)) if k_valid > 0 else 0,
            }

        # 3. Feasibility Waterfall
        if k_valid <= cls.FEASIBILITY_RELAX_THRESHOLD:
            # Case 1: Standard
            m_c_min = 3
            eval_clusters = valid_clusters
            eval_counts = valid_counts
        elif k_valid <= cls.MAX_REPRESENTABLE_CLUSTERS:
            # Case 2: Relaxed quota
            m_c_min = 2
            eval_clusters = valid_clusters
            eval_counts = valid_counts
        else:
            # Case 3: Cardinality cap - retain top 1,500 largest clusters
            m_c_min = 2
            sort_idx = np.argsort(-valid_counts)
            top_indices = sort_idx[: cls.MAX_REPRESENTABLE_CLUSTERS]
            eval_clusters = valid_clusters[top_indices]
            eval_counts = valid_counts[top_indices]

        k_eval = len(eval_clusters)
        k_excluded = k_valid - k_eval
        n_represented = int(np.sum(eval_counts))
        n_excluded_stops = int(np.sum(valid_counts) - n_represented)

        target_m = min(max_m, n_represented)

        # Map cluster labels to indices in X_clean
        cluster_indices_map = {}
        for c in eval_clusters:
            cluster_indices_map[c] = np.where(labels_clean == c)[0]

        # 4. Evaluate across 5 deterministic seeds
        seed_weighted_scores = []
        seed_unweighted_scores = []

        for seed in seed_list:
            rng = np.random.RandomState(seed)
            sampled_indices = []

            # Step A: Guaranteed minimum per evaluated cluster
            min_quotas = {}
            for c in eval_clusters:
                c_idx = cluster_indices_map[c]
                q_base = min(m_c_min, len(c_idx))
                min_quotas[c] = q_base
                chosen = rng.choice(c_idx, size=q_base, replace=False)
                sampled_indices.extend(chosen)

            # Step B: Proportional allocation of remainder via Largest Remainder Method
            m_allocated = len(sampled_indices)
            m_remain = target_m - m_allocated

            if m_remain > 0:
                remaining_capacities = np.array([len(cluster_indices_map[c]) - min_quotas[c] for c in eval_clusters], dtype=float)
                r_total = float(np.sum(remaining_capacities))

                if r_total > 0:
                    real_quotas = m_remain * (remaining_capacities / r_total)
                    int_quotas = np.floor(real_quotas).astype(int)
                    remainders = real_quotas - int_quotas
                    surplus = int(m_remain - np.sum(int_quotas))

                    # Deterministic tie-breaking: sort descending by remainder, then cluster size desc, then cluster ID asc
                    tie_breaker = []
                    for idx, c in enumerate(eval_clusters):
                        tie_breaker.append((-remainders[idx], -eval_counts[idx], c, idx))
                    tie_breaker.sort()

                    additional_slots = np.zeros(k_eval, dtype=int)
                    for i in range(surplus):
                        cluster_idx = tie_breaker[i][3]
                        additional_slots[cluster_idx] += 1

                    total_additional = int_quotas + additional_slots

                    # Sample additional points without replacement from remaining pool
                    for idx, c in enumerate(eval_clusters):
                        n_extra = total_additional[idx]
                        if n_extra > 0:
                            c_idx = cluster_indices_map[c]
                            # Exclude already sampled
                            already_chosen = set(sampled_indices)
                            avail = [x for x in c_idx if x not in already_chosen]
                            extra_chosen = rng.choice(avail, size=n_extra, replace=False)
                            sampled_indices.extend(extra_chosen)

            sampled_indices = np.array(sampled_indices)
            X_sub = X_clean[sampled_indices]
            labels_sub = labels_clean[sampled_indices]

            # Scikit-learn condition: 2 <= n_labels <= n_samples - 1
            n_sub_labels = len(np.unique(labels_sub))
            if n_sub_labels < 2 or n_sub_labels > len(X_sub) - 1:
                seed_weighted_scores.append(np.nan)
                seed_unweighted_scores.append(np.nan)
                continue

            sample_sil = silhouette_samples(X_sub, labels_sub, metric="euclidean")

            # Population-weighted calculation: sum_{c} (N_c / N_represented) * mean(sil_c)
            weighted_components = []
            for idx, c in enumerate(eval_clusters):
                c_mask = labels_sub == c
                if np.sum(c_mask) > 0:
                    mean_c = float(np.mean(sample_sil[c_mask]))
                    w_c = float(eval_counts[idx]) / float(n_represented)
                    weighted_components.append(w_c * mean_c)

            seed_score = float(np.sum(weighted_components))
            seed_weighted_scores.append(seed_score)
            seed_unweighted_scores.append(float(np.mean(sample_sil)))

        # Summary statistics across seeds
        valid_seed_scores = [s for s in seed_weighted_scores if not np.isnan(s)]

        if len(valid_seed_scores) == 0:
            status = "NOT COMPUTABLE"
            mean_score = np.nan
            score_std = np.nan
            score_range = (np.nan, np.nan)
        else:
            status = "VALID EVALUATION"
            mean_score = float(np.mean(valid_seed_scores))
            score_std = float(np.std(valid_seed_scores, ddof=1)) if len(valid_seed_scores) > 1 else 0.0
            score_range = (float(np.min(valid_seed_scores)), float(np.max(valid_seed_scores)))

        return {
            "status": status,
            "metric_name": "Approximate Represented-Population-Weighted Sampled Silhouette Score",
            "mean_score": mean_score,
            "score_std": score_std,
            "score_range": score_range,
            "unweighted_reference_mean": float(np.mean(seed_unweighted_scores)) if len(seed_unweighted_scores) > 0 else np.nan,
            "seed_scores": seed_weighted_scores,
            "n_noise_stops": n_noise,
            "n_valid_clusters": k_valid,
            "n_evaluated_clusters": k_eval,
            "n_excluded_clusters": k_excluded,
            "n_represented_stops": n_represented,
            "n_excluded_stops": n_excluded_stops,
            "sample_size_evaluated": target_m,
            "seeds_evaluated": seed_list,
        }

    @staticmethod
    def compute_hub_rankings(
        stop_features_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Computes composite HubScores across Config A, Config B, and Config C
        over the identical eligible stop population (stops with mapped visits > 0 and demand not null).
        
        Configurations:
          Config A (Balanced): 0.40 * v~ + 0.35 * R~ + 0.25 * D~
          Config B (Connectivity): 0.25 * v~ + 0.55 * R~ + 0.20 * D~
          Config C (Demand Intensity): 0.30 * v~ + 0.30 * R~ + 0.40 * I~
        """
        df = stop_features_df.copy()

        # Strict eligible cohort: mapped visits > 0 and demand is not null
        eligible_mask = (df["mapped_visits"] > 0) & (df["attributed_demand"].notna())
        df_eval = df[eligible_mask].copy()

        def _min_max(col):
            c_min = col.min()
            c_max = col.max()
            if c_max > c_min:
                return (col - c_min) / (c_max - c_min)
            return np.zeros_like(col)

        def _robust_min_max(col):
            q01 = col.quantile(0.01)
            q99 = col.quantile(0.99)
            clipped = np.clip(col, q01, q99)
            if q99 > q01:
                return (clipped - q01) / (q99 - q01)
            return np.zeros_like(col)

        v_norm = _min_max(df_eval["total_visits"])
        r_norm = _min_max(df_eval["routes_served"])
        d_norm = _min_max(df_eval["attributed_demand"])

        # Intensity feature: I_s = D_{s, mapped} / v_{s, mapped}
        intensity = df_eval["attributed_demand"] / df_eval["mapped_visits"]
        i_norm = _robust_min_max(intensity)

        df_eval["score_config_a"] = 0.40 * v_norm + 0.35 * r_norm + 0.25 * d_norm
        df_eval["score_config_b"] = 0.25 * v_norm + 0.55 * r_norm + 0.20 * d_norm
        df_eval["score_config_c"] = 0.30 * v_norm + 0.30 * r_norm + 0.40 * i_norm

        df_eval["rank_config_a"] = df_eval["score_config_a"].rank(ascending=False, method="min").astype(int)
        df_eval["rank_config_b"] = df_eval["score_config_b"].rank(ascending=False, method="min").astype(int)
        df_eval["rank_config_c"] = df_eval["score_config_c"].rank(ascending=False, method="min").astype(int)

        return df_eval

    @staticmethod
    def evaluate_hub_sensitivity(
        ranked_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Computes Spearman rank correlations across full population and Top-100 Jaccard overlaps.
        """
        rho_ab, _ = spearmanr(ranked_df["rank_config_a"], ranked_df["rank_config_b"])
        rho_ac, _ = spearmanr(ranked_df["rank_config_a"], ranked_df["rank_config_c"])
        rho_bc, _ = spearmanr(ranked_df["rank_config_b"], ranked_df["rank_config_c"])

        top100_a = set(ranked_df.nsmallest(100, "rank_config_a")["stop_id"])
        top100_b = set(ranked_df.nsmallest(100, "rank_config_b")["stop_id"])
        top100_c = set(ranked_df.nsmallest(100, "rank_config_c")["stop_id"])

        def _jaccard(s1, s2):
            return len(s1.intersection(s2)) / len(s1.union(s2)) if len(s1.union(s2)) > 0 else 0.0

        j_ab = _jaccard(top100_a, top100_b)
        j_ac = _jaccard(top100_a, top100_c)
        j_bc = _jaccard(top100_b, top100_c)

        r_vd, _ = pearsonr(ranked_df["total_visits"], ranked_df["attributed_demand"])
        rho_vd, _ = spearmanr(ranked_df["total_visits"], ranked_df["attributed_demand"])

        return {
            "eligible_population_size": len(ranked_df),
            "spearman_rank_corr_a_b": float(rho_ab),
            "spearman_rank_corr_a_c": float(rho_ac),
            "spearman_rank_corr_b_c": float(rho_bc),
            "top100_jaccard_a_b": float(j_ab),
            "top100_jaccard_a_c": float(j_ac),
            "top100_jaccard_b_c": float(j_bc),
            "top100_overlap_count_a_b": len(top100_a.intersection(top100_b)),
            "top100_overlap_count_a_c": len(top100_a.intersection(top100_c)),
            "top100_overlap_count_b_c": len(top100_b.intersection(top100_c)),
            "pearson_visits_demand": float(r_vd),
            "spearman_visits_demand": float(rho_vd),
        }
