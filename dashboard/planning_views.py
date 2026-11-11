"""Import, comparison, proposal and allocation workflows."""
from datetime import date
from io import BytesIO
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard import charts
from dashboard.data import ROOT, DAY_TYPES, table, scenario_export, catalog
from dashboard.views import export, metric, number, period_note
from scripts.gtfs_import import FeedError, inspect_gtfs
from scripts.planning_proposals import allocate_service, candidate_actions, route_change_candidates, save_proposal, load_proposals
from scripts.service_scenarios import compare_frequency
from scripts.load_classification import LABEL_FIELDS, validate_labels, train_classifier

SAVED = ROOT / 'data/app/proposals'


def comparison(route):
    st.title('Route comparison')
    period_note()
    baselines = table('baselines')
    options = sorted(set(baselines.bus_route) - {route})
    peer = st.selectbox('Compare with route', options, index=options.index('M34A+') if 'M34A+' in options else 0)
    kind = st.selectbox('Comparison day type', DAY_TYPES)
    rows = baselines.loc[baselines.bus_route.isin([route, peer]) & baselines.day_type.eq(kind)]
    st.dataframe(rows[['bus_route', 'route_long_name', 'baseline_status', 'observed_dates', 'mean_boardings',
                       'mean_departures', 'mean_bus_hours', 'boardings_per_departure', 'boardings_per_bus_hour']],
                 hide_index=True, width='stretch', column_config={
                     'bus_route':'Route','route_long_name':'Corridor','baseline_status':'Evidence status',
                     'observed_dates':'Matched dates','mean_boardings':st.column_config.NumberColumn('Mean daily boardings',format='%.1f'),
                     'mean_departures':st.column_config.NumberColumn('Mean daily departures',format='%.2f'),
                     'mean_bus_hours':st.column_config.NumberColumn('Scheduled bus-hours / day',format='%.2f'),
                     'boardings_per_departure':st.column_config.NumberColumn('Boardings / departure',format='%.2f'),
                     'boardings_per_bus_hour':st.column_config.NumberColumn('Boardings / bus-hour',format='%.2f')})
    if rows.observation_dates_sha256.nunique() != 1:
        st.error('The two routes do not share the same comparison dates.')
        return
    st.caption('Both routes use the same exact observation dates. Source-withheld rates remain unavailable.')
    members = table('members')
    daily = members.loc[members.bus_route.isin([route, peer]) & members.day_type.eq(kind)]
    charts.line(daily, 'payment_date', 'analysis_boardings', 'Published daily boardings', 'bus_route')
    from dashboard.data import peer_overlaps, route_paths
    pair = peer_overlaps(route)
    pair = pair.loc[pair.peer.eq(peer)]
    st.subheader('Shared and exclusive coverage')
    st.dataframe(pair[['peer', 'shared_stop_ids', 'selected_route_only_stops', 'peer_only_stops', 'jaccard', 'snapshot_id']], hide_index=True, width='stretch')
    st.caption('Exclusive means relative to this pair. Walking access, passenger journeys and direction/time compatibility need separate evaluation.')
    with st.expander('Compare route geometry'):
        paths = [{**p, '_color': [8,127,140]} for p in route_paths(route)] + [{**p, '_color': [209,122,48]} for p in route_paths(peer)]
        charts.route_map(paths)
        st.caption(f'{route}: teal · {peer}: orange')
    export(rows, f'{route}_{peer}_{kind}_comparison.csv')


