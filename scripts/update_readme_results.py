"""Fill the RESULTS block of README.md from reports/metrics/*.json (run after the pipeline)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT / "reports/metrics/model_metrics.json").read_text())
MAN = json.loads((ROOT / "reports/metrics/pipeline_manifest.json").read_text())
cl, fc, km, db = M["classification"], M["forecasting"], M["clustering"]["kmeans"], M["clustering"]["dbscan"]
imp = M["optimisation_impact_validation"]

block = f"""
## 📈 Results (last pipeline run: {MAN['built_at_ist']})

Data: **{MAN['data_start']} → {MAN['data_end']}**, {MAN['routes']} routes, {MAN['route_hours']:,} route-hours (hourly).
Validation = last 28 days (chronological hold-out).

| Model | Metric | Result |
|---|---|---|
| KMeans (k={km['k']}) | silhouette / Davies-Bouldin | {km['silhouette']:.3f} / {km['davies_bouldin']:.3f} |
| DBSCAN (eps={db['eps']:.2f}) | dense clusters / outlier routes | {db['n_clusters']} / {db['n_outliers']} |
| Random Forest classifier | accuracy / macro-F1 | {cl['RandomForest']['accuracy']:.3f} / {cl['RandomForest']['f1_macro']:.3f} |
| XGBoost classifier | accuracy / macro-F1 | {cl['XGBoost']['accuracy']:.3f} / {cl['XGBoost']['f1_macro']:.3f} |
| Seasonal baseline forecaster | MAE / R² / WAPE | {fc['SeasonalProfileBaseline']['mae']:.1f} / {fc['SeasonalProfileBaseline']['r2']:.3f} / {fc['SeasonalProfileBaseline']['wape']:.1%} |
| Random Forest forecaster | MAE / R² / WAPE | {fc['RandomForest']['mae']:.1f} / {fc['RandomForest']['r2']:.3f} / {fc['RandomForest']['wape']:.1%} |
| XGBoost forecaster | MAE / R² / WAPE | {fc['XGBoost']['mae']:.1f} / {fc['XGBoost']['r2']:.3f} / {fc['XGBoost']['wape']:.1%} |

Selected: classifier **{cl['best']}**, forecaster **{fc['best']}**.
Optimiser on the hold-out: overcrowded route-hours {imp['overcrowded_share_now']:.1%} → {imp['overcrowded_share_opt']:.1%},
underutilised {imp['underutilized_share_now']:.1%} → {imp['underutilized_share_opt']:.1%},
vehicle-hours {imp['veh_hours_now']:,.0f} → {imp['veh_hours_opt']:,.0f}.
"""
readme = (ROOT / "README.md").read_text(encoding="utf-8")
readme = re.sub(r"<!-- RESULTS:START -->.*<!-- RESULTS:END -->",
                "<!-- RESULTS:START -->" + block + "<!-- RESULTS:END -->", readme, flags=re.S)
(ROOT / "README.md").write_text(readme, encoding="utf-8")
print("README results updated")
