"""Planner-facing pages; calculations use the established analysis products."""
from datetime import datetime, timedelta, timezone
import json

import altair as alt
import pandas as pd
import streamlit as st

from dashboard import charts
from dashboard.data import (ROOT, DAY_TYPES, STATES, DataUnavailable, catalog, checked_bytes,
                            csv_bytes, document, filtered_history, generate_preview, history_summary,
                            inventory, load_preview, peer_overlaps, preview_age, preview_list,
                            route_paths, scenario_export, table)
from scripts.service_scenarios import compare_frequency, transfer_bus_hours

WINDOW = "6 July–27 September 2026"
MODEL_NAMES = {"seasonal_mean4": "Seasonal reference", "anchored_ratio_15": "Anchored challenger"}


def metric(columns, values):
    for column, (label, value, help_text) in zip(columns, values):
        column.metric(label, value, help=help_text, border=True)


def number(value, precision=0):
    return "Unavailable" if pd.isna(value) else f"{value:,.{precision}f}"


def export(frame, filename, label="Download table", key=None):
    st.download_button(label, csv_bytes(frame), file_name=filename, mime="text/csv", key=key)


def period_note():
    st.caption(f"Historical review · {WINDOW} · 78 shared eligible dates · both directions combined")


def route_context(route):
    row = table("review").set_index("bus_route").loc[route]
    st.caption(f"{route} · {row.route_long_name}")
    if row.review_state == "source_clarification":
        st.warning("Source clarification required: published boardings occur on four dates with zero matched scheduled service. Scenario projections are withheld for this route.")
    return row


def overview(route):
    st.markdown('<div class="hero"><div class="eyebrow">MANHATTAN · BUS NETWORK PLANNING</div>'
                '<h1>Understand service.<br>Explore the alternatives.</h1>'
                '<p>Published demand, historically matched schedules, and transparent planning evidence.</p></div>',
                unsafe_allow_html=True)
    period_note()
    reviews, members = table("review"), table("members")
    metric(st.columns(4), [
        ("Routes in study", str(len(reviews)), "Fixed Manhattan cohort, not the entire New York network."),
        ("Shared observation days", str(members.payment_date.nunique()), "Every route uses these same eligible dates."),
        ("Planning review", str(reviews.review_state.eq("planning_review").sum()), "Rules flag evidence for investigation, not an instruction to change service."),
        ("Source clarification", str(reviews.review_state.eq("source_clarification").sum()), "Source issues take precedence over planning signals.")])
    left, right = st.columns([1.7, 1])
    with left:
        st.subheader("Demand across the study network")
        observed = members.groupby("payment_date", as_index=False).analysis_boardings.sum(min_count=1)
        # Insert gaps for excluded dates so chart lines do not imply observations there.
        observed = observed.set_index("payment_date").reindex(pd.date_range(observed.payment_date.min(), observed.payment_date.max())).rename_axis("payment_date").reset_index()
        charts.line(observed, "payment_date", "analysis_boardings", "Published daily boardings")
        st.caption("Boardings count passenger entries, not unique people. Blank dates were excluded from the common-date comparison.")
    with right:
        st.subheader("Review workflow")
        st.markdown("**01 · Inspect** demand and the matching service dates.\n\n"
                    "**02 · Review** reasons, sample sizes, and source issues.\n\n"
                    "**03 · Compare** explicit frequency and bus-hour assumptions.")
        st.info("This workspace supports historical planning. Occupancy, actual delays, and operational benefits are not observed in these inputs.")
    st.subheader("Route review register")
    st.caption("Workflow order puts source issues first; routes are not ranked by an efficiency score.")
    display = reviews[["bus_route", "route_long_name", "review_state", "evidence_summary"]].copy()
    display.review_state = display.review_state.map(STATES)
    st.dataframe(display, hide_index=True, width="stretch", column_config={
        "bus_route": "Route", "route_long_name": "Corridor", "review_state": "Review status", "evidence_summary": "Reason"})
    export(reviews, "route_review_register.csv")


