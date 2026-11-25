#!/usr/bin/env python3
"""
AI_RouteRanker - Data Source Downloader
Streaming HTTP downloader for CTA bus ridership and Mobility Database GTFS feeds.
Complies with Milestone 2.1 specifications.
"""

import argparse
import gzip
import hashlib
import http.client
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

# Configuration Constants
RIDERSHIP_METADATA = {
    "name": "CTA Daily Bus Ridership",
    "filename": "cta_ridership.csv",
    "relative_path": os.path.join("data", "raw", "ridership", "cta_ridership.csv"),
    "url": "https://data.cityofchicago.org/api/v3/views/jyb9-n7fm/export.csv?accessType=DOWNLOAD",
    "expected_sha256": "6a999ea344084036310a779886bc6a72de6bad24cbb696e90822c83a337e608a",
    "expected_records": 1120604,
    "expected_date_range": ("2001-01-01", "2026-07-31"),
}

GTFS_ARCHIVES: List[Dict[str, str]] = [
    {
        "id": "mdb-389-202511230128",
        "date_label": "November 23, 2025",
        "sha256": "4a34e0c78a12d797ae5b3f5075005e91db8b6e6715eda9b146fa3946b1136964",
    },
    {
        "id": "mdb-389-202512190112",
        "date_label": "December 19, 2025",
        "sha256": "1d49526cbce5bf3188cad4524cafdae581e3ad6a4920d256d4577a51e3c3bb4d",
    },
    {
        "id": "mdb-389-202601080131",
        "date_label": "January 8, 2026",
        "sha256": "41cc4ddabefed327cd0093ba9f707f8ce9f2fd39405d95abdffb8a4702099156",
    },
    {
        "id": "mdb-389-202602100132",
        "date_label": "February 10, 2026",
        "sha256": "a2115731f779a6c12d27ed72d45027d5a5c213ad99945da10452994a451d281c",
    },
    {
        "id": "mdb-389-202603260020",
        "date_label": "March 26, 2026",
        "sha256": "57715a5a369542ec95dcfe6b1f519e9c37dbf8032801912eb88379cccbcf9aba",
    },
    {
        "id": "mdb-389-202604240144",
        "date_label": "April 24, 2026",
        "sha256": "b3e31c8fb050b9a3d32d7851e2d8b5c4a0fb39776ba1574f85fecd4f65cd8502",
    },
    {
        "id": "mdb-389-202605300003",
        "date_label": "May 30, 2026",
        "sha256": "3253ed0b0e19ced092c97d800acb07a7ae9df2bcfb593039e170c684639773d5",
    },
    {
        "id": "mdb-389-202607110020",
        "date_label": "July 11, 2026",
        "sha256": "cf14e64fa93bb3f5bed661c70d5834beb0be98a677f0b3e3487343bf42a76aa0",
    },
]

CHUNK_SIZE = 1024 * 32  # 32 KB streaming chunks
MIN_FREE_DISK_BYTES = 5 * 1024 * 1024 * 1024  # Require at least 5 GB free space


def get_gtfs_url(archive_id: str) -> str:
    """Generate exact Mobility Database archive URL."""
    return f"https://files.mobilitydatabase.org/mdb-389/{archive_id}/{archive_id}.zip"


def check_disk_space(target_path: str, required_bytes: int = MIN_FREE_DISK_BYTES) -> Tuple[bool, int]:
    """Check if the filesystem containing target_path has sufficient free space."""
    target_dir = os.path.dirname(os.path.abspath(target_path))
    os.makedirs(target_dir, exist_ok=True)
    usage = shutil.disk_usage(target_dir)
    return usage.free >= required_bytes, usage.free


def calculate_sha256(filepath: str) -> str:
    """Calculate SHA-256 hash using streaming blocks to minimize memory usage."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def probe_remote_resource(url: str, timeout: int = 15) -> Tuple[int, int, str]:
    """Perform a HEAD request to verify resource status and content length."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "AI_RouteRanker-Downloader/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            length = int(res.headers.get("Content-Length", 0))
            return res.status, length, res.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, 0, ""
    except Exception as e:
        return -1, 0, str(e)


