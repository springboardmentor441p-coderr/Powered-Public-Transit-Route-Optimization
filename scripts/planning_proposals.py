"""Explicit continuous service-allocation scenarios and traceable review proposals."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import uuid

import numpy as np
import pandas as pd


def allocate_service(baselines, day_type, added_bus_hours, maximum_increase=.2):
    """Minimize sum(D**2/N) under paired mean bus-hour and per-route bounds.

    This convex proxy penalizes concentrated daily boarding intensity. It is not a
    passenger assignment, occupancy, waiting-time or welfare model. No cuts are made.
    The allocation is continuous mean-daily arithmetic, not an integer timetable.
    """
    if isinstance(added_bus_hours, bool) or not math.isfinite(added_bus_hours) or added_bus_hours < 0:
        raise ValueError('Added bus-hours must be finite and nonnegative')
    if not math.isfinite(maximum_increase) or not 0 <= maximum_increase <= 1:
        raise ValueError('Maximum increase must be between zero and one')
    selected = baselines.loc[baselines.day_type.eq(day_type)].copy()
    if selected.empty or selected.bus_route.duplicated().any():
        raise ValueError('One baseline per route is required for this day type')
    excluded = selected.loc[~selected.baseline_eligible.eq(True), ['bus_route', 'baseline_status']]
    eligible = selected.loc[selected.baseline_eligible.eq(True)].copy()
    if eligible.empty:
        raise ValueError('No source-eligible baselines')
    if eligible.observation_dates_sha256.nunique() != 1:
        raise ValueError('Allocation requires identical observation-date populations')
    numbers = eligible[['mean_boardings', 'mean_departures', 'mean_bus_hours']].to_numpy(float)
    if not np.isfinite(numbers).all() or (numbers < 0).any() or (numbers[:, 1:] <= 0).any():
        raise ValueError('Invalid baseline demand or service')
    demand, original, hours = numbers.T
    costs = hours / original  # aggregate scaling coefficient, not a measured trip cycle
    upper = original * (1 + maximum_increase)
    target_hours = min(hours.sum() + added_bus_hours, float((costs * upper).sum()))
    if added_bus_hours == 0 or maximum_increase == 0 or not demand.any():
        allocation = original.copy()
    else:
        def at(multiplier):
            return np.clip(demand / np.sqrt(multiplier * costs), original, upper)
        high = 1.
        while np.dot(costs, at(high)) > target_hours:
            high *= 2
        low = 0.
        for _ in range(160):
            middle = (low + high) / 2
            if np.dot(costs, at(middle)) > target_hours:
                low = middle
            else:
                high = middle
        allocation = at(high)
    # Match the allocation's actual spend for a fair uniform-increase comparison.
    spend = max(0., float(np.dot(costs, allocation) - hours.sum()))
    uniform = original * (1 + spend / hours.sum())
    objective = lambda n: float(np.sum(demand**2 / n))
    eligible['scenario_mean_departures'] = allocation
    eligible['scenario_mean_bus_hours'] = allocation * costs
    eligible['delta_mean_departures'] = allocation - original
    eligible['delta_mean_bus_hours'] = eligible.scenario_mean_bus_hours - hours
    eligible['scenario_boardings_per_departure'] = demand / allocation
    eligible['uniform_mean_departures'] = uniform
    eligible['demand_assumption'] = 'historical paired demand held fixed'
    eligible['automatic_service_change'] = False
    eligible['timetable_feasibility'] = 'not_assessed'
    summary = {'objective': 'minimize sum of squared mean boardings divided by mean departures',
               'objective_interpretation': 'boarding-intensity concentration proxy; not occupancy or measured passenger benefit',
               'day_type': day_type, 'budget_added_bus_hours': added_bus_hours,
               'maximum_increase_fraction': maximum_increase, 'spent_added_bus_hours': spend,
               'unused_budget_bus_hours': max(0., added_bus_hours-spend),
               'eligible_routes': len(eligible), 'excluded_routes': list(excluded.bus_route),
               'baseline_objective': objective(original), 'allocation_objective': objective(allocation),
               'equal_spend_uniform_objective': objective(uniform),
               'relative_proxy_reduction': (1-objective(allocation)/objective(original)) if objective(original)>0 else None,
               'demand_response_estimated': False, 'passenger_benefit_measured': False,
               'integer_timetable_generated': False, 'automatic_service_change': False}
    if spend > added_bus_hours + 1e-8 or (allocation < original-1e-8).any() or (allocation > upper+1e-8).any():
        raise AssertionError('Allocation violates declared constraints')
    if objective(allocation) > objective(uniform) + 1e-5:
        raise AssertionError('Allocation is worse than the equal-spend feasible comparator')
    return eligible, excluded, summary


def candidate_actions(review, signals, overlaps):
    """Review candidates with evidence; overlap never becomes a merger instruction."""
    rows = []
    for record in review.itertuples():
        route_signals = signals.loc[signals.bus_route.eq(record.bus_route)]
        if record.review_state == 'source_clarification':
            action = 'Resolve schedule/demand alignment before proposing service changes'
        elif not route_signals.empty and route_signals.direction.eq('higher').any():
            action = 'Review an added-frequency alternative and collect direction/time-window load evidence'
        elif not route_signals.empty:
            action = 'Review service distribution, coverage obligations and day-type demand before any reduction'
        else:
            action = 'Retain in monitoring; no triggered planning rule'
        pairs = overlaps.loc[(overlaps.route_a.eq(record.bus_route) | overlaps.route_b.eq(record.bus_route)) & overlaps.shared_stop_ids.gt(0)]
        peer = pairs.sort_values('jaccard', ascending=False).head(1)
        corridor = 'No shared-stop corridor candidate'
        if len(peer):
            item = peer.iloc[0]
            other = item.route_b if item.route_a == record.bus_route else item.route_a
            corridor = f'Compare corridor with {other}: {int(item.shared_stop_ids)} shared stop IDs; retain exclusive coverage checks'
        rows.append({'bus_route': record.bus_route, 'review_state': record.review_state,
                     'proposed_review_action': action, 'corridor_review': corridor,
                     'evidence_summary': record.evidence_summary,
                     'baseline_period': f'{record.review_period_start} to {record.review_period_end}',
                     'merge_or_split_status': 'not_validated; requires stop order, access, passenger journeys and operational constraints',
                     'automatic_service_change': False})
    return pd.DataFrame(rows)


def route_change_candidates(overlaps, groups, minimum_jaccard=.3, minimum_shared_stops=10, minimum_patterns=3):
    """Structural hypotheses only; thresholds are declared pilot screening choices."""
    rows = []
    for pair in overlaps.loc[overlaps.jaccard.ge(minimum_jaccard) & overlaps.shared_stop_ids.ge(minimum_shared_stops)].itertuples():
        rows.append({'candidate_type':'corridor_coordination_or_merge_review','route':pair.route_a,'peer':pair.route_b,
                     'reason':f'{pair.shared_stop_ids} shared stop IDs; Jaccard {pair.jaccard:.3f}; {pair.a_only_stop_ids}/{pair.b_only_stop_ids} exclusive stop IDs',
                     'snapshot_id':pair.snapshot_id,
                     'required_validation':'Compare stop order, direction/time compatibility, walking access, exclusive coverage, passenger journeys and fleet feasibility',
                     'recommendation_status':'hypothesis_for_review; not an approved route change'})
    for group in groups.loc[groups.stop_patterns.ge(minimum_patterns)].itertuples():
        rows.append({'candidate_type':'branch_or_short_turn_split_review','route':group.bus_route,'peer':'',
                     'reason':f'{group.stop_patterns} distinct scheduled stop patterns; variants may be necessary short-turns, not inefficiency',
                     'snapshot_id':group.snapshot_id,
                     'required_validation':'Determine variant purposes and direction/time-specific demand; preserve through journeys, transfers and coverage before designing a split',
                     'recommendation_status':'hypothesis_for_review; not an approved route change'})
    return pd.DataFrame(rows,columns=['candidate_type','route','peer','reason','snapshot_id','required_validation','recommendation_status'])


def save_proposal(folder, title, metadata, tables):
    """Append-only local proposal bundle. No source, model or schedule is replaced."""
    title = str(title).strip()
    if not title or len(title) > 160:
        raise ValueError('Enter a proposal title of 1–160 characters')
    identifier = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:12]
    destination = Path(folder) / identifier
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, frame in tables.items():
        if not name.replace('_', '').isalnum():
            raise ValueError('Invalid proposal table name')
        output = destination / (name+'.csv')
        frame.to_csv(output, index=False)
        hashes[output.name] = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {'id': identifier, 'title': title, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'scope': 'planning_review_proposal', 'automatic_service_change': False,
                'timetable_feasibility': 'not_assessed', 'assumptions': metadata, 'tables': hashes}
    (destination/'proposal.json').write_text(json.dumps(manifest, indent=2, default=str), encoding='utf-8')
    return identifier


def load_proposals(folder):
    rows = []
    for file in sorted(Path(folder).glob('*/proposal.json'), reverse=True):
        try:
            record = json.loads(file.read_text(encoding='utf-8'))
            if (record['id'] != file.parent.name or not isinstance(record['tables'],dict)
                    or record['automatic_service_change'] is not False):
                raise ValueError('Invalid saved proposal metadata')
            for field in ['title','created_utc','timetable_feasibility','assumptions']:
                if field not in record: raise ValueError('Incomplete saved proposal')
        except (OSError,ValueError,KeyError,TypeError):
            rows.append({'id':file.parent.name,'title':'Unreadable proposal','created_utc':'unavailable',
                         'timetable_feasibility':'not_assessed','integrity_valid':False})
            continue
        valid = True
        for name, expected in record['tables'].items():
            if Path(name).name != name or not (file.parent/name).is_file() or hashlib.sha256((file.parent/name).read_bytes()).hexdigest() != expected:
                valid = False
        rows.append({**record, 'integrity_valid': valid})
    return rows