def imports(_route):
    st.title('GTFS import')
    st.write('Inspect a bus schedule on a selected service date before using it in a new analysis. Imports are isolated from the frozen Manhattan study.')
    payload = st.file_uploader('GTFS Schedule ZIP', type=['zip'], max_upload_size=100)
    selected = st.date_input('Service date to inspect', date(2026,9,14), key='import_date')
    if payload is None:
        st.info('Upload a GTFS ZIP containing agency, routes, trips, stops, stop_times, and calendar or calendar_dates. Frequency templates are counted separately from explicit trips.')
        return
    raw = payload.getvalue()
    identity = hashlib.sha256(raw).hexdigest() + str(selected)
    if st.button('Validate and inspect schedule', type='primary'):
        try:
            with st.spinner('Checking tables, calendars, references, time ordering and active bus service…'):
                summary, profiles, trips = inspect_gtfs(raw, selected)
            st.session_state['import_result'] = (identity, summary, profiles, trips)
        except FeedError as exc:
            st.error(str(exc))
    result = st.session_state.get('import_result')
    if result is None or result[0] != identity:
        return
    _, summary, profiles, trips = result
    st.success('Schedule inspection complete. This is project-field validation, not full GTFS certification.')
    metric(st.columns(4), [('Bus routes', number(summary['bus_routes']), 'Bus route types only.'),
                          ('Active trip templates', number(summary['active_bus_templates']), 'Calendar-selected templates; frequency templates can represent multiple departures.'),
                          ('Stops', number(summary['stops']), 'Stops in the uploaded feed.'),
                          ('Unavailable durations', number(summary['bus_templates_with_unavailable_duration']), 'Trip counts are retained; incomplete route service-hours are withheld.')])
    if profiles.counts_include_expected_service.any():
        st.warning('Some routes use headway-based service: their counts are expected departures, not exact scheduled times.')
    if summary['invalid_or_missing_stop_coordinates']:
        st.warning('Some stop coordinates are unavailable or invalid. Geometry features require additional review.')
    only_active=st.checkbox('Show only routes with active service',value=True)
    st.caption(f"{int(profiles.scheduled_or_expected_departures.gt(0).sum())} routes have active bus service on the selected date; {len(profiles)} route records are declared in the feed.")
    shown=profiles.loc[profiles.scheduled_or_expected_departures.gt(0)] if only_active else profiles
    st.dataframe(shown, hide_index=True, width='stretch')
    st.caption('Imported schedule hours use service-day trip durations. They cannot be substituted for the study’s clock-date exposure without rebuilding alignment.')
    export(profiles, 'imported_route_profiles.csv')
    export(trips, 'imported_active_trip_templates.csv', 'Download active trip templates')
    st.download_button('Download inspection record', json.dumps(summary, indent=2), file_name='gtfs_inspection.json', mime='application/json')
    if st.button('Save validated import locally'):
        folder = ROOT / 'data/app/imports' / summary['source_sha256']
        folder.mkdir(parents=True, exist_ok=True)
        source = folder/'source.zip'
        if not source.exists():
            source.write_bytes(raw)
        if hashlib.sha256(source.read_bytes()).hexdigest() != summary['source_sha256']:
            st.error('Existing import fingerprint mismatch.')
            return
        record = folder / (str(selected)+'_inspection.json')
        record.write_text(json.dumps(summary, indent=2), encoding='utf-8')
        profiles.to_csv(folder/(str(selected)+'_route_profiles.csv'), index=False)
        st.success('Validated source bytes and inspection saved in the local import collection. The study and trained models are unchanged.')


