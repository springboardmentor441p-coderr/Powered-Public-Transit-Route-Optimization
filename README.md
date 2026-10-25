# RouteRanker – Chennai public transit route analysis

This branch contains the Chennai single-city analysis workflow: GTFS audit, scheduled route/hour supply, a clearly synthetic demand scenario, route feature preparation, exploratory service clustering, and overlap review. The supervised model and full-stack application should follow after the prediction target and evaluation approach are established.

## Important data limitation

The supplied Chennai GTFS feed describes the network and scheduled service. It does not include actual passenger boardings, alightings, segment loads, or route-level ridership. The synthetic notebook allocates an MTC network-wide average across scheduled trips using stated assumptions. It is a **scenario only**, not observed ridership, and must not be used as ground-truth training labels or evidence that a route is overcrowded. See the synthetic-scenario section in `notebooks/02_synthetic_scenario_and_overlap_review.ipynb` for its assumptions and caveats.

For route-level ground truth, request anonymized MTC/CUMTA ticketing or passenger-count records, or conduct a documented field survey. Keep that observed data separate from the generated scenario.

## Project structure

```text
app.py                    earlier Streamlit scaffold; full app work is deferred
notebooks/
  01_data_preparation_eda_features.ipynb
  02_synthetic_scenario_and_overlap_review.ipynb
  03_schedule_clustering_baseline.ipynb
src/
  gtfs.py                  shared GTFS loading and calendar helpers
dataset/
  raw/chennai_gtfs/        local input only; not committed
  processed/               local notebook outputs only; not committed
```

## Step-by-step: run the notebooks

1. Open the project folder and switch to your own branch:

   ```powershell
   cd D:\DOCS\Powered-Public-Transit-Route-Optimization
   git switch mdzaid-khan
   ```

2. Set up Python and install the listed packages if you have not already:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. The Chennai feed should be in `dataset/raw/chennai_gtfs/`. The loader also accepts a `GTFS_DIR` environment variable.

4. Start Jupyter from the project root with `jupyter lab`, then run the three notebooks in order:
   - `01_data_preparation_eda_features.ipynb` — audit, scheduled supply, EDA, and route features.
   - `02_synthetic_scenario_and_overlap_review.ipynb` — synthetic scenario and cautious route-overlap shortlist.
   - `03_schedule_clustering_baseline.ipynb` — exploratory clustering of scheduled service patterns.

5. Processed CSVs are written to `dataset/processed/` and remain local. The feed and generated CSVs are ignored by Git.

The supervised ridership model and full-stack application are not established by the schedule-clustering baseline. Define and review the prediction target and its data source before training a supervised model. Expand the app after the model and evaluation approach are agreed.

## Synthetic ridership assumptions

The synthetic-scenario section uses the MTC performance indicator of 32.24 lakh passengers/day for FY 2024–25 as an illustrative whole-network calibration value. It assigns that total to route/hour rows in proportion to scheduled trip departures, with a 1.6 peak multiplier for 07:00–09:00 and 17:00–19:00. It does **not** establish how actual passengers are distributed across routes. Change the total, date, and multipliers only with clearly documented rationale; preserve the `data_status` and source columns in any export.

## Branch workflow

Work and push only to `mdzaid-khan`; do not push to `main` or another intern's branch. Commit code and documentation, not raw GTFS files or generated CSVs:

```bash
git status --short
git add README.md requirements.txt src notebooks
git commit -m "Add Chennai GTFS analysis notebooks"
git push origin mdzaid-khan
```

The existing repository contribution instructions also require each intern to use their own branch; this project setup follows that rule.