def explorer(route):
    st.title("Route explorer")
    context = route_context(route)
    daily = table("daily")
    a, b = st.columns([1, 1.5])
    with a:
        dates = st.date_input("Observation dates", value=(pd.Timestamp("2026-07-06").date(), pd.Timestamp("2026-09-27").date()),
                              min_value=daily.payment_date.min().date(), max_value=daily.payment_date.max().date(), key="explore_dates")
    with b:
        kinds = st.multiselect("Day types", DAY_TYPES, default=DAY_TYPES, key="explore_day_types")
    if not isinstance(dates, (tuple, list)) or len(dates) != 2:
        st.info("Choose both a start and an end date.")
        return
    selected = filtered_history(daily, route, dates[0], dates[1], kinds)
    if selected.empty:
        st.info("No observations match these date and day-type filters.")
        return
    summary = history_summary(selected)
    metric(st.columns(4), [
        ("Observed demand days", str(summary["observed_days"]), "Nonmissing quality-screened demand observations."),
        ("Mean daily boardings", number(summary["mean_boardings"]), "Mean across the selected nonmissing demand dates."),
        ("Comparable service days", str(summary["paired_days"]), "Only exact-date, quality-eligible demand/service comparisons."),
        ("Boardings / bus-hour", number(summary["boardings_per_bus_hour"], 1), "Sum of boardings divided by sum of scheduled hours on the same eligible dates; not occupancy.")])
    if summary["paired_days"] < len(selected):
        st.info(f"{len(selected) - summary['paired_days']} selected route/dates are unavailable for a positive-service comparison. Missing schedules are not treated as zero.")
    demand_tab, map_tab, profile_tab = st.tabs(["Demand & service", "Route geometry", "Peer context"])
    with demand_tab:
        st.subheader("Daily demand")
        charts.line(selected, "payment_date", "analysis_boardings", "Published boardings")
        service = selected[["payment_date", "scheduled_departures", "comparison_eligible"]].copy()
        service["scheduled_departures"] = service.scheduled_departures.where(service.comparison_eligible.eq(True))
        st.subheader("Matched scheduled departures")
        charts.line(service, "payment_date", "scheduled_departures", "Scheduled departures")
        st.caption("Scheduled departures are trip starts on the clock date. Timetable times do not measure actual bus arrivals.")
        hourly = table("hourly")
        hourly = filtered_history(hourly, route, dates[0], dates[1], kinds)
        st.subheader("Time-of-day demand")
        if hourly.empty:
            st.info("Hourly observations are available only for July–September 2026.")
        else:
            profile = hourly.groupby("hour", as_index=False).agg(mean_boardings=("analysis_boardings", "mean"),
                                                                observed_hours=("analysis_boardings", "count"))
            charts.bar(profile, "hour", "mean_boardings", "Local clock hour", "Mean boardings per observed hour")
            st.caption(f"New York local time · {hourly.payment_date.nunique()} dates in the hourly window. Each hour uses its available observations.")
            with st.expander("Hourly sample sizes"):
                st.dataframe(profile, hide_index=True, width="stretch")
        with st.expander("Selected observations and source coverage"):
            columns = ["payment_date", "bus_route", "day_type", "published_boardings", "analysis_boardings",
                       "scheduled_departures", "scheduled_service_hours", "comparison_eligible", "source_snapshot", "prior_source_snapshot"]
            st.dataframe(selected[columns], hide_index=True, width="stretch")
        export(selected, f"{route}_observations_{dates[0]}_{dates[1]}.csv", "Download selected observations")
    with map_tab:
        st.subheader("Published route variants")
        st.caption("This map is a fixed geometry snapshot and does not change with the observation-date filter.")
        paths = route_paths(route)
        charts.route_map(paths)
        metric(st.columns(3), [("Shape variants", str(len(paths)), "Published geometry variants in the selected snapshot."),
                              ("Served stop IDs", number(context.served_stop_ids), "Distinct stop identifiers in the snapshot."),
                              ("Exclusive stop IDs", number(context.exclusive_stop_ids), "Stop IDs served by this route only within this 41-route cohort.")])
        with st.expander("Map geometry as coordinates"):
            coordinates = pd.DataFrame([{"shape_id": item["shape"], "point": i, "longitude": p[0], "latitude": p[1]}
                                        for item in paths for i, p in enumerate(item["path"], 1)])
            st.dataframe(coordinates, hide_index=True, width="stretch", height=200)
            export(coordinates, f"{route}_geometry.csv")
    with profile_tab:
        st.subheader("Shared-stop corridors")
        peers = peer_overlaps(route)
        st.dataframe(peers[["peer", "shared_stop_ids", "jaccard", "selected_route_only_stops", "peer_only_stops"]].head(12),
                     hide_index=True, width="stretch")
        st.caption("Shared stop IDs indicate common corridors. They do not show interchangeable passenger journeys or justify merging routes.")
        export(peers, f"{route}_overlap_context.csv")
        group = table("groups").set_index("bus_route").loc[route]
        st.subheader(f"Exploratory profile · {group.group_id}")
        st.write(group.group_description)
        st.warning("Group membership is sensitive to scaling and feature choices. These groups are descriptive context, not established route types or performance classes.")
        with st.expander("Grouping stability"):
            st.write(f"Week-resample membership retention: {group.bootstrap_retention:.1%}. This is not a probability that the route belongs to a true class.")
            st.dataframe(table("group_sensitivity"), hide_index=True, width="stretch")


