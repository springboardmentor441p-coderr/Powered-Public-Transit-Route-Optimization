"""Replay notebooks 05-07 in an isolated copy, preserving all original forecasts."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(python):
    python=str(Path(shutil.which(python) or python).resolve())
    if not Path(python).is_file():
        raise FileNotFoundError(f'Interpreter not found: {python}')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    base=ROOT.parent/'router_archives'/'forecast_replay'/stamp
    workspace=base/'workspace'
    workspace.mkdir(parents=True,exist_ok=False)
    logs=base/'logs'
    logs.mkdir()
    protected_folders=['forecasting','forecasting_followup','forecast_error_analysis','prospective_registry']
    protected_paths=[p for name in protected_folders
        for p in (ROOT/'data/processed/new_york'/name).rglob('*') if p.is_file()]
    notebook_names=['05_demand_forecasting.ipynb','06_forecast_validation.ipynb','07_forecast_error_analysis.ipynb']
    protected_paths += [ROOT/'notebooks/new_york'/name for name in notebook_names]
    before={p.relative_to(ROOT).as_posix():digest(p) for p in protected_paths}
    for relative in ['scripts','tests','data/raw/new_york','data/raw/new_york_monitoring']:
        source=ROOT/relative
        if not source.exists():
            raise FileNotFoundError(f'Frozen input required: {relative}')
        shutil.copytree(source,workspace/relative,
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc','.ipynb_checkpoints'))
    # Restore only validated upstream tables and immutable registrations. All forecast CSVs
    # and fitted working models must be rebuilt by the executed notebooks.
    processed=ROOT/'data/processed/new_york'
    restored=workspace/'data/processed/new_york'
    restored.mkdir(parents=True)
    for source in processed.iterdir():
        if source.is_file():
            shutil.copy2(source,restored/source.name)
    shutil.copytree(processed/'prospective_registry',restored/'prospective_registry')
    pointers=restored/'forecasting_followup'
    pointers.mkdir()
    for name in ['registration_pointer.json','baseline_registration_pointer.json']:
        shutil.copy2(processed/'forecasting_followup'/name,pointers/name)
    assert not list(restored.glob('forecast*/*.csv'))
    (workspace/'notebooks/new_york').mkdir(parents=True)
    for name in notebook_names:
        shutil.copy2(ROOT/'notebooks/new_york'/name,workspace/'notebooks/new_york'/name)
    shutil.copy2(ROOT/'requirements-forecast.lock.txt',workspace/'requirements-forecast.lock.txt')

    env=os.environ.copy()
    env.update(PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
    jupyter_data=base/'jupyter'
    spec=jupyter_data/'kernels'/'routeranker-replay'
    spec.mkdir(parents=True)
    (spec/'kernel.json').write_text(json.dumps({'argv':[str(Path(python).resolve()),'-m','ipykernel_launcher','-f','{connection_file}'],
        'display_name':'Forecast replay','language':'python'}),encoding='utf-8')
    env['JUPYTER_PATH']=str(jupyter_data)
    package_query="""import importlib.metadata as m,json,sys
