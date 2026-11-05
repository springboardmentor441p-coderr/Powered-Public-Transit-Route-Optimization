"""Builds notebooks/RouteRanker_ML_Model.ipynb (then executed with nbconvert so outputs are embedded)."""
import nbformat as nbf
from pathlib import Path
nb = nbf.v4.new_notebook(); C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip())); code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# RouteRanker – a machine-learning model that learns from real transit data
This notebook trains, evaluates and saves the model **step by step on real GTFS feeds** (Pune PMPML, Chennai MTC, Bengaluru BMTC).

**What the model learns (and what it does not).** Published GTFS feeds contain *schedules*, not passengers. So the model learns how each operator
**allocates service**: given a route's geometry and network position (length, stops, connectivity, distance to the core, overlap, hour of day…),
how many trips does it get in that hour? Routes that get far fewer/more trips than comparable routes are flagged as
*relatively under-/over-served versus peers*. That is a **screening signal**; confirming crowding needs ridership data.
""")
code("""
import sys, json, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, '..')
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from pathlib import Path
from sklearn.ensemble import HistGradientBoostingRegressor
from src import learning as L
plt.rcParams.update({'figure.dpi': 90, 'axes.grid': True, 'grid.alpha': .3})
print(Path('../real_data/SOURCES.md').read_text()[:1500])
""")
md("## 1. The real data\nThe corpus was built by `python -m src.learn corpus ...` from the three downloaded feeds (validated, cleaned, row counts logged). One row = one route in one hour of a typical weekday.")
code("""
T, I, metas = L.corpus_load()
print(pd.DataFrame(metas)[['name','source','routes','rows','added']].to_string(index=False))
print('\\nrow-level table:', T.shape); T[['city','route_uid','hour','trips','city_scale'] + L.FEATURES[:6]].head(8)
""")
md("""
**Features** (all computed from the schedule and stop geography; the route's own timetable is *not* an input):
`hour` (+ cyclic encoding, position in the service day, peak flags) · `route_length_km`, `n_stops`, `avg_stop_spacing_km`, `trip_duration_min`, `avg_speed_kmph`, `service_span_hr` ·
`mean_conn`/`max_conn` (how many routes serve its stops) · `frac_stops_shared`, `hub_frac`, `max_overlap` · `mean_dist_norm`/`min_dist_norm` (distance to the city core, normalised by city size) ·
`other_service_log` (trips of *other* routes at its stops).

**Target:** trips in that route-hour, expressed **relative to the city's mean** (operators differ hugely in fleet size, so the model learns structure, not scale).
City-level descriptors were deliberately removed: with only three cities they act as a city ID and the model would just memorise operators.
""")
code("""
fig, ax = plt.subplots(1, 3, figsize=(15, 3.6))
for c, g in T.groupby('city'): ax[0].plot(g.groupby('hour').trips.mean(), label=c)
ax[0].set(title='Average trips per route-hour', xlabel='hour'); ax[0].legend()
for c, g in T.groupby('city'): ax[1].hist(g.groupby('route_uid').trips.sum().clip(upper=120), bins=40, alpha=.5, label=c)
ax[1].set(title='Trips per route per day (clipped at 120)'); ax[1].legend()
r = T.drop_duplicates('route_uid'); ax[2].scatter(r.service_span_hr + np.random.rand(len(r))*.4, r.route_uid.map(T.groupby('route_uid').trips.sum()).clip(upper=150), s=3, alpha=.3)
ax[2].set(title='Longer operating span -> more trips', xlabel='service span (h)', ylabel='trips/day'); plt.tight_layout(); plt.show()
""")
md("## 2. Baselines first\nA model only 'learns' if it beats simple rules. Baseline 0 = always the average; baseline 1 = average for that hour of the day (ignores the route entirely).")
md("""
## 3. Training and honest evaluation: learning each city's network
For every city we train on **its own routes** and test on **routes the model has never seen** (5-fold, grouped by route so a route is never in both sets).
""")
code("""
from sklearn.model_selection import GroupKFold
res = []
for city in sorted(T.city.unique()):
    D = T[T.city == city].reset_index(drop=True)
    for name in ['baseline_mean', 'baseline_hour_mean', 'poisson_linear', 'random_forest', 'gradient_boosting']:
        oof = np.zeros(len(D))
        for a, b in GroupKFold(5).split(D, groups=D.route_uid):
            oof[b], _ = L._fit_predict(name, D.iloc[a], D.iloc[b])          # fit on relative target, predict, rescale
        s = L.score(D.trips, oof, D.route_uid.values); res.append(dict(city=city, model=name, **s))
R = pd.DataFrame(res); piv = R.pivot(index='model', columns='city', values='mae').round(3)
print('MAE in trips per route-hour on held-out routes (lower is better)'); display(piv)
display(R.pivot(index='model', columns='city', values='r2').round(3).rename_axis('R-squared'))
piv.T.plot.bar(figsize=(10, 3.8), title='Held-out-route error by model'); plt.ylabel('MAE'); plt.show()
""")
code("""
base = R[R.model == 'baseline_hour_mean'].set_index('city').mae; gb = R[R.model == 'gradient_boosting'].set_index('city').mae
print('Error reduction of the learned model vs the best baseline:'); print((1 - gb / base).round(3).rename('skill'))
""")
md("""
## 4. Does it really *learn from data*? Learning curve
Fixed held-out routes; the model is trained on growing numbers of routes. If it learns, error falls and R² rises as it sees more data.
""")
code("""
lc = L.learning_curve(T, seeds=2); P = pd.DataFrame(lc['points'])
fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
ax[0].errorbar(P.n_routes, P.mae, yerr=P.mae_sd, marker='o'); ax[0].axhline(lc['baseline_hour_mean_mae'], ls='--', c='gray', label='hour-mean baseline'); ax[0].set(xscale='log', xlabel='training routes', ylabel='MAE', title='Error falls with more data'); ax[0].legend()
ax[1].plot(P.n_routes, P.r2, marker='o', c='C2'); ax[1].set(xscale='log', xlabel='training routes', ylabel='R-squared', title='Explained variance rises'); plt.show(); P.round(3)
""")
md("""
## 5. Generalising to a city the model has never seen (leave-one-city-out) – the honest limit
Train on two cities, test on the third. Values come from the saved model card (`models/model_card.json`, produced by `python -m src.learn train`).
""")
code("""
card = json.load(open('../models/model_card.json'))
lo = pd.DataFrame({m: {c: v['mae'] for c, v in d.items()} for m, d in card['loco'].items()}).round(3); display(lo.rename_axis('unseen city (MAE)'))
display(pd.DataFrame({m: {c: v['r2'] for c, v in d.items()} for m, d in card['loco'].items()}).round(3).rename_axis('unseen city (R-squared)'))
""")
md("""
**Reading this honestly:** with only three operators, knowledge transfers weakly between cities (Pune is even worse than the baseline), because each operator schedules differently.
That is why RouteRanker **learns from the feed you give it** (section 3) and only uses the pooled model as a prior. More real cities in the corpus will improve cross-city transfer; the learning loop (section 8) makes adding them one command.
""")
code("""
imp = pd.Series(card['permutation_importance']).sort_values(); imp.plot.barh(figsize=(7, 4), title='Permutation importance (increase in error when a feature is shuffled)'); plt.show()
""")
md("## 6. Using what was learned: peer comparison of routes\nFor each route: actual daily trips vs the trips the model expects for a comparable route (predicted on held-out routes). Only the extreme tails are flagged.")
code("""
G = pd.read_csv('../outputs/peer_gap.csv'); print(G.flag.value_counts().to_string())
fig, ax = plt.subplots(figsize=(8, 3.4))
for c, g in G.groupby('city'): ax.hist(np.log2(g.ratio.clip(.05, 20)), bins=60, alpha=.45, label=c, density=True)
ax.set(xlabel='log2(actual / expected trips)', title='Routes versus their peers (0 = as expected)'); ax.legend(); plt.show()
cols = ['city', 'route_short_name', 'route_long_name', 'actual_trips', 'expected_trips', 'ratio', 'flag']
print('Most relatively UNDER-served vs peers (candidates to check for crowding, needs ridership data):')
display(G[G.flag.str.contains('under')].sort_values('ratio').groupby('city').head(4)[cols].round(2))
""")
md("## 7. Saving, loading and applying the model to any feed\nThe trained model is a file: `models/service_model.joblib` (+ `model_card.json`, `registry.json`). `predict_feed` learns from the feed it is given and checks reliability.")
code("""
from src import gtfs_validation as gv
art = L.load_model(); print('model version', art['version'], '| best model:', art['best'], '| trained on', art['cities'])
feed = gv.read_zip_safely('../real_data/Pune_PMPML_gtfs.zip')
out, val, rep = L.predict_feed(art, feed, 'PuneCheck', mode='auto')
print('validation:', val['status'], '| mode:', out['mode'].iloc[0], '| skill on held-out routes: %.2f' % out['model_skill'].iloc[0]); print(out.flag.value_counts().to_string())
""")
md("""
## 8. Learning from new data (the learning loop)
Add any new city's GTFS and the model **retrains on everything**; a champion/challenger rule decides whether the new version replaces the old one:
```
python -m src.learn add --gtfs path\\to\\new_city.zip --name Hyderabad
```
The registry below is the version history written by the code.
""")
code("""
pd.DataFrame(json.load(open('../models/registry.json')))[['version', 'trained_at', 'cities', 'n_routes', 'best', 'cv_mae', 'promoted', 'reason']]
""")
md("""
## 9. Limitations
* Learns **service allocation**, not passenger demand: a route flagged "under-served vs peers" may simply be a low-demand route. Confirm with ridership/APC data before changing service.
* Cross-city transfer is weak with 3 cities (section 5); per-feed learning is the supported use.
* The Bengaluru feed is unofficial and covers only routes with live tracking; Pune's is auto-generated; Chennai's contains non-bus modes (filtered) and some junk identifiers (flagged by validation).
* No causal claims; no cost or passenger-impact figures are produced.
""")
nb["cells"] = C; nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
Path(__file__).resolve().parent.parent.joinpath("notebooks").mkdir(exist_ok=True)
nbf.write(nb, Path(__file__).resolve().parent.parent / "notebooks" / "RouteRanker_ML_Model.ipynb")
