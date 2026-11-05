# Real GTFS feeds used for learning (unmodified downloads, retrieved 2026-10-23)

| City | Operator | File | Original URL | Licence / terms | Notes |
|---|---|---|---|---|---|
| Pune | PMPML | `Pune_PMPML_gtfs.zip` | https://raw.githubusercontent.com/croyla/pmpml-gtfs/main/pmpml_gtfs_compat.zip | see repository `croyla/pmpml-gtfs` | Auto-generated from PMPML data; "compat" variant merges both directions into one route. 315 routes, 10,128 trips. |
| Chennai | MTC (+ CMRL, Southern Railway in same file) | `Chennai_MTC_gtfs.zip` | https://raw.githubusercontent.com/ungalsoththu/ChennaiGTFS/main/data/chennai-unified-gtfs.zip | see repository `ungalsoththu/ChennaiGTFS` | Multi-modal; only bus routes (route_type 3, 4,611 entries) are used. |
| Bengaluru | BMTC | `Bengaluru_BMTC_gtfs.zip` | https://raw.githubusercontent.com/Vonter/bmtc-gtfs/main/gtfs/bmtc.zip | ODbL 1.0 (some content © BMTC) | **Unofficial**, scraped from the Namma BMTC app; only routes with live tracking are included, so it is a partial network. 4,434 routes, 57,836 trips. |

What these files are: real published **schedules** (routes, stops, timetables). They contain **no passenger counts** and no live vehicle data.
Checksums: `SHA256SUMS.txt`. Re-download with `python scripts/fetch_real_data.py`.