from pathlib import Path
names=[line.split('==')[0] for line in Path('requirements-forecast.lock.txt').read_text().splitlines() if line and not line.startswith('#')]
print(json.dumps({'python':sys.version.split()[0],'prefix':sys.prefix,'base_prefix':sys.base_prefix,'packages':{n:m.version(n) for n in names}}))"""
    runtime=json.loads(subprocess.check_output([python,'-c',package_query],cwd=workspace,env=env,text=True,encoding='utf-8'))
    expected={line.split('==')[0]:line.split('==')[1].split(';')[0].strip()
              for line in (ROOT/'requirements-forecast.lock.txt').read_text().splitlines()
              if line and not line.startswith('#')}
    mismatches={name:{'expected':version,'found':runtime['packages'].get(name)}
                for name,version in expected.items() if runtime['packages'].get(name)!=version}
    if mismatches:
        raise ValueError(f'Installed packages differ from replay lock: {mismatches}')
    expected_python=json.loads((ROOT/'data/processed/new_york/forecasting/forecast_manifest.json').read_text())['python_version']
    if runtime['python']!=expected_python:
        raise ValueError(f"Replay requires recorded Python {expected_python}; found {runtime['python']}")

    commands=[('tests',[python,'-m','unittest','discover','-s','tests','-v']),
        ('notebooks',[python,'-u','scripts/execute_notebooks.py','--kernel','routeranker-replay',
                       *['notebooks/new_york/'+name for name in notebook_names]]),
        ('audit_05',[python,'scripts/audit_forecast.py']),
        ('audit_06',[python,'scripts/audit_forecast_followup.py']),
        ('audit_07',[python,'scripts/audit_forecast_error_analysis.py'])]
    runs=[]
    for label,command in commands:
        print('Replay:',label,flush=True)
        log=logs/f'{label}.log'
        with log.open('w',encoding='utf-8') as handle:
            process=subprocess.Popen(command,cwd=workspace,env=env,stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            for line in process.stdout:
                handle.write(line)
                handle.flush()
                if line.startswith(('Running ','Saved:')):
                    print(line.strip(),flush=True)
            code=process.wait()
        runs.append({'step':label,'exit_code':code})
        if code:
            raise RuntimeError(f'Replay {label} failed; preserved log: {log}')
    # Compare tables, not notebook timing metadata or Python pickle byte layout.
    import pandas as pd
    comparisons=[]
    manifests={'forecasting':'forecast_manifest.json','forecasting_followup':'followup_manifest.json',
               'forecast_error_analysis':'error_analysis_manifest.json'}
    for folder,name in manifests.items():
        source=ROOT/'data/processed/new_york'/folder
        replay=workspace/'data/processed/new_york'/folder
        manifest=json.loads((source/name).read_text())
        for product in manifest['products']:
            original=source/f'{product}.csv'
            rebuilt=replay/f'{product}.csv'
            a,b=pd.read_csv(original,low_memory=False),pd.read_csv(rebuilt,low_memory=False)
            pd.testing.assert_frame_equal(a,b,check_dtype=True,check_exact=False,rtol=1e-10,atol=1e-8)
            comparisons.append({'product':folder+'/'+product,'rows':len(a),
                                'numerically_equivalent':True,'byte_identical':digest(original)==digest(rebuilt)})
    assert before=={p.relative_to(ROOT).as_posix():digest(p) for p in protected_paths}
    test_log=(logs/'tests.log').read_text(encoding='utf-8')
    match=re.search(r'Ran (\d+) tests?',test_log)
    assert match,'Test runner did not report a test count'
    skipped=re.search(r'skipped=(\d+)',test_log)
    skipped_count=int(skipped.group(1)) if skipped else 0
    assert skipped_count==0,'Full replay requires local integration tests to run, not skip'
    output=ROOT/'reports/forecast_milestone'
    output.mkdir(parents=True,exist_ok=True)
    result={'completed_utc':datetime.now(timezone.utc).isoformat(),'workspace':str(workspace),
        'isolated_workspace':True,'isolated_python_environment':runtime['prefix']!=runtime['base_prefix'],
        'python_version':runtime['python'],'runtime_packages':runtime['packages'],
        'lock_sha256':digest(ROOT/'requirements-forecast.lock.txt'),'commands':runs,
        'tables_compared':len(comparisons),'byte_identical_tables':sum(item['byte_identical'] for item in comparisons),
        'numeric_tolerance':{'rtol':1e-10,'atol':1e-8},'comparisons':comparisons,
        'tests':{'run':int(match.group(1)),'skipped':skipped_count,'passed':int(match.group(1))-skipped_count},
        'original_files_unchanged':len(before),'registrations_reused_without_reissuing':True}
    result['forecast_tables_prepopulated']=0
    (base/'replay_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (output/'reproducibility.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['comparisons','runtime_packages','workspace']},indent=2),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',default=sys.executable,help='Interpreter with the exact replay lock installed')
    args=parser.parse_args()
    run(args.python)
