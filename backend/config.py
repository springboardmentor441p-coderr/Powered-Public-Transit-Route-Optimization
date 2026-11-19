import os

PROCESSED_DIR = os.getenv("ROUTERANKER_PROCESSED_DIR", "data/processed")
ARTIFACTS_DIR = os.getenv("ROUTERANKER_ARTIFACTS_DIR", "artifacts")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./routeranker.db")
DEFAULT_REPORTING_DELAY_DAYS = 1
