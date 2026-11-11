# Demonstration and deployment

## Primary planning application

Use [APPLICATION.md](APPLICATION.md) for the React/FastAPI/PostgreSQL launch and
container commands. The primary demo is: inspect a route map, compare common-date
service, select a named ranking, start replay, inspect a frozen forecast, advance
until its actual is released, and save a conditional frequency scenario.

## Earlier Streamlit launch

Restore the validated source and processed-data bundle before reproducing the study.
The public code repository intentionally excludes datasets, private documents and runtime
outputs. A checkout alone does not contain the installed analytical release.

```powershell
python -m pip install -r requirements-dashboard.txt
python -m streamlit run streamlit_app.py
```

## Eight-step demonstration

1. Open Data coverage: explain observation windows, five historical archives and unavailable
   occupancy/delay evidence.
2. Open Route explorer for M34+: inspect demand and scheduled service on the selected dates.
3. Open Route comparison: compare M34A+ on matching weekday dates and inspect exclusive stops.
4. Open Planning review: inspect a triggered signal; select M98 to demonstrate source withholding.
5. Open Demand forecasts: distinguish the reference from the challenger, explain historical
   evaluation and why challenger ranges are withheld. Old previews retain their issue dates.
6. Open Service scenarios: set M34+ weekday departures to +20%; observe the added hours exceeding
   a ten-hour allowance. Explain why this does not establish a crowding benefit.
7. Open Budget allocation: compare a 50-hour, 20%-cap allocation with the equal-spend uniform
   alternative. Explain the objective and its limits.
8. Open Planning proposals: save and reopen the evidence/assumptions, then download the package.
   Demonstrate GTFS import separately; do not replace the study with an unrelated upload.

Observed-load classification remains blocked until independently observed labels are available.
Its header-only template is not a dataset. No fictional labels or fixture metrics belong in the
demonstration.

## Verification

```powershell
python -m unittest discover -s tests -v
python scripts/smoke_dashboard.py
python scripts/smoke_completion.py
python scripts/audit_completion.py
```

The browser check needs a running server and Playwright Chromium. It exercises original pages,
downloads and integrity verification. The completion browser check covers the additional
workflows and real GTFS upload. Screenshots and runtime evidence remain local.

## Rebuild the report and presentation

First reproduce the analytical artifacts and run the completion audit, then:

```powershell
python -m pip install -r requirements-handoff.txt
python scripts/build_final_handoff.py
npm.cmd install --prefix .tools/presentations pptxgenjs
$env:NODE_PATH = Join-Path (Get-Location) '.tools/presentations/node_modules'
node scripts/build_presentation.cjs
```

PowerPoint can export the editable deck to PDF. The report builder uses the public Markdown
report, and the presentation reads audited results. Generated files are in handoff/final and
excluded from Git; no private source document is required to rebuild them.

## Container option

With Docker available and the data directories restored:

```powershell
docker compose up --build
```

The host port is bound to localhost. Original and analytical inputs are read-only. The preview
subdirectory, proposals/imports and reports use separate writable mounts. No source data,
private documents, credentials or notebooks are included in the build context.

Docker is unavailable on the current verification host, so the container configuration is
provided but not represented as a tested deployment. Verify it on the destination before handoff.

For shared hosting, add authentication, access controls, persistent backups, error monitoring,
resource limits for ZIP inspection/model jobs, dependency pinning and source-refresh review.
Do not expose the development server directly as an operational service. Predictions retain
their experimental status until the prospective acceptance policy is met.
