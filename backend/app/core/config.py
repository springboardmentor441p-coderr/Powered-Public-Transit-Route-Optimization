import json
import os
from pathlib import Path
from typing import Any, List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or defaults."""
    
    PROJECT_NAME: str = "AI_RouteRanker"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "AI-Powered Public Transit Route Optimization API"
    API_V1_STR: str = "/api"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Server host & port
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    
    # CORS Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    
    # Database Configuration (PostgreSQL - optional/inactive in Stage 1)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_routeranker_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: Union[str, None] = None

    # Analytical Artifact Paths (Read-Only)
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
    DATA_DIR: Path = PROJECT_ROOT / "data" / "processed"
    DUCKDB_PATH: Path = DATA_DIR / "ai_routeranker.duckdb"
    ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts"
    FEATURE_MASTER_PATH: Path = ARTIFACTS_DIR / "ranking_features" / "route_ranker_feature_master.parquet"
    RANKINGS_MASTER_PATH: Path = ARTIFACTS_DIR / "ranking_results" / "route_rankings_master.parquet"
    EXPLANATIONS_PATH: Path = ARTIFACTS_DIR / "ranking_results" / "route_ranking_explanations.json"
    SENSITIVITY_PATH: Path = ARTIFACTS_DIR / "ranking_results" / "ranking_sensitivity_analysis.parquet"

    # Phase 6.1 Spatial Clustering Artifacts (Read-Only)
    CLUSTERING_DIR: Path = ARTIFACTS_DIR / "clustering"
    TRANSIT_HUB_RANKINGS_PATH: Path = CLUSTERING_DIR / "transit_hub_rankings.parquet"
    DBSCAN_ASSIGNMENTS_PATH: Path = CLUSTERING_DIR / "spatial_dbscan_assignments.parquet"
    PHASE6_1_METADATA_PATH: Path = CLUSTERING_DIR / "phase6_1_stage2_metadata.json"
    TOP100_HUBS_CONFIG_A_PATH: Path = CLUSTERING_DIR / "top100_hubs_config_a.csv"

    # Phase 6.2 & 6.3 Corridor Topology Artifacts (Read-Only)
    ROUTE_CLUSTERING_DIR: Path = ARTIFACTS_DIR / "route_clustering"
    CORRIDOR_CLUSTERS_PATH: Path = ROUTE_CLUSTERING_DIR / "corridor_cluster_assignments.parquet"
    BUFFER_SIMILARITY_PATH: Path = ROUTE_CLUSTERING_DIR / "buffer_overlap_similarity_matrix.parquet"
    JACCARD_SIMILARITY_PATH: Path = ROUTE_CLUSTERING_DIR / "route_direction_jaccard_matrix.parquet"
    SHARED_SEQUENCES_PATH: Path = ROUTE_CLUSTERING_DIR / "shared_consecutive_stop_sequences.parquet"
    GEOMETRIES_META_PATH: Path = ROUTE_CLUSTERING_DIR / "route_direction_geometries_metadata.parquet"
    CONNECTIVITY_MATRIX_PATH: Path = ARTIFACTS_DIR / "ranking_features" / "route_direction_connectivity_matrix.parquet"

    # Phase 5 / Milestone 5.2 Random Forest Historical Evaluation Artifacts (Read-Only)
    RANDOM_FOREST_DIR: Path = ARTIFACTS_DIR / "random_forest"
    RF_TIER1_VAL_PRED_PATH: Path = RANDOM_FOREST_DIR / "tier1_val_predictions_tuned.parquet"
    RF_TIER1_TEST_PRED_PATH: Path = RANDOM_FOREST_DIR / "tier1_test_predictions_tuned.parquet"
    RF_TIER1_AUG_PRED_PATH: Path = RANDOM_FOREST_DIR / "tier1_august_predictions_tuned.parquet"
    RF_TIER2_VAL_PRED_PATH: Path = RANDOM_FOREST_DIR / "tier2_val_predictions_tuned.parquet"
    RF_TIER2_TEST_PRED_PATH: Path = RANDOM_FOREST_DIR / "tier2_test_predictions_tuned.parquet"
    RF_FINAL_METRICS_CSV_PATH: Path = PROJECT_ROOT / "reports" / "modeling" / "random_forest" / "final_model_evaluation_metrics.csv"
    RF_CHAMPION_CONFIG_PATH: Path = PROJECT_ROOT / "reports" / "modeling" / "random_forest" / "random_forest_champion_config.json"

    # Historical Ridership Bounds
    RIDERSHIP_DEFAULT_START_DATE: str = "2024-01-01"
    RIDERSHIP_DEFAULT_END_DATE: str = "2026-08-31"
    RIDERSHIP_MAX_DAILY_SPAN_DAYS: int = 366

    # Private Runtime Data Hydration (Hugging Face Dataset)
    HF_HYDRATION_ENABLED: bool = False
    HF_DATASET_REPO_ID: str = ""
    HF_DATASET_REVISION: str = "main"
    HF_TOKEN: Union[str, None] = None
    HF_CACHE_DIR: Union[Path, None] = None
    HYDRATION_MAX_RETRIES: int = 3
    HYDRATION_RETRY_DELAY_SECONDS: float = 2.0
    HYDRATION_STARTUP_MODE: str = "background"

    # Pagination & Validation Limits
    DEFAULT_PAGE_LIMIT: int = 25
    MAX_PAGE_LIMIT: int = 150
    ROUTE_ID_PATTERN: str = r"^[A-Za-z0-9_-]{1,16}$"
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        """Accept either JSON array strings or comma-separated origin strings."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _resolve_dependent_paths(self) -> "Settings":
        """Re-derive dependent artifact paths when base directory env vars are overridden."""
        if "DUCKDB_PATH" not in self.model_fields_set:
            self.DUCKDB_PATH = self.DATA_DIR / "ai_routeranker.duckdb"

        if "CLUSTERING_DIR" not in self.model_fields_set:
            self.CLUSTERING_DIR = self.ARTIFACTS_DIR / "clustering"
        if "ROUTE_CLUSTERING_DIR" not in self.model_fields_set:
            self.ROUTE_CLUSTERING_DIR = self.ARTIFACTS_DIR / "route_clustering"
        if "RANDOM_FOREST_DIR" not in self.model_fields_set:
            self.RANDOM_FOREST_DIR = self.ARTIFACTS_DIR / "random_forest"

        artifact_defaults = {
            "FEATURE_MASTER_PATH": self.ARTIFACTS_DIR / "ranking_features" / "route_ranker_feature_master.parquet",
            "RANKINGS_MASTER_PATH": self.ARTIFACTS_DIR / "ranking_results" / "route_rankings_master.parquet",
            "EXPLANATIONS_PATH": self.ARTIFACTS_DIR / "ranking_results" / "route_ranking_explanations.json",
            "SENSITIVITY_PATH": self.ARTIFACTS_DIR / "ranking_results" / "ranking_sensitivity_analysis.parquet",
            "TRANSIT_HUB_RANKINGS_PATH": self.CLUSTERING_DIR / "transit_hub_rankings.parquet",
            "DBSCAN_ASSIGNMENTS_PATH": self.CLUSTERING_DIR / "spatial_dbscan_assignments.parquet",
            "PHASE6_1_METADATA_PATH": self.CLUSTERING_DIR / "phase6_1_stage2_metadata.json",
            "TOP100_HUBS_CONFIG_A_PATH": self.CLUSTERING_DIR / "top100_hubs_config_a.csv",
            "CORRIDOR_CLUSTERS_PATH": self.ROUTE_CLUSTERING_DIR / "corridor_cluster_assignments.parquet",
            "BUFFER_SIMILARITY_PATH": self.ROUTE_CLUSTERING_DIR / "buffer_overlap_similarity_matrix.parquet",
            "JACCARD_SIMILARITY_PATH": self.ROUTE_CLUSTERING_DIR / "route_direction_jaccard_matrix.parquet",
            "SHARED_SEQUENCES_PATH": self.ROUTE_CLUSTERING_DIR / "shared_consecutive_stop_sequences.parquet",
            "GEOMETRIES_META_PATH": self.ROUTE_CLUSTERING_DIR / "route_direction_geometries_metadata.parquet",
            "CONNECTIVITY_MATRIX_PATH": self.ARTIFACTS_DIR / "ranking_features" / "route_direction_connectivity_matrix.parquet",
            "RF_TIER1_VAL_PRED_PATH": self.RANDOM_FOREST_DIR / "tier1_val_predictions_tuned.parquet",
            "RF_TIER1_TEST_PRED_PATH": self.RANDOM_FOREST_DIR / "tier1_test_predictions_tuned.parquet",
            "RF_TIER1_AUG_PRED_PATH": self.RANDOM_FOREST_DIR / "tier1_august_predictions_tuned.parquet",
            "RF_TIER2_VAL_PRED_PATH": self.RANDOM_FOREST_DIR / "tier2_val_predictions_tuned.parquet",
            "RF_TIER2_TEST_PRED_PATH": self.RANDOM_FOREST_DIR / "tier2_test_predictions_tuned.parquet",
        }
        for attr, default_path in artifact_defaults.items():
            if attr not in self.model_fields_set:
                setattr(self, attr, default_path)
        return self

    @property
    def runtime_required_paths(self) -> List[Path]:
        """Return all 22 runtime artifact and database paths required by API v1 endpoints."""
        return [
            self.DUCKDB_PATH,
            self.FEATURE_MASTER_PATH,
            self.RANKINGS_MASTER_PATH,
            self.EXPLANATIONS_PATH,
            self.SENSITIVITY_PATH,
            self.TRANSIT_HUB_RANKINGS_PATH,
            self.DBSCAN_ASSIGNMENTS_PATH,
            self.PHASE6_1_METADATA_PATH,
            self.TOP100_HUBS_CONFIG_A_PATH,
            self.CORRIDOR_CLUSTERS_PATH,
            self.BUFFER_SIMILARITY_PATH,
            self.JACCARD_SIMILARITY_PATH,
            self.SHARED_SEQUENCES_PATH,
            self.GEOMETRIES_META_PATH,
            self.CONNECTIVITY_MATRIX_PATH,
            self.RF_TIER1_VAL_PRED_PATH,
            self.RF_TIER1_TEST_PRED_PATH,
            self.RF_TIER1_AUG_PRED_PATH,
            self.RF_TIER2_VAL_PRED_PATH,
            self.RF_TIER2_TEST_PRED_PATH,
            self.RF_FINAL_METRICS_CSV_PATH,
            self.RF_CHAMPION_CONFIG_PATH,
        ]

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Compute the database connection URI."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