def download_stream(
    url: str,
    target_path: str,
    expected_sha256: Optional[str] = None,
    max_retries: int = 5,
    timeout: int = 90,
    force: bool = False,
) -> bool:
    """
    Download file with streaming HTTP requests, progress reporting,
    retry mechanism, and temporary .part file handling.
    """
    if os.path.exists(target_path) and not force:
        file_size = os.path.getsize(target_path)
        if file_size > 0:
            if expected_sha256:
                current_sha = calculate_sha256(target_path)
                if current_sha.lower() == expected_sha256.lower():
                    print(f"  [EXISTS & VERIFIED] {target_path} ({file_size / (1024*1024):.2f} MB)")
                    return True
                else:
                    print(f"  [EXISTS BUT DIFFERENT] {target_path} (Hash: {current_sha[:12]}... Expected: {expected_sha256[:12]}...)")
            else:
                print(f"  [EXISTS] {target_path} ({file_size / (1024*1024):.2f} MB)")
                return True

    sufficient_space, free_bytes = check_disk_space(target_path)
    if not sufficient_space:
        print(f"  [ERROR] Insufficient disk space ({free_bytes / (1024*1024*1024):.2f} GB free, {MIN_FREE_DISK_BYTES / (1024*1024*1024):.2f} GB required)")
        return False

    temp_path = f"{target_path}.part"
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  Attempt {attempt}/{max_retries}: Connecting to {url}...")
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AI_RouteRanker-Downloader/1.0",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "*/*",
                },
            )

            start_time = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                encoding = response.headers.get("Content-Encoding", "").lower()
                stream = gzip.GzipFile(fileobj=response) if "gzip" in encoding else response
                downloaded = 0

                with open(temp_path, "wb") as f_out:
                    while True:
                        try:
                            chunk = stream.read(CHUNK_SIZE)
                        except (http.client.IncompleteRead, gzip.BadGzipFile) as ir:
                            partial_bytes = getattr(ir, "partial", b"")
                            if partial_bytes:
                                f_out.write(partial_bytes)
                                downloaded += len(partial_bytes)
                            raise ir
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)

                        # Progress reporting
                        elapsed = time.time() - start_time
                        rate = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                        if total_size > 0 and "gzip" not in encoding:
                            percent = (downloaded / total_size) * 100
                            print(
                                f"\r    Downloading: {downloaded / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB ({percent:.1f}%) at {rate:.2f} MB/s",
                                end="",
                                flush=True,
                            )
                        else:
                            print(
                                f"\r    Downloading: {downloaded / (1024*1024):.1f} MB (streamed) at {rate:.2f} MB/s",
                                end="",
                                flush=True,
                            )

                print()

            # Safely replace temporary file
            if os.path.exists(target_path):
                os.remove(target_path)
            shutil.move(temp_path, target_path)

            file_size = os.path.getsize(target_path)
            actual_sha = calculate_sha256(target_path)
            print(f"  [DOWNLOAD COMPLETE] Saved {target_path} ({file_size / (1024*1024):.2f} MB)")
            print(f"  SHA-256: {actual_sha}")
            return True

        except (urllib.error.URLError, TimeoutError, IOError, http.client.HTTPException, Exception) as e:
            print(f"\n  [ERROR on attempt {attempt}]: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            if attempt < max_retries:
                sleep_sec = attempt * 3
                print(f"  Retrying in {sleep_sec}s...")
                time.sleep(sleep_sec)
            else:
                print("  [FAILED] All download attempts exhausted.")
                return False

    return False


def run_probe_plan(project_root: str):
    """Inspect and display remote resource availability, URL resolution, and size estimates."""
    print("=" * 80)
    print("AI_RouteRanker - Data Source Probe and Download Plan")
    print("=" * 80)

    # Disk Space Check
    has_space, free_bytes = check_disk_space(project_root)
    print(f"\n[Environment Status]")
    print(f"  Target Root: {project_root}")
    print(f"  Available Disk Space: {free_bytes / (1024*1024*1024):.2f} GB")
    print(f"  Disk Space Requirement: >= {MIN_FREE_DISK_BYTES / (1024*1024*1024):.2f} GB (Passed: {has_space})")

    # Probing Dataset A
    print(f"\n[Dataset A: CTA Daily Bus Ridership]")
    print(f"  URL: {RIDERSHIP_METADATA['url']}")
    status, length, _ = probe_remote_resource(RIDERSHIP_METADATA["url"])
    print(f"  HTTP Status: {status} ({'Available' if status == 200 else 'Check URL'})")
    print(f"  Target Path: {os.path.join(project_root, RIDERSHIP_METADATA['relative_path'])}")
    print(f"  Estimated Size: ~35 - 45 MB CSV")
    print(f"  Reference SHA-256: {RIDERSHIP_METADATA['expected_sha256']}")

    # Probing Dataset B
    print(f"\n[Dataset B: 8 Historical GTFS Archives (Mobility Database mdb-389)]")
    total_gtfs_bytes = 0
    for idx, item in enumerate(GTFS_ARCHIVES, 1):
        url = get_gtfs_url(item["id"])
        target_zip = os.path.join(project_root, "data", "raw", "gtfs", item["id"], "original.zip")
        status, length, _ = probe_remote_resource(url)
        total_gtfs_bytes += length
        print(f"  {idx}. {item['id']} ({item['date_label']})")
        print(f"     URL: {url}")
        print(f"     HTTP: {status} | Size: {length / (1024*1024):.2f} MB | Dest: {target_zip}")
        print(f"     Expected SHA-256: {item['sha256']}")

    total_est_mb = (total_gtfs_bytes / (1024 * 1024)) + 40
    print("\n" + "-" * 80)
    print(f"Estimated Total Download Volume: ~{total_est_mb:.1f} MB (~{total_est_mb / 1024:.2f} GB)")
    print(f"Estimated Total Extracted Volume: ~2.0 - 2.5 GB")
    print(f"Total Disk Footprint: ~3.0 GB (Well within available {free_bytes / (1024*1024*1024):.2f} GB)")
    print("=" * 80)


def download_all(project_root: str, dataset_choice: str = "all", force: bool = False):
    """Execute download process according to dataset choice."""
    os.chdir(project_root)

    if dataset_choice in ("all", "ridership"):
        print("\n=== Initiating Dataset A Download (CTA Ridership) ===")
        target_csv = os.path.join(project_root, RIDERSHIP_METADATA["relative_path"])
        download_stream(
            url=RIDERSHIP_METADATA["url"],
            target_path=target_csv,
            expected_sha256=RIDERSHIP_METADATA["expected_sha256"],
            force=force,
        )

    if dataset_choice in ("all", "gtfs"):
        print("\n=== Initiating Dataset B Download (8 GTFS Archives) ===")
        for item in GTFS_ARCHIVES:
            url = get_gtfs_url(item["id"])
            target_zip = os.path.join(project_root, "data", "raw", "gtfs", item["id"], "original.zip")
            print(f"\nDownloading GTFS Archive: {item['id']} ({item['date_label']})")
            download_stream(
                url=url,
                target_path=target_zip,
                expected_sha256=item["sha256"],
                force=force,
            )


def main():
    parser = argparse.ArgumentParser(description="Download real CTA and GTFS datasets for AI_RouteRanker.")
    parser.add_argument(
        "--dataset",
        choices=["all", "ridership", "gtfs"],
        default="all",
        help="Select which dataset to download (default: all)",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Only display probe report, URL resolution, and storage calculations without downloading",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files already exist locally",
    )
    parser.add_argument(
        "--project-root",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        help="Root path of AI_RouteRanker project",
    )

    args = parser.parse_args()

    if args.plan_only:
        run_probe_plan(args.project_root)
    else:
        download_all(args.project_root, dataset_choice=args.dataset, force=args.force)


if __name__ == "__main__":
    main()
