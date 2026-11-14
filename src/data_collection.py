"""
Module 1: Data Collection & Loading
Loads all GTFS files from the extracted dataset folder.
"""
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')


def load_gtfs_data(gtfs_dir: str) -> dict:
    """
    Load all essential GTFS files into a dictionary of DataFrames.

    Parameters
    ----------
    gtfs_dir : str
        Path to the directory containing GTFS .txt files.

    Returns
    -------
    dict : Dictionary mapping file names (without .txt) to DataFrames.
    """
    required_files = [
        'routes', 'trips', 'stop_times', 'stops', 'calendar'
    ]
    optional_files = [
        'frequencies', 'shapes', 'agency', 'calendar_dates',
        'fare_attributes', 'fare_rules', 'feed_info', 'transfers', 'timetables'
    ]

    data = {}

    # Load required files
    for fname in required_files:
        fpath = os.path.join(gtfs_dir, f'{fname}.txt')
        if os.path.exists(fpath):
            data[fname] = pd.read_csv(fpath, low_memory=False)
            print(f"  ✅ Loaded {fname}.txt: {data[fname].shape[0]:,} rows, {data[fname].shape[1]} columns")
        else:
            print(f"  ❌ MISSING required file: {fname}.txt")

    # Load optional files
    for fname in optional_files:
        fpath = os.path.join(gtfs_dir, f'{fname}.txt')
        if os.path.exists(fpath):
            data[fname] = pd.read_csv(fpath, low_memory=False)
            print(f"  ✅ Loaded {fname}.txt: {data[fname].shape[0]:,} rows, {data[fname].shape[1]} columns")

    return data


def inspect_data(data: dict):
    """Print basic statistics for each loaded DataFrame."""
    print("\n" + "=" * 70)
    print("DATASET INSPECTION REPORT")
    print("=" * 70)

    for name, df in data.items():
        print(f"\n📄 {name}.txt")
        print(f"   Shape: {df.shape}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Missing values:\n{df.isnull().sum().to_string()}")
        print(f"   Dtypes:\n{df.dtypes.to_string()}")
        print("-" * 50)


if __name__ == "__main__":
    GTFS_DIR = os.path.join(os.path.dirname(__file__), '..', 'gtfs')
    print("📦 Loading GTFS Data...")
    data = load_gtfs_data(GTFS_DIR)
    inspect_data(data)
