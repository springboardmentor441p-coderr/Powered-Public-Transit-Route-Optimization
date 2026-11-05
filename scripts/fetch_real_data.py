"""Download the real GTFS feeds listed in real_data/SOURCES.md (works on Windows/Linux/macOS)."""
import urllib.request, hashlib
from pathlib import Path
FEEDS = {"Pune_PMPML_gtfs.zip": "https://raw.githubusercontent.com/croyla/pmpml-gtfs/main/pmpml_gtfs_compat.zip",
         "Chennai_MTC_gtfs.zip": "https://raw.githubusercontent.com/ungalsoththu/ChennaiGTFS/main/data/chennai-unified-gtfs.zip",
         "Bengaluru_BMTC_gtfs.zip": "https://raw.githubusercontent.com/Vonter/bmtc-gtfs/main/gtfs/bmtc.zip"}
out = Path(__file__).resolve().parent.parent / "real_data"; out.mkdir(exist_ok=True)
for name, url in FEEDS.items():
    p = out / name
    if p.exists(): print("exists:", name); continue
    print("downloading", name, "..."); urllib.request.urlretrieve(url, p)
    print("  sha256", hashlib.sha256(p.read_bytes()).hexdigest())
