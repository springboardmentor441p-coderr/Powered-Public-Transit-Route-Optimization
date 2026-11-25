# AI_RouteRanker – Data Download & Integrity Validation Audit

**Audit Generated:** `2026-11-20T16:43:24.109835`  
**Target System:** `AI_RouteRanker (Milestone 2.1)`  

---

## 1. Dataset A: CTA Daily Bus Ridership

- **Source Endpoint:** `https://data.cityofchicago.org/api/v3/views/jyb9-n7fm/export.csv?accessType=DOWNLOAD`
- **File Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker\data\raw\ridership\cta_ridership.csv`
- **File Status:** `VALID`
- **File Size:** `33,838,656 bytes` (32.27 MB)
- **Calculated SHA-256:** `92e8ac49be18bd689dcb4d42694c4be22248368a2bc23688a880d5d239f056d0`
- **Reference SHA-256:** `6a999ea344084036310a779886bc6a72de6bad24cbb696e90822c83a337e608a`
- **SHA-256 Reference Match:** `DIFFERENT (Live updated export)`
- **Required Columns Validated:** `PASS` (`route`, `date`, `daytype`, `rides`)
- **Total Validated Records:** `1,124,170` (Reference: `1,120,604`)
- **Observed Date Range:** `2001-01-01` to `2026-08-31`
- **Unique Historical Routes:** `188`
- **Notes:** Live export SHA-256 differs from historical reference (valid updated dataset); Records count (1,124,170) meets or exceeds reference (1,120,604)

## 2. Dataset B: Historical GTFS Feed Archives (Mobility Database mdb-389)

| Archive ID | Snapshot Date | Size (MB) | SHA-256 Match | CRC Check | 8 Required Files | Shapes.txt | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `mdb-389-202511230128` | November 23, 2025 | 65.85 | PASS | PASS | PASS | YES | `VALID` |
| `mdb-389-202512190112` | December 19, 2025 | 95.49 | PASS | PASS | PASS | YES | `VALID` |
| `mdb-389-202601080131` | January 8, 2026 | 48.10 | PASS | PASS | PASS | YES | `VALID` |
| `mdb-389-202602100132` | February 10, 2026 | 47.59 | PASS | PASS | PASS | YES | `VALID` |
| `mdb-389-202603260020` | March 26, 2026 | 94.79 | PASS | PASS | PASS | YES | `VALID` |
| `mdb-389-202604240144` | April 24, 2026 | 48.60 | PASS | PASS | PASS | YES | `VALID` |
| `mdb-389-202605300003` | May 30, 2026 | 93.75 | PASS | PASS | PASS | YES | `VALID` |
| `mdb-389-202607110020` | July 11, 2026 | 64.75 | PASS | PASS | PASS | YES | `VALID` |


### Required GTFS Files Specification

All extracted archives are verified for the presence of the 8 core GTFS transit specification tables:
- `[x]` `agency.txt`
- `[x]` `routes.txt`
- `[x]` `trips.txt`
- `[x]` `stops.txt`
- `[x]` `stop_times.txt`
- `[x]` `calendar.txt`
- `[x]` `calendar_dates.txt`
- `[x]` `frequencies.txt`
- `[x]` `shapes.txt` (Tracked and preserved when available)

### Security & Traversal Safeguards

- Zip Slip traversal mitigation: Destination extraction paths strictly validated with `os.path.commonpath`.
- Original archive preservation: `original.zip` is immutable and never overwritten by extraction.
- Discrete directory separation: Each archive is kept strictly isolated in `data/raw/gtfs/<ARCHIVE_ID>/extracted/`.
