"""Read-only DuckDB repository for historical ridership time-series queries."""

import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from app.core.config import settings
from app.core.exceptions import ArtifactUnavailableError

logger = logging.getLogger("ai_routeranker.repositories.duckdb")


class DuckDBRepository:
    """
    Read-only repository for analytical.daily_ridership in DuckDB.

    Opens a short-lived read-only connection per query with bounded memory (256 MB)
    and threads (2), uses exclusively parameterized SQL, and never mutates the DB.
    """

    def __init__(self, duckdb_path: Optional[Path] = None) -> None:
        self._db_path = Path(duckdb_path or settings.DUCKDB_PATH)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """Open a thread-isolated read-only DuckDB connection with resource limits."""
        if not self._db_path.exists() or not self._db_path.is_file():
            logger.error("DuckDB analytical database is missing.")
            raise ArtifactUnavailableError(
                code="DATABASE_UNAVAILABLE",
                message="Analytical ridership database is unavailable.",
            )
        try:
            con = duckdb.connect(str(self._db_path), read_only=True)
            con.execute("PRAGMA max_memory='256MB'")
            con.execute("PRAGMA threads=2")
            return con
        except Exception as exc:
            logger.error("Failed to open DuckDB read-only connection: %s", type(exc).__name__)
            raise ArtifactUnavailableError(
                code="DATABASE_UNAVAILABLE",
                message="Analytical ridership database could not be opened.",
            ) from exc

    def get_monthly_ridership(
        self,
        route_id: str,
        start_date: date,
        end_date: date,
        daytype: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query monthly aggregated ridership from analytical.daily_ridership."""
        sql = """
            SELECT
                strftime(date, '%Y-%m') AS period,
                AVG(CASE WHEN daytype = 'W' THEN rides END) AS weekday_avg_rides,
                AVG(CASE WHEN daytype = 'A' THEN rides END) AS saturday_avg_rides,
                AVG(CASE WHEN daytype = 'U' THEN rides END) AS sunday_avg_rides,
                SUM(rides) AS total_rides,
                COUNT(*) AS observation_days
            FROM analytical.daily_ridership
            WHERE route = ?
              AND date >= ?
              AND date <= ?
        """
        params: List[Any] = [route_id, start_date, end_date]
        if daytype is not None:
            sql += " AND daytype = ?"
            params.append(daytype)

        sql += """
            GROUP BY strftime(date, '%Y-%m')
            ORDER BY period ASC
        """

        con = self._connect()
        try:
            rows = con.execute(sql, params).fetchall()
            return [
                {
                    "period": str(r[0]),
                    "weekday_avg_rides": float(r[1]) if r[1] is not None else None,
                    "saturday_avg_rides": float(r[2]) if r[2] is not None else None,
                    "sunday_avg_rides": float(r[3]) if r[3] is not None else None,
                    "total_rides": int(r[4]) if r[4] is not None else 0,
                    "observation_days": int(r[5]),
                }
                for r in rows
            ]
        except duckdb.Error as exc:
            logger.error("DuckDB monthly ridership query failed: %s", type(exc).__name__)
            raise ArtifactUnavailableError(
                code="DATABASE_QUERY_FAILED",
                message="Analytical ridership data could not be queried.",
            ) from exc
        finally:
            con.close()

    def get_daily_ridership(
        self,
        route_id: str,
        start_date: date,
        end_date: date,
        daytype: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query daily ridership observations from analytical.daily_ridership."""
        sql = """
            SELECT
                strftime(date, '%Y-%m-%d') AS period,
                daytype,
                day_of_week,
                is_weekend,
                rides
            FROM analytical.daily_ridership
            WHERE route = ?
              AND date >= ?
              AND date <= ?
        """
        params: List[Any] = [route_id, start_date, end_date]
        if daytype is not None:
            sql += " AND daytype = ?"
            params.append(daytype)

        sql += " ORDER BY date ASC"

        con = self._connect()
        try:
            rows = con.execute(sql, params).fetchall()
            return [
                {
                    "period": str(r[0]),
                    "daytype": str(r[1]),
                    "day_of_week": str(r[2]),
                    "is_weekend": bool(r[3]),
                    "rides": int(r[4]),
                }
                for r in rows
            ]
        except duckdb.Error as exc:
            logger.error("DuckDB daily ridership query failed: %s", type(exc).__name__)
            raise ArtifactUnavailableError(
                code="DATABASE_QUERY_FAILED",
                message="Analytical ridership data could not be queried.",
            ) from exc
        finally:
            con.close()
