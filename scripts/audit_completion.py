"""Reproduce added planning evidence and independently check allocation optimality."""
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dashboard.data import table, inventory
from scripts.gtfs_import import inspect_gtfs
from scripts.planning_proposals import allocate_service, candidate_actions, route_change_candidates


def run():
    out=ROOT/'reports/completion';out.mkdir(parents=True,exist_ok=True)
    audit=inventory()
    assert audit.status.eq('verified').all()
    result,excluded,summary=allocate_service(table('baselines'),'Weekday',50,.2)
    n=result.scenario_mean_departures.to_numpy(float)
    baseline=result.mean_departures.to_numpy(float)
    demand=result.mean_boardings.to_numpy(float)
    costs=(result.mean_bus_hours/result.mean_departures).to_numpy(float)
    lower=np.isclose(n,baseline,atol=1e-6,rtol=0)
    upper=np.isclose(n,baseline*1.2,atol=1e-6,rtol=0)
    free=~(lower|upper)
    gains=demand**2/(n*n*costs)
    assert free.any(), 'Expected an interior allocation for this audit example'
    multiplier=float(np.median(gains[free]))
    np.testing.assert_allclose(gains[free],multiplier,rtol=1e-7)
    assert (gains[lower]<=multiplier+1e-6).all()
    assert (gains[upper]>=multiplier-1e-6).all()
    assert n.min()>0 and (n>=baseline-1e-8).all() and (n<=baseline*1.2+1e-8).all()
    spend=float(np.dot(n-baseline,costs))
    np.testing.assert_allclose(spend,50.,atol=1e-7)
    np.testing.assert_allclose(np.sum(demand*demand/n),summary['allocation_objective'])
    uniform=baseline*(1+spend/result.mean_bus_hours.sum())
    assert np.sum(demand*demand/n)<=np.sum(demand*demand/uniform)+1e-6
    result.to_csv(out/'constrained_allocation.csv',index=False)
    excluded.to_csv(out/'allocation_exclusions.csv',index=False)
    (out/'allocation_summary.json').write_text(json.dumps(summary,indent=2))
    candidate_actions(table('review'),table('signals'),table('overlap')).to_csv(out/'review_actions.csv',index=False)
    candidates=route_change_candidates(table('overlap'),table('groups'))
    candidates.to_csv(out/'route_change_hypotheses.csv',index=False)
    source=ROOT/'data/raw/new_york/gtfs/archive/manhattan_20260903.zip'
    receipt=json.loads(source.with_name(source.name+'.receipt.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==receipt['sha256']
    imported,routes,_=inspect_gtfs(source.read_bytes(),'2026-09-14')
    (out/'real_gtfs_import_audit.json').write_text(json.dumps(imported,indent=2))
    routes.to_csv(out/'real_gtfs_route_profiles.csv',index=False)
    checked=0
    if (out/'protected_before.json').exists():
        original=json.loads((out/'protected_before.json').read_text())
        for name,expected in original.items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
        checked=len(original)
    verification={'dashboard_inputs_verified':len(audit),'allocation_kkt_conditions_verified':True,
                  'allocation_interior_routes':int(free.sum()),'budget_spend':spend,
                  'equal_spend_comparator_passed':True,'route_change_hypotheses':len(candidates),
                  'real_import_stop_events':imported['stop_events'],
                  'previous_data_notebooks_unchanged':checked,'independent_load_labels_installed':False,
                  'empirical_crowding_accuracy_claimed':False,'measured_passenger_benefits_claimed':False,
                  'docker_execution_verified':False}
    test_file=out/'test_results.txt'
    if test_file.exists():
        raw=test_file.read_bytes()
        content=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig',errors='replace')
        tests=re.search(r'Ran (\d+) tests in',content)
        verification['test_count']=int(tests.group(1)) if tests else None
        verification['tests_passed']='\nOK' in content
    browser=out/'browser/result.json'
    if browser.exists():verification['browser']=json.loads(browser.read_text())
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    print(json.dumps(verification,indent=2))


if __name__=='__main__':run()
