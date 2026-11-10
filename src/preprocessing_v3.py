"""Feature contract from RouteRanker Intern Guide v3."""

import pandas as pd

LAG_DAYS = (1, 7, 14, 21, 28)
SEASONAL_LAG_DAYS = (7, 14, 21, 28)
LAG_COLUMNS = {days: f"lag_{days}d_boardings" for days in LAG_DAYS}
SEASONAL_COLUMNS = [LAG_COLUMNS[days] for days in SEASONAL_LAG_DAYS]
DEMAND_FEATURES = [
    "route",
    "day_of_week",
    "month",
    "is_weekend",
    "is_sunday_holiday_daytype",
    *(LAG_COLUMNS[days] for days in LAG_DAYS),
    "seasonal_lag_observations",
    "past_four_same_weekdays_mean",
]
SERVICE_FEATURES = ["scheduled_trips", "scheduled_service_hours"]
TARGET = "rides"


def make_forecasting_features(
    observations: pd.DataFrame,
    reporting_delay_days: int = 1,
    target_rows: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build exact route/calendar lags visible under a reporting-delay policy.

    For target date D and an assumed delay of one day, rides dated through
    D-1 are allowed. Lags younger than the configured delay are suppressed.
    """
    if not isinstance(reporting_delay_days, int) or reporting_delay_days < 1:
        raise ValueError("reporting_delay_days must be a positive integer")
    required_history = {"route", "date", "daytype", "rides"}
    if not required_history.issubset(observations.columns):
        raise ValueError(f"Observations must contain {sorted(required_history)}")
    history = observations[["route", "date", "daytype", "rides"]].copy()
    history["route"] = history["route"].astype("string").str.strip()
    history["date"] = pd.to_datetime(history["date"], errors="coerce").dt.normalize()
    history["daytype"] = history["daytype"].astype("string").str.strip().str.upper()
    history["rides"] = pd.to_numeric(history["rides"], errors="coerce")
    if history[["route", "date", "daytype", "rides"]].isna().any().any():
        raise ValueError("Observations contain missing route/date/daytype/rides values")
    if history.duplicated(["route", "date"]).any():
        raise ValueError("Observations must be unique by route/date")
    if not history["daytype"].isin(["W", "A", "U"]).all():
        raise ValueError("daytype must contain only W, A, or U")

    if target_rows is None:
        frame = history.copy()
    else:
        required_targets = {"route", "date", "daytype"}
        if not required_targets.issubset(target_rows.columns):
            raise ValueError(f"target_rows must contain {sorted(required_targets)}")
        target_columns = ["route", "date", "daytype"]
        if "rides" in target_rows.columns:
            target_columns.append("rides")
        frame = target_rows[target_columns].copy()
        frame["route"] = frame["route"].astype("string").str.strip()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame["daytype"] = frame["daytype"].astype("string").str.strip().str.upper()
        if "rides" in frame.columns:
            frame["rides"] = pd.to_numeric(frame["rides"], errors="coerce")
        if frame[["route", "date", "daytype"]].isna().any().any():
            raise ValueError("target_rows contain missing route/date/daytype values")
        if "rides" in frame.columns and frame["rides"].notna().any():
            raise ValueError("target_rows must not include observed rides")
        if frame.duplicated(["route", "date"]).any():
            raise ValueError("target_rows must be unique by route/date")
        if not frame["daytype"].isin(["W", "A", "U"]).all():
            raise ValueError("target daytype must contain only W, A, or U")

    frame["day_of_week"] = frame["date"].dt.dayofweek.astype("int8")
    frame["month"] = frame["date"].dt.month.astype("int8")
    frame["is_weekend"] = (frame["day_of_week"] >= 5).astype("int8")
    # CTA's reported U marks Sundays and holidays. This flag is retained as a
    # calendar predictor under the guide's declared known-calendar assumption.
    frame["is_sunday_holiday_daytype"] = frame["daytype"].eq("U").astype("int8")

    lookup_base = history[["route", "date", "rides"]]
    for days, column in LAG_COLUMNS.items():
        lookup = lookup_base.rename(columns={"date": "source_date", "rides": column}).copy()
        lookup["date"] = lookup["source_date"] + pd.to_timedelta(days, unit="D")
        frame = frame.merge(
            lookup[["route", "date", column]],
            on=["route", "date"], how="left", validate="one_to_one",
        )
        if days < reporting_delay_days:
            frame[column] = pd.NA

    frame["seasonal_lag_observations"] = frame[SEASONAL_COLUMNS].notna().sum(axis=1).astype("int8")
    seasonal_mean = frame[SEASONAL_COLUMNS].mean(axis=1)
    frame["past_four_same_weekdays_mean"] = seasonal_mean.where(
        frame["seasonal_lag_observations"] >= 2
    )
    return frame.sort_values(["date", "route"]).reset_index(drop=True)


def apply_service_features(
    features: pd.DataFrame,
    service: pd.DataFrame,
) -> pd.DataFrame:
    """Join forecast-available service on exact route/date keys."""
    required = {"route", "date", *SERVICE_FEATURES}
    if not required.issubset(service.columns):
        raise ValueError(f"Service table must contain {sorted(required)}")
    service = service.copy()
    if "match_status" in service.columns:
        service = service.loc[service["match_status"].eq("matched")].copy()
    extra = [
        column for column in ("source_snapshot", "archive_available_from", "match_status")
        if column in service.columns
    ]
    schedules = service[["route", "date", *SERVICE_FEATURES, *extra]].copy()
    schedules["route"] = schedules["route"].astype("string").str.strip()
    schedules["date"] = pd.to_datetime(schedules["date"], errors="coerce").dt.normalize()
    schedules["scheduled_trips"] = pd.to_numeric(schedules["scheduled_trips"], errors="coerce")
    schedules["scheduled_service_hours"] = pd.to_numeric(
        schedules["scheduled_service_hours"], errors="coerce"
    )
    if schedules.duplicated(["route", "date"]).any():
        raise ValueError("Service table must be unique by route/date")
    if "archive_available_from" in schedules.columns:
        schedules["archive_available_from"] = pd.to_datetime(
            schedules["archive_available_from"], errors="coerce"
        ).dt.normalize()
        if schedules["archive_available_from"].isna().any() or (
            schedules["archive_available_from"] >= schedules["date"]
        ).any():
            raise ValueError(
                "Replay schedule snapshots must have a capture date strictly before the target date"
            )
    return features.merge(
        schedules, on=["route", "date"], how="inner", validate="one_to_one"
    )
