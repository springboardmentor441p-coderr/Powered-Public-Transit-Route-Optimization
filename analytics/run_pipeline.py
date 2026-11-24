"""
Orchestrates the entire RouteRanker offline ETL, feature engineering, and model training pipeline.
"""
import os
import sys

# Silence joblib/loky CPU core warning on modern Windows where wmic is deprecated
try:
    import joblib.externals.loky.backend.context as _loky_ctx
    _loky_ctx.physical_cores_cache = os.cpu_count() or 4
except Exception:
    pass

import importlib

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

def main():
    steps = [
        "analytics.00_generate_sample_data",
        "analytics.01_source_register",
        "analytics.02_clean_boardings",
        "analytics.03_gtfs_calendar_expansion",
        "analytics.04_snapshot_selection_and_join",
        "analytics.05_route_structure_and_overlap",
        "analytics.build_reference_datasets",
        "train_models",
    ]
    for mod_name in steps:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "run"):
            mod.run()
        elif hasattr(mod, "generate"):
            mod.generate()

if __name__ == "__main__":
    main()
