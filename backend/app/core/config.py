import os
from pathlib import Path
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
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

    # Pagination & Validation Limits
    DEFAULT_PAGE_LIMIT: int = 25
    MAX_PAGE_LIMIT: int = 150
    ROUTE_ID_PATTERN: str = r"^[A-Za-z0-9_-]{1,16}$"
    
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
