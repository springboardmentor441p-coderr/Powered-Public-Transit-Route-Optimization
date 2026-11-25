"""Read-only JSON repository for route ranking explanations."""

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import ArtifactUnavailableError

logger = logging.getLogger("ai_routeranker.repositories.json")


class JSONRepository:
    """
    Read-only repository for precomputed route ranking explanations JSON.

    Builds an O(1) lookup index keyed by (track, route_id) and a lightweight
    weight-metadata index for ranking list responses, with thread-safe lazy loading.
    """

    TRACK_KEYS = {
        "track_bus_priority": "BUS_PRIORITY",
        "track_rail_priority": "RAIL_PRIORITY",
        "track_unified_supply": "UNIFIED_SUPPLY",
    }

    def __init__(self, explanations_path: Optional[Path] = None) -> None:
        self._explanations_path = Path(explanations_path or settings.EXPLANATIONS_PATH)
        self._lock = threading.Lock()
        self._index: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None
        self._weight_index: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None

    def clear_cache(self) -> None:
        """Clear in-memory cached explanations indexes."""
        with self._lock:
            self._index = None
            self._weight_index = None

    def _load_index(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Load and validate explanations JSON into O(1) lookup indexes (thread-safe)."""
        if self._index is not None:
            return self._index

        with self._lock:
            if self._index is not None:
                return self._index

            if not self._explanations_path.exists() or not self._explanations_path.is_file():
                logger.error("Explanations artifact is missing.")
                raise ArtifactUnavailableError(
                    code="ARTIFACT_MISSING",
                    message="Required analytical artifact 'route_ranking_explanations' is unavailable.",
                )

            try:
                with self._explanations_path.open("r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as exc:
                logger.error("Failed to read explanations JSON: %s", type(exc).__name__)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_CORRUPT",
                    message="Analytical artifact 'route_ranking_explanations' could not be parsed.",
                ) from exc

            if not isinstance(raw_data, dict):
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message="Analytical artifact 'route_ranking_explanations' has invalid structure.",
                )

            index: Dict[Tuple[str, str], Dict[str, Any]] = {}
            weight_index: Dict[Tuple[str, str], Dict[str, Any]] = {}

            for json_key, default_track in self.TRACK_KEYS.items():
                entries = raw_data.get(json_key)
                if entries is None:
                    continue
                if not isinstance(entries, list):
                    raise ArtifactUnavailableError(
                        code="ARTIFACT_SCHEMA_INVALID",
                        message="Analytical artifact 'route_ranking_explanations' has invalid track list.",
                    )
                for item in entries:
                    if not isinstance(item, dict) or "route_id" not in item:
                        raise ArtifactUnavailableError(
                            code="ARTIFACT_SCHEMA_INVALID",
                            message="Analytical artifact 'route_ranking_explanations' contains malformed items.",
                        )
                    route_id = str(item["route_id"]).strip()
                    track = str(item.get("track") or default_track).strip().upper()
                    key = (track, route_id)
                    index[key] = item

                    original_weights = {
                        str(k): float(v) for k, v in item.get("original_weights", {}).items()
                    }
                    effective_weights = {
                        str(k): float(v) for k, v in item.get("effective_weights", {}).items()
                    }
                    missing_criteria: List[str] = [
                        str(x) for x in item.get("missing_criteria", [])
                    ]
                    valid_coverage = sum(
                        original_weights.get(k, 0.0)
                        for k in original_weights
                        if k not in missing_criteria
                    )
                    weight_index[key] = {
                        "original_weights": original_weights,
                        "effective_weights": effective_weights,
                        "missing_criteria": missing_criteria,
                        "valid_weight_coverage": round(float(valid_coverage), 6),
                    }

            if not index:
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message="Analytical artifact 'route_ranking_explanations' contains no valid explanations.",
                )

            self._weight_index = weight_index
            self._index = index
            return self._index

    def get_explanation(self, route_id: str, track: str) -> Optional[Dict[str, Any]]:
        """Return a deep copy of the explanation payload for (track, route_id) or None."""
        index = self._load_index()
        item = index.get((track.upper(), str(route_id).strip()))
        return copy.deepcopy(item) if item is not None else None

    def get_weight_metadata(self, route_id: str, track: str) -> Optional[Dict[str, Any]]:
        """
        Return an isolated shallow copy of weight metadata for (track, route_id).

        Avoids deep-copying full explanation narratives and driver lists for ranking rows.
        """
        self._load_index()
        assert self._weight_index is not None
        meta = self._weight_index.get((track.upper(), str(route_id).strip()))
        if meta is None:
            return None
        return {
            "original_weights": dict(meta["original_weights"]),
            "effective_weights": dict(meta["effective_weights"]),
            "missing_criteria": list(meta["missing_criteria"]),
            "valid_weight_coverage": meta["valid_weight_coverage"],
        }

    def get_track_count(self, track: str) -> int:
        """Return the number of route explanations in a given track."""
        index = self._load_index()
        target_track = track.upper()
        return sum(1 for (t, _) in index if t == target_track)
