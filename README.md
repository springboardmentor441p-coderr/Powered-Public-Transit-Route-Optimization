# RouteRanker – Chennai public transit route analysis

This branch is for the Chennai single-city internship implementation. The first milestone builds a reproducible GTFS audit, scheduled route/hour supply analysis, and an explicitly synthetic route/hour demand scenario.

## Important data limitation

The supplied Chennai GTFS feed describes the network and scheduled service. It does not include actual passenger boardings, alightings, segment loads, or route-level ridership. The synthetic notebook allocates an MTC network-wide average across scheduled trips using stated assumptions. It is a **scenario only**, not observed ridership, and must not be used as ground-truth training labels or evidence that a route is overcrowded. See `notebooks/03_synthetic_ridership_scenario.ipynb` for its assumptions and caveats.

For route-level ground truth, request anonymized MTC/CUMTA ticketing or passenger-count records, or conduct a documented field survey. Keep that observed data separate from the generated scenario.

## Project structure

```text
notebooks/
  01_chennai_gtfs_data_audit.ipynb
  02_route_hour_supply.ipynb
  03_synthetic_ridership_scenario.ipynb
src/
  gtfs.py                  shared GTFS loading and calendar helpers
data/
  raw/Chennai_gtfs/        local input only; not committed
  processed/               local notebook outputs only; not committed
```

## Step-by-step: run the notebooks

1. Clone **your branch** and enter the project:

   ```bash
   git clone --branch mdzaid-khan --single-branch https://github.com/springboardmentor441p-coderr/Powered-Public-Transit-Route-Optimization.git
   cd Powered-Public-Transit-Route-Optimization
   ```

   If you already cloned it, run `git switch mdzaid-khan` and `git pull origin mdzaid-khan`.

2. Use Python 3.10 or newer. Create and activate a virtual environment (Windows PowerShell):

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Put the seven supplied `.txt` files in `data/raw/Chennai_gtfs/`, **or** set `GTFS_DIR` to the folder where you already keep them. For example, in PowerShell:

   ```powershell
   $env:GTFS_DIR = 'D:\DOCS\InfosysInternship\Chennai_gtfs'
   ```

   The original feed is intentionally excluded from Git because it is large and should remain a local input. The loader checks `GTFS_DIR`, then `data/raw/Chennai_gtfs/`, then the path above as a convenience for the current machine.

4. Start Jupyter from the repository root:

   ```powershell
   jupyter lab
   ```

5. Run these notebooks in order:
   - `01_chennai_gtfs_data_audit.ipynb` – inspect table sizes, missing keys, and joins.
   - `02_route_hour_supply.ipynb` – count scheduled trips by route and first departure hour for a selected calendar date.
   - `03_synthetic_ridership_scenario.ipynb` – allocate the selected aggregate daily total by schedule supply and peak-hour assumptions. Check the source/year and assumptions with your mentor before using the output.

6. Generated CSVs go to `data/processed/`. They are local outputs and are excluded from Git by `.gitignore`.

## Synthetic ridership assumptions

Notebook 03 uses the MTC performance indicator of 32.24 lakh passengers/day for FY 2024–25 as an illustrative whole-network calibration value. It assigns that total to route/hour rows in proportion to scheduled trip departures, with a 1.6 peak multiplier for 07:00–09:00 and 17:00–19:00. It does **not** establish how actual passengers are distributed across routes. Change the total, date, and multipliers only with clearly documented rationale; preserve the `data_status` and source columns in any export.

## Branch workflow

Work and push only to `mdzaid-khan`; do not push to `main` or another intern's branch. Commit code and documentation, not raw GTFS files or generated CSVs:

```bash
git status --short
git add README.md requirements.txt src notebooks
git commit -m "Add Chennai GTFS analysis notebooks"
git push origin mdzaid-khan
```

The existing repository contribution instructions also require each intern to use their own branch; this project setup follows that rule.
