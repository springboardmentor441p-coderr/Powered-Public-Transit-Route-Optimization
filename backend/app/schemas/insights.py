"""Pydantic Schemas for Network Insights Endpoints."""

from __future__ import annotations

from typing import Any, List, Optional
from app.schemas.common import BaseModel, Field


class InsightItem(BaseModel):
    """An individual analytical finding derived from the schedule."""
    category: str
    title: str
    observation: str
    impact: str
    recommendation: str
    supporting_metric: str
    description: str = ""
    value: str = ""

    def __init__(self, **data: Any) -> None:
        if "observation" in data and "description" not in data:
            data["description"] = str(data["observation"])
        if "supporting_metric" in data and "value" not in data:
            data["value"] = str(data["supporting_metric"])
        super().__init__(**data)


class InsightsResponse(list):
    """Dual response: acts as list of InsightItem for frontend array responses, with executive summary attributes."""
    def __init__(
        self,
        system_overview: str = "",
        network_health_grade: str = "B+",
        insights: Optional[List[InsightItem]] = None,
        items: Optional[List[InsightItem]] = None,
        schedule_derived_notice: str = "",
        **kwargs: Any,
    ) -> None:
        insight_list = items if items is not None else (insights or [])
        super().__init__(insight_list)
        self.system_overview = system_overview
        self.network_health_grade = network_health_grade
        self.insights = insight_list
        self.schedule_derived_notice = (
            schedule_derived_notice or
            "Insights are derived algorithmically from schedule headway, network overlap, and geographic stop density."
        )
