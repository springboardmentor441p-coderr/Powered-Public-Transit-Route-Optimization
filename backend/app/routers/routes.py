"""Route list, route detail, route forecast, and route group endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.data import clean_records
from backend.app.schemas import (
    GenericTableResponse,
    GroupsResponse,
    RouteDetailResponse,
    RouteForecastResponse,
)

router = APIRouter(prefix="/api", tags=["routes"])


@router.get("/routes", response_model=GenericTableResponse)
def list_routes(
    request: Request,
    group_id: int | None = Query(default=None),
    service_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> GenericTableResponse:
    store = request.app.state.store
    df = store.routes_summary.copy()
    if group_id is not None:
        df = df[df["group_id"] == group_id]
    if service_type is not None:
        df = df[df["service_type"] == service_type]
    if search:
        q = search.strip().lower()
        df = df[
            df["route"].str.lower().str.contains(q, na=False)
            | df["route_long_name"].str.lower().str.contains(q, na=False)
        ]

    return GenericTableResponse(
        period="Spring 2026 GTFS (2026-04-09) & Jan–May / Jan–Sep 2026 Typical Ridership",
        source="app_data/routes_summary.csv (GTFS profiles, stop exclusivity & K-Means k=3 + M35 outlier)",
        count=len(df),
        rows=clean_records(df),
    )


@router.get("/routes/{route}", response_model=RouteDetailResponse)
def get_route_detail(request: Request, route: str) -> RouteDetailResponse:
    store = request.app.state.store
    if route not in store.valid_routes:
        raise HTTPException(status_code=404, detail=f"Route '{route}' not found in the 41 Manhattan study routes.")

    prof = clean_records(store.routes_summary[store.routes_summary["route"] == route])[0]
    thresholds = clean_records(store.route_thresholds[store.route_thresholds["route"] == route])
    hourly_patterns = clean_records(
        store.route_hourly_pattern[store.route_hourly_pattern["route"] == route]
    )
    tb_perf = clean_records(
        store.route_time_band_performance[store.route_time_band_performance["route"] == route]
    )
    review_cells = clean_records(store.review_list[store.review_list["route"] == route])

    ovr_df = store.route_overlap_pairs[
        (store.route_overlap_pairs["route_1"] == route)
        | (store.route_overlap_pairs["route_2"] == route)
    ].sort_values("overlap_share", ascending=False)
    overlaps = []
    for row in clean_records(ovr_df):
        partner = row["route_2"] if row["route_1"] == route else row["route_1"]
        overlaps.append({**row, "partner_route": partner})

    geometry = store.route_geometries.get("routes", {}).get(route)
    return RouteDetailResponse(
        period="Jan–Sep 2026 Typical Ridership, Spring 2026-04-09 GTFS & Aug–Oct 2026 Review Window",
        source="app_data/routes_summary.csv, route_hourly_pattern.csv, route_overlap_pairs.csv, review_list.csv & route_geometries.json",
        route=route,
        profile=prof,
        thresholds=thresholds,
        hourly_patterns=hourly_patterns,
        time_band_performance=tb_perf,
        review_cells=review_cells,
        overlaps=overlaps,
        geometry=geometry,
    )


@router.get("/routes/{route}/forecast", response_model=RouteForecastResponse)
def get_route_forecast(request: Request, route: str) -> RouteForecastResponse:
    store = request.app.state.store
    if route not in store.valid_routes:
        raise HTTPException(status_code=404, detail=f"Route '{route}' not found in the 41 Manhattan study routes.")

    val_hgb = clean_records(
        store.val_forecast_by_route_hgb[store.val_forecast_by_route_hgb["route"] == route]
    )
    val_4wk = clean_records(
        store.val_forecast_by_route_4wk[store.val_forecast_by_route_4wk["route"] == route]
    )
    test_f = clean_records(
        store.test_forecast_by_route[store.test_forecast_by_route["route"] == route]
    )
    test_clf_off = clean_records(
        store.test_classification_by_route_official[
            store.test_classification_by_route_official["route"] == route
        ]
    )
    test_clf_rb = clean_records(
        store.test_classification_by_route_rule_b[
            store.test_classification_by_route_rule_b["route"] == route
        ]
    )
    oct_route_rows = clean_records(
        store.october_forecast_by_route[store.october_forecast_by_route["route"] == route]
    )

    oct_hr_df = store.october_hourly_forecast_vs_actual[
        store.october_hourly_forecast_vs_actual["route"] == route
    ].sort_values(["date", "hour"])

    oct_daily_df = (
        oct_hr_df.groupby(["date", "day_of_week", "day_type", "day_group"], as_index=False)
        .agg(
            active_hours=("hour", "count"),
            actual_ridership=("actual_ridership", "sum"),
            pred_ridership=("pred_ridership", "sum"),
            baseline_4wk_ridership=("lag_mean_available", "sum"),
            actual_high_hours=("actual_high_demand_per_trip", "sum"),
            pred_high_hours=("pred_high_demand_per_trip", "sum"),
        )
        .sort_values("date")
    )
    oct_daily_df["pred_ridership"] = oct_daily_df["pred_ridership"].round(1)
    oct_daily_df["baseline_4wk_ridership"] = oct_daily_df["baseline_4wk_ridership"].round(1)

    return RouteForecastResponse(
        period="Validation: Jun–Jul 2026 | Test: Aug–Sep 2026 | Operational Check: Oct 18–31, 2026",
        source="app_data/test_forecast_by_route.csv, october_forecast_by_route.csv & october_hourly_forecast_vs_actual.parquet",
        route=route,
        validation_summary={
            "hgb": val_hgb[0] if val_hgb else None,
            "baseline_4wk": val_4wk[0] if val_4wk else None,
        },
        test_summary={
            "subsets": test_f,
            "primary": test_f[0] if test_f else None,
        },
        test_classification=test_clf_off + test_clf_rb,
        october_summary=oct_route_rows[0] if oct_route_rows else None,
        october_daily=clean_records(oct_daily_df),
        october_hourly=clean_records(oct_hr_df),
        note=(
            "Hourly forecast vs actual series is exported for the unseen October operational check "
            "(2026-10-18 to 2026-10-31 under realistic publish-date lag cutoff); August–September test "
            "metrics show the single logged final test evaluation without reloading test_features.parquet."
        ),
    )


@router.get("/groups", response_model=GroupsResponse)
def get_route_groups(request: Request) -> GroupsResponse:
    store = request.app.state.store
    return GroupsResponse(
        period="Jan–May 2026 Ridership Features + Spring 2026-04-09 GTFS Profiles",
        source="app_data/route_groups.json, route_groups_*.csv (incl. route_groups_pca_variance.csv) & route_geometries.json",
        metadata=store.route_groups_meta,
        pca_variance=clean_records(store.route_groups_pca_variance),
        routes=clean_records(store.route_groups_assigned),
        group_profiles=clean_records(store.route_groups_profiles),
        k_selection=clean_records(store.route_groups_k_selection),
        k2_vs_k3=clean_records(store.route_groups_k2_vs_k3),
        dbscan_summary=clean_records(store.route_groups_dbscan),
        geometries=store.route_geometries,
    )

