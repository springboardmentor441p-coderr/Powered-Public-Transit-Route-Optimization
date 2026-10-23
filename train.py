"""One command to run the whole project:  python train.py"""
import time, json, sys
from pathlib import Path
import pandas as pd
from src.config import *
from src import data_loader, pipeline, eda

def main():
    if not DATA_DIR.exists():
        print("No data found - generating synthetic GTFS for 23 cities ...")
        import subprocess; subprocess.check_call([sys.executable, str(ROOT / "data" / "generate_synthetic_gtfs.py")])
    t0 = time.time()
    print("[1/6] Loading GTFS ..."); ds = data_loader.load_all()
    print(f"      {len(ds)} cities"); print("[2/6] Cleaning + feature engineering ..."); bundle = pipeline.build_bundle(ds, data_loader.load_histories())
    r = bundle["routes"]; print(f"      {len(r)} routes | {len(bundle['stops'])} stops | classes: {r.label.value_counts().to_dict()}")
    print("[3/6] EDA figures ..."); eda.make_figures(bundle)
    eda.density_map(bundle, "Pune", FIG_DIR / "pune_density_map.html")
    print("[4/6] Training clustering + classifiers (grouped CV) ..."); art = pipeline.train(bundle)
    clf = art["classifier"]
    for k, m in clf["metrics"].items():
        print(f"      {k:14s} CV acc={m['grouped_cv']['accuracy']:.3f} F1={m['grouped_cv']['macro_f1']:.3f} | "
              f"val F1={m['stratified_val']['macro_f1']:.3f} | unseen-city F1={m.get('unseen_cities', {}).get('macro_f1', float('nan')):.3f}")
    print(f"      best = {clf['best']} | clusters: k={art['cluster']['metrics']['k']}, silhouette={art['cluster']['metrics']['kmeans_silhouette']:.3f}")
    if "forecaster" in art:
        fm = art["forecaster"]["metrics"]; print(f"      FORECAST backtest (train {fm['train_months']} past months -> predict next {fm['test_months']}): "
              + " | ".join(f"{k} WAPE={fm[k]['wape']:.3f}" for k in ("model", "seasonal_naive_drift", "seasonal_naive", "naive_last3")))
    print("[5/6] Inference + optimisation ..."); res = pipeline.analyze(bundle, art, honest_pred=clf["oof_pred"])
    b, a = res["impact"]["before"], res["impact"]["after"]
    for k in b: print(f"      {k:34s} {b[k]:10.3f} -> {a[k]:10.3f}")
    print("[6/6] Saving ..."); pipeline.save_art(art); pipeline.save_results(res)
    if "forecaster" in art: art["forecaster"]["backtest_city"].to_csv(OUT_DIR / "backtest_city.csv", index=False)
    summary = dict(classifier=clf["metrics"], best=clf["best"], clustering=art["cluster"]["metrics"], classification_report=clf["report"],
                   feature_importance=clf["importance"].head(15).round(4).to_dict(), cleaning=bundle["cleaning"],
                   impact=res["impact"], forecast=art.get("forecaster", {}).get("metrics"), actions=res["recs"].action.value_counts().to_dict())
    json.dump(summary, open(OUT_DIR / "metrics.json", "w"), indent=2, default=float)
    print(f"Done in {time.time() - t0:.0f}s. Run the dashboard:  streamlit run app.py")

if __name__ == "__main__": main()
