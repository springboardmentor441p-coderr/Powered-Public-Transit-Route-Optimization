import importlib.util
from pathlib import Path

_cur = Path(__file__).resolve().parent

def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _cur / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

source_register = _load("source_register", "01_source_register.py")
clean_boardings = _load("clean_boardings", "02_clean_boardings.py")
parse_gtfs_schedule = _load("parse_gtfs_schedule", "03_parse_gtfs_schedule.py")
route_structure_and_overlap = _load("route_structure_and_overlap", "04_route_structure_and_overlap.py")
feature_engineering = _load("feature_engineering", "05_feature_engineering.py")
train_evaluate_models = _load("train_evaluate_models", "06_train_evaluate_models.py")
route_productivity_ranking = _load("route_productivity_ranking", "07_route_productivity_ranking.py")

__all__ = [
    "source_register",
    "clean_boardings",
    "parse_gtfs_schedule",
    "route_structure_and_overlap",
    "feature_engineering",
    "train_evaluate_models",
    "route_productivity_ranking"
]