def proposals(route):
    st.title('Planning proposals')
    period_note()
    actions = candidate_actions(table('review'), table('signals'), table('overlap'))
    action = actions.set_index('bus_route').loc[route]
    st.subheader(f'Prepare a review for {route}')
    st.write('**Suggested next investigation:** '+action.proposed_review_action)
    st.write(action.corridor_review)
    st.caption(action.merge_or_split_status)
    export(actions, 'route_review_actions.csv', 'Download all review candidates')
    with st.expander('Route merge/split hypotheses and required checks'):
        candidates=route_change_candidates(table('overlap'),table('groups'))
        candidates=candidates.loc[candidates.route.eq(route)|candidates.peer.eq(route)]
        st.caption('Pilot screening: Jaccard ≥0.30 and at least ten shared stop IDs for corridor review; at least three stop patterns for variant review. These are investigation thresholds, not transport standards or proof that changes are beneficial.')
        st.dataframe(candidates,hide_index=True,width='stretch')
        export(candidates,f'{route}_route_change_hypotheses.csv')
    kind = st.selectbox('Proposal day type', DAY_TYPES)
    baseline = table('baselines')
    baseline = baseline.loc[baseline.bus_route.eq(route) & baseline.day_type.eq(kind)]
    title = st.text_input('Proposal title', value=f'{route} {kind} frequency review', max_chars=160)
    change = st.slider('Proposed departure change (%)', -50, 100, 10, 5)
    budget = st.number_input('Added bus-hours allowance per day', 0., 1000., 10.)
    result = compare_frequency(baseline, 1+change/100, max_added_bus_hours=budget)
    st.dataframe(result[['bus_route', 'day_type', 'mean_departures', 'scenario_mean_departures', 'mean_bus_hours',
                         'scenario_mean_bus_hours', 'arithmetic_status']], hide_index=True, width='stretch')
    questions = pd.DataFrame({'required_review': [
        'Confirm independent passenger-load observations before claiming crowding',
        'Check direction, origin and time windows for the proposed departures',
        'Check fleet, staffing, layover, deadhead and operating budget',
        'Preserve exclusive coverage, walking access and passenger transfers',
        'Obtain operational approval and design an outcome evaluation']})
    st.caption('This proposal can be saved for investigation, including a source-withheld result. Saving does not approve or apply service changes.')
    metadata = {'route': route, 'day_type': kind, 'frequency_factor': 1+change/100,
                'demand_assumption': 'historical paired demand fixed', 'max_added_bus_hours': budget,
                'minimum_retained_fraction': .8, 'data_release': catalog()['version'],
                'review_action': action.proposed_review_action, 'merge_or_split_status': action.merge_or_split_status}
    evidence = actions.loc[actions.bus_route.eq(route)]
    signals = table('signals'); signals = signals.loc[signals.bus_route.eq(route)]
    tables = {'scenario': result, 'review_evidence': evidence, 'signals': signals, 'required_checks': questions}
    if st.button('Save proposal', type='primary'):
        try:
            identifier = save_proposal(SAVED, title, metadata, tables)
            st.success('Proposal saved: '+identifier)
        except ValueError as exc:
            st.error(str(exc))
    st.download_button('Download proposal package', scenario_export(result, {'title': title, **metadata},
                       {k:v for k,v in tables.items() if k!='scenario'}), file_name=f'{route}_review_proposal.zip', mime='application/zip')
    st.subheader('Saved local proposals')
    records = load_proposals(SAVED)
    if not records:
        st.info('No proposals saved yet.')
    else:
        st.dataframe(pd.DataFrame([{k:r[k] for k in ['id','title','created_utc','integrity_valid','timetable_feasibility']} for r in records]), hide_index=True, width='stretch')
        ids = {r['id']:r for r in records}
        selected = st.selectbox('Open saved proposal', list(ids), format_func=lambda i: ids[i]['title']+' · '+i)
        record = ids[selected]
        if not record['integrity_valid']:
            st.error('Saved proposal data changed; export is withheld.')
        else:
            st.json(record['assumptions'])
            saved_tables = {Path(name).stem:pd.read_csv(SAVED/selected/name) for name in record['tables']}
            st.download_button('Download saved proposal', scenario_export(saved_tables.pop('scenario'), record,
                                saved_tables), file_name=f'{selected}.zip', mime='application/zip')