def forecasts(route):
    st.title("Demand forecasts")
    route_context(route)
    st.warning("Experimental daily boarding forecasts. Prospective acceptance is pending; no forecast is approved for operational service decisions.")
    preview_tab, evaluation_tab = st.tabs(["Issued previews", "Historical evaluation"])
    with preview_tab:
        items, rejected = preview_list()
        if rejected:
            st.warning(f"{len(rejected)} unreadable preview record(s) were excluded.")
        mode = st.selectbox("Forecast method", ["reference", "challenger"],
                            format_func=lambda x: "Seasonal reference · default" if x == "reference" else "Anchored challenger · experimental", key="forecast_mode")
        options = [m for m in items if m["preview_mode"] == mode]
        labels = {m["id"]: f"Issued {m['generated_utc'][:16].replace('T', ' ')} UTC · {m['first_target']} to {m['last_target']}" for m in options}
        new_preview = st.session_state.pop("new_preview", None)
        if new_preview in labels:
            st.session_state[f"preview_{mode}"] = new_preview
            st.success("New seven-day preview saved and selected below.")
        if options:
            selected = st.selectbox("Issued forecast", list(labels), format_func=labels.get, key=f"preview_{mode}")
            try:
                meta, all_points, all_ranges = load_preview(selected)
                points = all_points.loc[all_points.bus_route.eq(route)]
                ranges = all_ranges.loc[all_ranges.bus_route.eq(route)] if len(all_ranges) else all_ranges
                st.subheader(preview_age(meta))
                st.caption(f"Source observed {meta['source_observed_utc'][:10]} · history cutoff {meta['maturity_cutoff']} · issued {meta['generated_utc'][:16].replace('T', ' ')} UTC")
                levels = meta["range_levels_available"]
                level = st.selectbox("Empirical range", levels, format_func=lambda x: f"{x:.0%} nominal range", key="forecast_level") if levels else None
                if not levels:
                    st.info("Ranges are withheld for the challenger because historical coverage did not meet the declared screen.")
                charts.preview_chart(points, ranges, level)
                if levels:
                    st.caption("The shaded band is an empirical experimental range. Historical coverage is reported in the evaluation tab; future coverage is not guaranteed.")
                display = points[["payment_date", "prediction"]].copy()
                if level is not None:
                    display = display.merge(ranges.loc[ranges.level.eq(level), ["payment_date", "lower", "upper"]], on="payment_date", validate="one_to_one")
                st.dataframe(display, hide_index=True, width="stretch", column_config={
                    "payment_date": st.column_config.DateColumn("Target date", format="DD MMM YYYY"),
                    "prediction": st.column_config.NumberColumn("Daily boardings estimate", format="%.1f"),
                    "lower": st.column_config.NumberColumn("Lower bound", format="%.1f"),
                    "upper": st.column_config.NumberColumn("Upper bound", format="%.1f")})
                export(points, f"{route}_{selected}_forecast.csv", "Download route forecast")
                st.download_button("Download forecast provenance", json.dumps(meta, indent=2), file_name=f"{selected}_provenance.json", mime="application/json")
            except DataUnavailable as exc:
                st.error(str(exc))
        else:
            st.info("No issued previews are available for this method. Generate a preview from a validated source below.")
        with st.expander("Generate a new experimental preview"):
            st.write("Uses the last validated observation snapshot and its maturity cutoff. Stale or incomplete history blocks generation. Each run creates a separate dated preview and preserves previous results.")
            today = datetime.now(timezone.utc).date()
            with st.form("generate_forecast"):
                start = st.date_input("First target date (UTC)", today + timedelta(days=1), min_value=today + timedelta(days=1), max_value=today + timedelta(days=7))
                submit = st.form_submit_button("Generate seven-day preview")
            if submit:
                try:
                    with st.spinner("Checking source history and generating the seven-day preview…"):
                        identifier = generate_preview(mode, start)
                    st.session_state["new_preview"] = identifier
                    st.rerun()
                except (DataUnavailable, ValueError) as exc:
                    st.error(str(exc))
            if st.button("Refresh previews"):
                st.rerun()
    with evaluation_tab:
        st.subheader("Additional October assessment")
        st.caption("1–4 and 12–21 October 2026 · 14 dates · 574 route/date targets across 41 routes · previously scored 5–11 October excluded")
        scores = table("forecast_scores")
        scores = scores.loc[scores.model.isin(MODEL_NAMES)].copy()
        st.dataframe(scores[["model", "rows", "routes", "mae", "rmse", "wape", "bias"]], hide_index=True, width="stretch",
                     column_config={"mae": st.column_config.NumberColumn("MAE · boardings", format="%.2f"),
                                    "wape": st.column_config.NumberColumn("WAPE · fraction", format="%.4f"),
                                    "bias": st.column_config.NumberColumn("Mean error · boardings", format="%.2f")})
        st.caption("The challenger was selected using an earlier March–April window. These are retrospective comparisons; publication-vintage and prospective checks remain outstanding.")
        predictions = table("forecast_predictions")
        selected = predictions.loc[predictions.bus_route.eq(route) & predictions.model.isin(MODEL_NAMES)].copy()
        actual = selected.drop_duplicates("payment_date")[["payment_date", "actual"]].rename(columns={"actual": "boardings"})
        actual["series"] = "Published outcome"
        predicted = selected.rename(columns={"prediction": "boardings"})
        predicted["series"] = predicted.model.map(MODEL_NAMES)
        charts.line(pd.concat([actual, predicted[["payment_date", "boardings", "series"]]]), "payment_date", "boardings", "Daily boardings", "series")
        export(selected, f"{route}_historical_forecast_evaluation.csv")
        st.subheader("Empirical range coverage")
        coverage = table("forecast_coverage")
        st.dataframe(coverage.loc[coverage.model.isin(MODEL_NAMES)], hide_index=True, width="stretch")
        st.caption("Coverage is the observed fraction inside each nominal range. Reference 80% / 90% ranges covered 75.96% / 87.11%; challenger 74.22% / 84.49%, so challenger ranges are withheld.")


