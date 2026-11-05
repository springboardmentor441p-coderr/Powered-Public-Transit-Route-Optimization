"""Command line for the learning loop.
  python -m src.learn corpus --gtfs real_data/Pune_PMPML_gtfs.zip --name Pune     # add a feed to the training corpus
  python -m src.learn train [--fast]                                              # learn from the whole corpus, save model + card
  python -m src.learn add --gtfs new_city.zip --name Hyderabad                    # corpus + retrain + champion/challenger decision
  python -m src.learn predict --gtfs some_city.zip --name X --out peer_gap.csv    # apply the saved model to any feed"""
import argparse, json, sys
from pathlib import Path
from . import learning as L, gtfs_validation as gv

def add_corpus(zip_path, name):
    feed = gv.read_zip_safely(zip_path); T, info, val, rep = L.build_city_table(feed, name)
    L.corpus_save(name, T, info, val, rep, source=str(Path(zip_path).name)); print(f"added {name}: {len(info)} routes, {len(T)} route-hours (validation: {val['status']})")

def retrain(fast=False):
    art, card, gap = L.train(fast=fast, names_models=(("baseline_mean", "baseline_hour_mean", "poisson_linear", "gradient_boosting") if fast else None) or ("baseline_mean", "baseline_hour_mean", "poisson_linear", "random_forest", "gradient_boosting")); ok, why = L.promote_or_reject(art, card)
    (L.MODEL_DIR.parent / "outputs").mkdir(exist_ok=True); gap.to_csv(L.MODEL_DIR.parent / "outputs" / "peer_gap.csv", index=False) if ok else None
    print(f"version {card['version']} | best={card['best_model']} | promoted={ok} | {why}"); return card

def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m src.learn"); sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("corpus", "add", "predict"):
        p = sub.add_parser(c); p.add_argument("--gtfs", required=True); p.add_argument("--name", required=True)
        if c == "predict": p.add_argument("--out", default="peer_gap.csv"); p.add_argument("--mode", default="auto", choices=["auto", "self", "pooled"])
    t = sub.add_parser("train"); t.add_argument("--fast", action="store_true"); a = ap.parse_args(argv)
    try:
        if a.cmd == "corpus": add_corpus(a.gtfs, a.name)
        elif a.cmd == "train": retrain(a.fast)
        elif a.cmd == "add": add_corpus(a.gtfs, a.name); retrain(fast=True)
        else:
            d, val, rep = L.predict_feed(L.load_model(), gv.read_zip_safely(a.gtfs), a.name, a.mode); d.to_csv(a.out, index=False)
            print(d.flag.value_counts().to_string(), f"\nsaved {a.out}")
    except (gv.GTFSError, FileNotFoundError, ValueError) as e: print("ERROR:", e); sys.exit(1)

if __name__ == "__main__": main()