def allocation(_route):
    st.title('Budget allocation')
    period_note()
    st.write('Compare a constrained allocation of added service with an equal-spend uniform increase.')
    st.info('Objective: minimize the sum of squared mean daily boardings divided by mean departures. This is an explicit boarding-intensity concentration proxy. It does not model on-board loads, waiting times, passenger journeys or demand response.')
    kind = st.selectbox('Allocation day type', DAY_TYPES)
    budget = st.number_input('Network added bus-hours per day', min_value=0., max_value=10000., value=50., step=5.)
    cap = st.slider('Maximum departure increase per route (%)', 0, 100, 20, 5)
    result, excluded, summary = allocate_service(table('baselines'), kind, budget, cap/100)
    metric(st.columns(4), [('Eligible routes', str(summary['eligible_routes']), 'Same observation-date population; source gates applied.'),
                          ('Additional hours used', number(summary['spent_added_bus_hours'],2), 'Must not exceed the declared budget.'),
                          ('Unused budget', number(summary['unused_budget_bus_hours'],2), 'Can remain unused when bounds are reached.'),
                          ('Proxy reduction', f"{summary['relative_proxy_reduction']:.2%}" if summary['relative_proxy_reduction'] is not None else 'Undefined', 'Change in the declared mathematical objective, not measured passenger improvement.')])
    comparison = pd.DataFrame({'Scenario':['Baseline','Equal-spend uniform increase','Constrained allocation'],
                              'Objective':[summary['baseline_objective'], summary['equal_spend_uniform_objective'], summary['allocation_objective']]})
    charts.bar(comparison, 'Scenario','Objective','Alternative','Boarding-intensity concentration proxy')
    st.dataframe(result[['bus_route','mean_departures','scenario_mean_departures','delta_mean_departures','delta_mean_bus_hours','scenario_boardings_per_departure']], hide_index=True, width='stretch')
    if len(excluded):
        st.write('Excluded by source/eligibility gates:')
        st.dataframe(excluded, hide_index=True, width='stretch')
    st.caption('No route loses departures. Each route is bounded by the selected increase cap. Fractions are mean-daily service quantities, not an executable timetable.')
    st.download_button('Download allocation and assumptions', scenario_export(result, summary, {'excluded_routes':excluded,'objective_comparison':comparison}), file_name='service_allocation.zip', mime='application/zip')
    title = st.text_input('Allocation proposal title', value=f'{kind} added-service allocation')
    if st.button('Save allocation proposal'):
        try:
            identifier=save_proposal(SAVED,title,summary,{'scenario':result,'excluded_routes':excluded,'objective_comparison':comparison})
            st.success('Proposal saved: '+identifier)
        except ValueError as exc:
            st.error(str(exc))


def load_model(_route):
    st.title('Observed-load classification')
    st.warning('The current study has no independent balanced/overcrowded labels. No crowding model has been trained or evaluated on these boarding/schedule inputs.')
    st.write('This workflow accepts independently observed route/date assessments. GTFS frequency, daily boardings and cluster IDs are not substitutes for those labels.')
    st.download_button('Download required label-file header', ','.join(LABEL_FIELDS)+'\n', file_name='observed_load_labels_header.csv', mime='text/csv')
    st.caption('Required label_basis: independent_observed_load_assessment. Every row needs the actual observation source reference. The file contains no invented example labels.')
    uploaded = st.file_uploader('Independent observed-load labels CSV', type=['csv'], max_upload_size=10)
    if uploaded is None:
        return
    if uploaded.size > 10_000_000:
        st.error('Label CSV exceeds the 10 MB limit.'); return
    try:
        labels = validate_labels(pd.read_csv(BytesIO(uploaded.getvalue()), dtype={'bus_route':'string'}))
        st.dataframe(labels.head(30), hide_index=True, width='stretch')
        confirmed = st.checkbox('The labels were independently observed and their sources have been verified')
        if st.button('Train chronological classifier', disabled=not confirmed):
            with st.spinner('Training on earlier dates and evaluating on later dates…'):
                model, report, outputs = train_classifier(table('daily'), labels)
            identifier = save_proposal(ROOT/'data/app/load_experiments', 'Observed-load classification assessment',
                                       {'report': report, 'labels_sha256':hashlib.sha256(uploaded.getvalue()).hexdigest()},
                                       {'observed_labels':labels,'held_out_predictions':outputs})
            import joblib
            experiment = ROOT/'data/app/load_experiments'/identifier
            joblib.dump(model, experiment/'pipeline.joblib')
            (experiment/'model_manifest.json').write_text(json.dumps({
                'pipeline_sha256':hashlib.sha256((experiment/'pipeline.joblib').read_bytes()).hexdigest(),
                'evaluation':report, 'untrusted_model_loading_supported':False}, indent=2),encoding='utf-8')
            st.json(report)
            export(outputs, 'load_classification_holdout.csv')
            st.success('Retrospective experiment saved: '+identifier)
            st.caption('Source authenticity and point-in-time publication availability need independent verification. These results do not confer operational acceptance.')
    except (ValueError, pd.errors.ParserError) as exc:
        st.error(str(exc))


EXTRA_PAGES = {'Route comparison': comparison, 'Planning proposals': proposals,
               'Budget allocation': allocation, 'GTFS import': imports,
               'Observed-load classification': load_model}