def review(route):
    st.title("Planning review")
    period_note()
    reviews = table("review")
    statuses = st.multiselect("Review states", list(STATES), default=["source_clarification", "planning_review"], format_func=STATES.get)
    selected = reviews.loc[reviews.review_state.isin(statuses)]
    st.dataframe(selected[["bus_route", "route_long_name", "review_state", "evidence_summary"]], hide_index=True, width="stretch")
    st.caption(f"{len(selected)} routes in this view. Source issues take precedence; no-rule routes are not labelled balanced or efficient.")
    export(selected, "filtered_review_queue.csv", "Download filtered queue")
    st.divider()
    st.subheader(f"Evidence for {route}")
    context = route_context(route)
    st.write(f"**{STATES[context.review_state]}** · {context.evidence_summary}")
    signals = table("signals")
    signals = signals.loc[signals.bus_route.eq(route)]
    issues = table("source_issues")
    issues = issues.loc[issues.bus_route.eq(route)]
    if len(issues):
        st.dataframe(issues, hide_index=True, width="stretch")
        export(issues, f"{route}_source_issues.csv")
    if signals.empty:
        st.info("No triggered planning signals for this route under the declared rules.")
    for signal in signals.itertuples():
        with st.container(border=True):
            st.markdown(f"**{signal.day_type} · {signal.family.replace('_', ' ').title()} · {signal.direction}**")
            st.write(signal.reason)
            st.caption(f"{signal.first_date} to {signal.last_date} · {int(signal.sample_dates)} sample dates · evidence {signal.evidence_id}")
            st.write(f"Week-resample retention: **{signal.bootstrap_retention:.0%}** · threshold sensitivity retention: **{signal.threshold_retention:.0%}**")
            if signal.bootstrap_retention < .8:
                st.warning("This signal is sensitive to which weeks are sampled.")
    with st.expander("All rule evaluations, including unavailable results"):
        rules = table("rules")
        rules = rules.loc[rules.bus_route.eq(route)]
        st.dataframe(rules, hide_index=True, width="stretch")
        export(rules, f"{route}_rule_evaluations.csv")
    with st.expander("Rules and sensitivity"):
        st.markdown("- Relative use: lower/upper 10% tails within each day type.\n"
                    "- Weekend contrast: outside 0.8–1.25 of the route's weekday boarding/service rate.\n"
                    "- Temporal contrast: compare the first and last six weeks using the same ratio limits.\n"
                    "- Minimum samples: 40 weekday dates and eight dates per weekend day type.")
        st.caption("Retention measures repeatability under resampling or threshold changes, not a probability that service should change. Cluster memberships and forecast errors are not score inputs.")
        st.dataframe(table("review_sensitivity"), hide_index=True, width="stretch")


