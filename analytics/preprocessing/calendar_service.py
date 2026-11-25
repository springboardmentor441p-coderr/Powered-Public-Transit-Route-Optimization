"""
AI_RouteRanker - GTFS Historical Service Calendar Service
Evaluates service activation for (service_id, date) pairs combining
calendar.txt and calendar_dates.txt exception rules according to GTFS specifications.
Complies with Milestone 3.1 specifications.
"""

import datetime
from typing import Dict, List, Optional, Set, Tuple


class GTFSServiceCalendar:
    """
    Evaluator for GTFS service operation on specific calendar dates.
    Accounts for weekly day-of-week operations, valid date ranges,
    and calendar_dates exception overrides (1=added, 2=removed).
    """

    WEEKDAY_COLUMNS = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    def __init__(self):
        # service_id -> {start_date: date, end_date: date, monday: int, ...}
        self.calendar_rules: Dict[str, Dict[str, object]] = {}
        # (service_id, date) -> exception_type (1 or 2)
        self.exceptions: Dict[Tuple[str, datetime.date], int] = {}
        # All known service IDs
        self.known_services: Set[str] = set()

    def add_calendar_rule(
        self,
        service_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
        monday: int,
        tuesday: int,
        wednesday: int,
        thursday: int,
        friday: int,
        saturday: int,
        sunday: int,
    ):
        """Register a base weekly operating rule from calendar.txt."""
        self.known_services.add(service_id)
        self.calendar_rules[service_id] = {
            "start_date": start_date,
            "end_date": end_date,
            "monday": int(monday),
            "tuesday": int(tuesday),
            "wednesday": int(wednesday),
            "thursday": int(thursday),
            "friday": int(friday),
            "saturday": int(saturday),
            "sunday": int(sunday),
        }

    def add_exception(
        self,
        service_id: str,
        target_date: datetime.date,
        exception_type: int,
    ):
        """Register a service exception override from calendar_dates.txt."""
        self.known_services.add(service_id)
        self.exceptions[(service_id, target_date)] = int(exception_type)

    def is_service_active(self, service_id: str, target_date: datetime.date) -> bool:
        """
        Determine if service operates on target_date.
        Rules:
        1. Exception override:
           - exception_type == 1 -> Service Added -> TRUE
           - exception_type == 2 -> Service Removed -> FALSE
        2. Regular weekly schedule:
           - If target_date is between start_date and end_date:
             Check weekday flag (monday..sunday).
             Flag == 1 -> TRUE, Flag == 0 -> FALSE
           - If outside start_date/end_date range -> FALSE
        3. If service_id not found -> FALSE
        """
        # Rule 1: Calendar dates exception override takes highest precedence
        if (service_id, target_date) in self.exceptions:
            exc = self.exceptions[(service_id, target_date)]
            if exc == 1:
                return True
            elif exc == 2:
                return False

        # Rule 2: Base calendar rule
        rule = self.calendar_rules.get(service_id)
        if not rule:
            return False

        if target_date < rule["start_date"] or target_date > rule["end_date"]:
            return False

        # Python weekday: Monday=0, Sunday=6
        weekday_name = self.WEEKDAY_COLUMNS[target_date.weekday()]
        return rule.get(weekday_name, 0) == 1

    def get_active_services_for_date(self, target_date: datetime.date) -> Set[str]:
        """Return the set of all service_ids active on target_date."""
        active = set()
        for srv in self.known_services:
            if self.is_service_active(srv, target_date):
                active.add(srv)
        return active
