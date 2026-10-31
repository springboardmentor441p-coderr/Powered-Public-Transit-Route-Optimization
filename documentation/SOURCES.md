# Public sources and reproduction

The analysis uses two source families: MTA boarding estimates and MTA bus GTFS schedules.
Different CSV windows, denominator checks and dated ZIP archives are versions/extracts, not
unrelated passenger datasets.

## Ridership

- [Official landing page](https://data.ny.gov/Transportation/MTA-Bus-Hourly-Ridership-Beginning-2025/gxb3-akrn)
- [Socrata CSV endpoint](https://data.ny.gov/resource/gxb3-akrn.csv)

Collection queries sum fare categories into route/hour and route/date boarding estimates, including
transfers separately as an existing subset. Seven quarterly daily files cover January 2025–September
2026; fourteen weekly hourly files cover July–September 2026. Exact query URLs are recorded in
receipts and the generated source register. Separate same-publisher denominator queries verify totals.

The collection also preserves publisher overview/dictionary PDFs and source metadata. These are
local evidence, not repository uploads. Read them for imputation, fare coverage and update limitations.

## Schedules

- [MTA developer source](https://www.mta.info/developers)
- [Manhattan archive catalogue](https://mobilitydatabase.org/feeds/gtfs/mdb-513)

Six current ZIP files are collected from the MTA links: Bronx, Brooklyn, Manhattan, Queens,
Staten Island and MTA Bus Company. Historical matching uses five separate Manhattan captures:

| Capture ID | Download |
|---|---|
| 202512300036 | [Original ZIP](https://files.mobilitydatabase.org/mdb-513/mdb-513-202512300036/mdb-513-202512300036.zip) |
| 202603270138 | [Original ZIP](https://files.mobilitydatabase.org/mdb-513/mdb-513-202603270138/mdb-513-202603270138.zip) |
| 202604090120 | [Original ZIP](https://files.mobilitydatabase.org/mdb-513/mdb-513-202604090120/mdb-513-202604090120.zip) |
| 202606240130 | [Original ZIP](https://files.mobilitydatabase.org/mdb-513/mdb-513-202606240130/mdb-513-202606240130.zip) |
| 202609030140 | [Original ZIP](https://files.mobilitydatabase.org/mdb-513/mdb-513-202609030140/mdb-513-202609030140.zip) |

MTA notes that bus feeds generally follow quarterly changes and generally exclude temporary
detours. Archive capture dates are distinct from feed operating dates. Current feeds are not used
as historical substitutes. Original downloaded hashes and sizes are recorded beside every source.

## Reproducibility boundaries

Run the collection scripts only when starting a new local collection. Existing receipt checks
protect the frozen data; publisher updates can legitimately change fresh-download results.
Restore the exact shared originals to reproduce identical hashes. Rebuild inspection and historical
audits before notebooks if starting without generated reports.

Installing Python dependencies and downloading public sources require network access; analysis
of a complete local collection runs offline. Downloaded data, generated artifacts, credentials
and environment files are excluded from version control.
