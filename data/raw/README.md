# Raw data

Place the CTA - Ridership - Bus Routes - Daily Totals by Route export here as
`cta_bus_ridership.csv`. Preserve the original download and record its
download date and SHA-256 fingerprint. The loader accepts case-insensitive
column names:

- Date: `date` or `service_date`
- Route: `route`, `route_name`, or `bus_route`
- Reported day type: `daytype` or `day_type` (CTA values W/A/U)
- Daily ridership: `rides`, `ridership`, `total_rides`, `boardings`, or
  `daily_boardings`

Counts may contain thousands separators. Exact duplicate observations are
deduplicated; conflicting route/date rows and malformed values stop training
for investigation. Missing route/date rows remain missing and true zero rides
remain valid observations. The CSV is intentionally not committed.

Historical GTFS archive paths and expected SHA-256 values are tracked in
gtfs_archive_manifest.csv. Keep each downloaded ZIP under its own
data/raw/gtfs/<archive_id>/original.zip directory; the ZIPs are excluded from
Git. The Colab workflow also accepts the extracted contents in that archive
directory, but then cannot verify the original ZIP fingerprint.