def scenario_status(status):
    messages = {
        "within_declared_arithmetic_limits": ("success", "Within the declared arithmetic limits"),
        "within_stated_transfer_limits": ("success", "Within the stated transfer limits"),
        "within_retention_limit_budget_unspecified": ("info", "Retention limit satisfied; added-hours budget unspecified"),
        "exceeds_added_hours_limit": ("warning", "Exceeds the added scheduled bus-hours limit"),
        "below_retained_service_limit": ("warning", "Below the minimum retained-service limit"),
        "withheld": ("warning", "Projection withheld: baseline needs source clarification or more evidence")}
    kind, message = messages[status]
    getattr(st, kind)(message + ". Timetable and fleet feasibility are unassessed.")


def scenarios(route):
    st.title("Service scenarios")
    period_note()
    route_context(route)
    manifest = document("scenario_manifest")
    for name, expected in manifest["source_code"].items():
        checked_bytes(ROOT / name, expected)
    baselines = table("baselines")
    st.info("Explore mean-daily service arithmetic using the historical baseline. Frequency scales departures and scheduled bus-hours together; demand changes are independent assumptions. No timetable or service change is applied.")
    kind = st.selectbox("Scenario day type", DAY_TYPES, key="scenario_day_type")
    baseline = baselines.loc[baselines.bus_route.eq(route) & baselines.day_type.eq(kind)]
    row = baseline.iloc[0]
    metric(st.columns(4), [("Baseline dates", number(row.observed_dates), "All means use the same exact observation dates."),
                          ("Mean daily boardings", number(row.mean_boardings), "Historical published boarding observations."),
                          ("Mean departures", number(row.mean_departures, 2), "Daily averages may be fractional; this is not a timetable."),
                          ("Scheduled bus-hours", number(row.mean_bus_hours, 2), "Clock-date service exposure, not a vehicle cycle or fleet count.")])
    st.caption(f"{row.first_date:%d %b %Y}–{row.last_date:%d %b %Y} · baseline status: {row.baseline_status}")
    frequency_tab, transfer_tab = st.tabs(["Frequency alternative", "Transfer bus-hours"])
    with frequency_tab:
        a, b = st.columns(2)
        with a:
            frequency = st.slider("Departure change (%)", -50, 100, 10, 5, key="frequency_change")
            demand = st.slider("Independent demand change (%)", -50, 50, 0, 5, key="demand_change")
        with b:
            floor = st.slider("Minimum retained service (%)", 0, 100, 80, 5, key="retained_floor")
            has_budget = st.checkbox("Specify an added bus-hours limit", value=True, key="has_budget")
            budget = st.number_input("Maximum added bus-hours per day", min_value=0., max_value=1000., value=10., step=1., disabled=not has_budget)
        result = compare_frequency(baseline, 1 + frequency / 100, 1 + demand / 100,
                                   budget if has_budget else None, floor / 100)
        current = result.iloc[0]
        scenario_status(current.arithmetic_status)
        if bool(row.baseline_eligible):
            comparison = pd.DataFrame({"Measure": ["Mean daily departures", "Scheduled bus-hours per day", "Mean daily boardings", "Boardings per departure", "Boardings per bus-hour"],
                                       "Baseline": [row.mean_departures, row.mean_bus_hours, row.mean_boardings, row.boardings_per_departure, row.boardings_per_bus_hour],
                                       "Scenario": [current.scenario_mean_departures, current.scenario_mean_bus_hours, current.scenario_mean_boardings,
                                                    current.scenario_boardings_per_departure, current.scenario_boardings_per_bus_hour]})
            comparison["Change"] = comparison.Scenario - comparison.Baseline
            st.dataframe(comparison, hide_index=True, width="stretch", column_config={c: st.column_config.NumberColumn(c, format="%.2f") for c in ["Baseline", "Scenario", "Change"]})
            cases = pd.concat([compare_frequency(baseline, f, 1 + demand / 100,
                                               budget if has_budget else None, floor / 100).assign(change_pct=(f-1)*100)
                               for f in [.5, .75, .8, .9, 1., 1.1, 1.2, 1.5, 2.]], ignore_index=True)
            chart = alt.Chart(cases).mark_line(color=charts.TEAL, point=True).encode(
                x=alt.X("change_pct:Q", title="Departure change (%)"),
                y=alt.Y("delta_mean_bus_hours:Q", title="Added scheduled bus-hours / day"),
                tooltip=["change_pct:Q", alt.Tooltip("delta_mean_bus_hours:Q", format=".2f"), "arithmetic_status:N"])
            if has_budget:
                chart += alt.Chart(pd.DataFrame({"limit": [budget]})).mark_rule(color=charts.ORANGE, strokeDash=[5, 4]).encode(y="limit:Q")
            st.altair_chart(chart.properties(height=260), width="stretch")
            st.caption("Separate alternatives, not one combined plan. A lower boarding/service ratio does not demonstrate reduced crowding. Cuts may harm access despite meeting the arithmetic floor.")
        st.download_button("Download scenario with assumptions", scenario_export(result, {
            "route": route, "day_type": kind, "frequency_factor": 1 + frequency / 100,
            "independent_demand_factor": 1 + demand / 100, "max_added_bus_hours": budget if has_budget else None,
            "minimum_retained_fraction": floor / 100}), file_name=f"{route}_{kind}_frequency_scenario.zip", mime="application/zip")
    with transfer_tab:
        st.write("Use the selected route as the donor. Transfers conserve paired scheduled bus-hours; they do not establish that vehicles, staff, or passenger journeys can be reassigned.")
        if not bool(row.baseline_eligible):
            st.warning("Transfers are unavailable for this source-withheld baseline.")
        else:
            recipients = sorted(baselines.loc[baselines.day_type.eq(kind) & baselines.baseline_eligible.eq(True) & baselines.bus_route.ne(route), "bus_route"])
            peer = st.selectbox("Receiving route", recipients, index=recipients.index("M34A+") if "M34A+" in recipients else 0)
            max_hours = max(0., float(row.mean_bus_hours) - .01)
            hours = st.number_input("Bus-hours transferred per day", min_value=0., max_value=max_hours, value=min(5., max_hours), step=1., key=f"transfer_hours_{route}_{kind}")
            retained = st.slider("Transfer minimum retained service (%)", 0, 100, 80, 5)
            transfer, summary = transfer_bus_hours(baselines, route, peer, kind, hours, retained / 100)
            scenario_status(summary["arithmetic_status"])
            metric(st.columns(3), [("Combined baseline hours", number(summary["baseline_total_mean_bus_hours"], 2), "Sum of both routes' paired daily means."),
                                  ("Combined scenario hours", number(summary["scenario_total_mean_bus_hours"], 2), "Equal-hour accounting; operational feasibility not assessed."),
                                  ("Net departure change", number(summary["net_mean_departures_change"], 2), "Equal bus-hours need not mean equal departure counts.")])
            st.dataframe(transfer[["bus_route", "transfer_role", "mean_departures", "scenario_mean_departures", "mean_bus_hours", "scenario_mean_bus_hours", "arithmetic_status"]], hide_index=True, width="stretch")
            peers = peer_overlaps(route)
            context = peers.loc[peers.peer.eq(peer), ["peer", "shared_stop_ids", "selected_route_only_stops", "peer_only_stops", "jaccard", "snapshot_id"]]
            st.caption("Corridor context · fixed September geometry; shared stops do not prove safe interchangeability.")
            st.dataframe(context, hide_index=True, width="stretch")
            st.download_button("Download transfer with assumptions", scenario_export(transfer, {
                **summary, "minimum_retained_fraction": retained / 100, "demand_assumption": "Each route's historical demand held fixed"},
                {"corridor_context": context}), file_name=f"{route}_to_{peer}_{kind}_transfer.zip", mime="application/zip")


