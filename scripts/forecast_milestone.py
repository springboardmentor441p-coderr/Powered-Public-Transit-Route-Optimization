"""Consolidate verified forecast experiments and record a bounded milestone decision."""
from datetime import datetime,timezone
import json
from pathlib import Path

import nbformat
import pandas as pd

from forecasting import sha256

ROOT=Path(__file__).resolve().parents[1]


def build():
    base=ROOT/'data/processed/new_york'
    locations={'05':('forecasting','forecast_manifest.json'),
               '06':('forecasting_followup','followup_manifest.json'),
               '07':('forecast_error_analysis','error_analysis_manifest.json')}
    manifests={key:json.loads((base/folder/name).read_text()) for key,(folder,name) in locations.items()}
    products_checked=0
    for key,(folder,name) in locations.items():
        for product,record in manifests[key]['products'].items():
            assert sha256(base/folder/f'{product}.csv')==record['sha256'],(folder,product)
            products_checked+=1
    for name,digest in manifests['07']['protected_files'].items():
        assert sha256(ROOT/name)==digest,name
    a,b,c=[manifests[key]['summary'] for key in ['05','06','07']]
    policy=json.loads((ROOT/'documentation/FORECAST_ACCEPTANCE.json').read_text())
    comparisons=[]

    def compare(protocol,start,end,maturity,records,model,baseline,description):
        table=pd.DataFrame(records).set_index('model')
        m,r=table.loc[model],table.loc[baseline]
        assert m.rows==r.rows and m.actual_total==r.actual_total
        comparisons.append({'protocol':protocol,'first_target':start,'last_target':end,
            'maturity_or_assumed_delay_days':maturity,'model':model,'baseline':baseline,
            'route_dates':int(m.rows),'routes':int(m.routes),'model_mae':float(m.mae),
            'baseline_mae':float(r.mae),'mae_improvement_percent':100*(1-float(m.mae)/float(r.mae)),
            'model_wape':float(m.wape),'baseline_wape':float(r.wape),
            'model_bias':float(m.bias),'baseline_bias':float(r.bias),
            'interpretation':description})

    compare('05 retrospective test','2026-08-03','2026-09-27',7,a['test_scores'],
        a['selected_model'],a['best_validation_baseline'],'Modest pooled gain; not consistent across weeks/months')
    compare('06 maturity-aware evaluation','2026-09-07','2026-09-27',14,b['evaluation_scores'],
        b['selected_model'],'seasonal_mean4','Different model and period; do not pool with notebook 05')
    compare('06 later-acquired October outcomes','2026-10-05','2026-10-11',7,b['later_outcome_scores'],
        a['selected_model'],'seasonal_mean4','Preserved historical outlook; baseline is stronger on these outcomes')
    compare('07 earlier development assessment','2025-10-13','2025-11-23',14,c['assessment_scores'],
        c['selected_candidate'],c['selection_chosen_baseline'],'Retrospective candidate replay; no promotion')
    notebook_audits=[]
    for name in ['05_demand_forecasting.ipynb','06_forecast_validation.ipynb','07_forecast_error_analysis.ipynb']:
        notebook=nbformat.read(ROOT/'notebooks/new_york'/name,as_version=4)
        nbformat.validate(notebook)
        code=[cell for cell in notebook.cells if cell.cell_type=='code']
        assert [cell.execution_count for cell in code]==list(range(1,len(code)+1))
        for cell in code:
            assert cell.outputs and all(o.output_type!='error' for o in cell.outputs)
            assert not cell.metadata.get('collapsed',False)
            assert not cell.metadata.get('jupyter',{}).get('outputs_hidden',False)
        notebook_audits.append({'notebook':name,'code_cells':len(code),
                               'saved_outputs':sum(len(cell.outputs) for cell in code)})
    registrations=[]
    for filename in ['registration_pointer.json','baseline_registration_pointer.json']:
        pointer=json.loads((base/'forecasting_followup'/filename).read_text())
        folder=ROOT/pointer['registration']
        metadata=json.loads((folder/'registration.json').read_text())
        assert sha256(folder/'forecasts.csv')==metadata['forecast_sha256']
        if metadata.get('model_sha256'):
            assert sha256(folder/'model.pkl')==metadata['model_sha256']
        first=pd.Timestamp(metadata['first_target']).tz_localize('America/New_York')
        assert pd.Timestamp(metadata['registered_utc'])<first
        registrations.append({'model':metadata['selected_model'],'registered_utc':metadata['registered_utc'],
            'first_target':metadata['first_target'],'last_target':metadata['last_target'],
            'forecast_route_dates':287,'forecast_sha256':metadata['forecast_sha256']})
    replay_path=ROOT/'reports/forecast_milestone/reproducibility.json'
    replay=json.loads(replay_path.read_text())
    assert replay['isolated_workspace'] and replay['isolated_python_environment']
    assert all(item['exit_code']==0 for item in replay['commands'])
    assert replay['tables_compared']==products_checked
    assert all(item['numerically_equivalent'] for item in replay['comparisons'])
    assert replay['lock_sha256']==sha256(ROOT/'requirements-forecast.lock.txt')
    replay_workspace=Path(replay['workspace'])
    verified_code={}
    for folder in ['scripts','tests']:
        for path in (ROOT/folder).glob('*.py'):
            if path.name=='forecast_milestone.py':
                continue  # This report builder is outside the analytical replay.
            relative=path.relative_to(ROOT)
            assert sha256(path)==sha256(replay_workspace/relative),str(relative)
            verified_code[relative.as_posix()]=sha256(path)
    for record in notebook_audits:
        relative=Path('notebooks/new_york')/record['notebook']
        original_notebook=nbformat.read(ROOT/relative,as_version=4)
        rebuilt_notebook=nbformat.read(replay_workspace/relative,as_version=4)
        assert [(cell.cell_type,cell.source) for cell in original_notebook.cells]==[
            (cell.cell_type,cell.source) for cell in rebuilt_notebook.cells],str(relative)
    result={'generated_utc':datetime.now(timezone.utc).isoformat(),
        'milestone_version':'1.0','evidence_snapshot':b['snapshot'],
        'evidence_observed_utc':json.loads((ROOT/b['snapshot']/'poll_summary.json').read_text())['observed_utc'],
        'research_milestone_status':'complete_for_review','deployment_status':'not_accepted',
        'reference_model':'seasonal_mean4','promoted_model':None,'scope':'41 Manhattan routes; seven daily boarding totals',
        'policy':policy,'comparisons':comparisons,
        'interval_results_06':b['interval_coverage'],'interval_results_07':c['assessment_interval_coverage'],
        'notebooks':notebook_audits,'total_code_cells':sum(item['code_cells'] for item in notebook_audits),
        'total_saved_outputs':sum(item['saved_outputs'] for item in notebook_audits),
        'products_verified':products_checked,'registrations':registrations,
        'prospective_status_as_of_snapshot':'pending','prospective_scored_route_dates':0,
        'earliest_full_maturity_date':'2026-11-30','prospective_origins_registered':1,
        'prospective_origins_required':policy['minimum_mature_weekly_origins'],
        'reproducibility':{'isolated_environment':True,'tables_compared':replay['tables_compared'],
            'byte_identical_tables':replay['byte_identical_tables'],'python_version':replay['python_version'],
            'reproducibility_report_sha256':sha256(replay_path)},
        'verified_analytical_code':verified_code,
        'acceptance_assessment':[
            {'criterion':'Saved calculations, provenance, audits and isolated replay','status':'pass'},
            {'criterion':'Consistent prospective point improvement','status':'pending',
             'reason':'No mature prospective outcomes; retrospective gains are inconsistent'},
            {'criterion':'Reliable interval coverage and width','status':'not_established',
             'reason':'2026 nominal 90% coverage is 62.83%; earlier replay does not repair it'},
            {'criterion':'Historical first-publication/revision reconstruction','status':'unavailable',
             'reason':'New snapshots do not reconstruct earlier unseen row-value vintages'},
            {'criterion':'Operational deployment','status':'not_accepted',
             'reason':'Research completion is separate from meeting prospective review criteria'}],
        'tests_passed':replay['tests']['passed'],'existing_forecasts_preserved':True,
        'provenance':{str((base/folder/name).relative_to(ROOT)):sha256(base/folder/name)
                      for folder,name in locations.values()}}
    output=ROOT/'reports/forecast_milestone'
    output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(comparisons).to_csv(output/'experiment_comparison.csv',index=False)
    (output/'milestone.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:result[key] for key in ['research_milestone_status','deployment_status',
        'reference_model','products_verified','total_code_cells','total_saved_outputs','tests_passed',
        'prospective_status_as_of_snapshot']},indent=2))
    return result


if __name__=='__main__':build()