def coverage(route):
    st.title("Data coverage")
    st.write("Source windows, matching decisions, and the evidence available for planning.")
    dates = table("date_coverage")
    daily = table("daily")
    matched = daily.loc[daily.comparison_eligible.eq(True)]
    metric(st.columns(4), [("Study routes", str(daily.bus_route.nunique()), "Exact route identifiers, both directions combined."),
                          ("Matched route/dates", number(len(matched)), "Eligible positive-service daily comparisons."),
                          ("Matched calendar dates", number(matched.payment_date.nunique()), "Dates with at least one eligible route comparison."),
                          ("Historical archives", str(table("crosswalk").snapshot_id.nunique()), "Manhattan dated schedule captures used for historical matching.")])
    st.subheader("Observation windows")
    st.dataframe(pd.DataFrame([
        {"Source": "Published daily boardings", "Window": "1 Jan 2025–30 Sep 2026", "Use": "History and retrospective model development"},
        {"Source": "Published hourly boardings", "Window": "1 Jul–30 Sep 2026", "Use": "Time-of-day patterns; not occupancy"},
        {"Source": "Later observation capture", "Window": "Captured 5 Nov; through 27 Oct 2026", "Use": "Forecast evaluation; maturity cutoff 21 Oct"},
        {"Source": "Common historical review", "Window": WINDOW, "Use": "78 of 84 dates shared by all 41 routes"},
        {"Source": "Map geometry", "Window": "3 Sep 2026 capture", "Use": "Fixed route shapes and stop overlap"}]), hide_index=True, width="stretch")
    st.subheader("Common-date coverage")
    excluded = dates.loc[~dates.included.eq(True)]
    st.write(f"{dates.included.eq(True).sum()} included dates; {len(excluded)} excluded. Common dates keep route comparisons on the same observation population.")
    st.dataframe(excluded, hide_index=True, width="stretch")
    export(dates, "common_date_coverage.csv")
    with st.expander("Service coverage over the full history"):
        counts = daily.groupby("payment_date", as_index=False).agg(demand_routes=("analysis_boardings", "count"),
                                                                    comparable_routes=("comparison_eligible", "sum"))
        plot = counts.melt("payment_date", var_name="series", value_name="routes")
        charts.line(plot, "payment_date", "routes", "Routes with available evidence", "series")
        st.write("Schedules use the latest whole archived capture on each date, calendar exceptions, exact route IDs, and clock-date service exposure. Archive gaps, partial calendars, and DST or block-overlap contexts can withhold comparisons.")
    st.subheader("What this evidence supports")
    st.dataframe(pd.DataFrame([
        {"Capability": "Demand and scheduled service", "Evidence": "Published boarding estimates; aligned schedule-derived service"},
        {"Capability": "Forecasting", "Evidence": "Retrospective daily demand experiments; prospective acceptance pending"},
        {"Capability": "Frequency scenarios", "Evidence": "Mean-daily arithmetic under explicit, independent assumptions"},
        {"Capability": "Crowding or capacity", "Evidence": "Unavailable: no observed on-board loads or capacity labels"},
        {"Capability": "Reliability or actual delays", "Evidence": "Unavailable: no tracked actual arrival observations"},
        {"Capability": "Operational rerouting or optimization", "Evidence": "Requires road constraints, journey demand, fleet/staff feasibility and evaluation"}]), hide_index=True, width="stretch")
    st.subheader("Public sources")
    st.markdown("[MTA hourly ridership](https://data.ny.gov/Transportation/MTA-Bus-Hourly-Ridership-Beginning-2025/gxb3-akrn) · "
                "[MTA developer feeds](https://www.mta.info/developers) · "
                "[Manhattan archive catalogue](https://mobilitydatabase.org/feeds/gtfs/mdb-513)")
    with st.expander("Local data release and integrity"):
        st.caption("Loaded artifacts are checked against their recorded fingerprints. Missing or changed files block the affected view.")
        if st.button("Verify all dashboard inputs"):
            with st.spinner("Verifying local files…"):
                audit = inventory()
            st.dataframe(audit, hide_index=True, width="stretch")
            if audit.status.eq("verified").all():
                st.success(f"All {len(audit)} dashboard inputs match this release.")
            else:
                st.error("Some artifacts are missing or changed. Restore the validated bundle before using affected views.")
            export(audit, "dashboard_input_integrity.csv")
        st.download_button("Download data release manifest", json.dumps(catalog(), indent=2), file_name="dashboard_data_manifest.json", mime="application/json")


PAGES = {"Overview": overview, "Route explorer": explorer, "Demand forecasts": forecasts,
         "Planning review": review, "Service scenarios": scenarios, "Data coverage": coverage}
