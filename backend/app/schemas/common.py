"""Common Pydantic schemas and safe value-sanitization helpers."""

import math
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


def to_optional_float(value: Any) -> Optional[float]:
    """Convert numeric values to float, preserving 0.0 and mapping NaN/Inf/NA to None."""
    if value is None or pd.isna(value):
        return None
    val = float(value)
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def to_optional_int(value: Any) -> Optional[int]:
    """Convert numeric values to int, preserving 0 and mapping NaN/NA to None."""
    if value is None or pd.isna(value):
        return None
    val = float(value)
    if math.isnan(val) or math.isinf(val):
        return None
    return int(val)


def to_optional_str(value: Any) -> Optional[str]:
    """Convert string values safely, mapping NaN/'nan'/empty to None."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


class PaginationMeta(BaseModel):
    """Pagination metadata returned with list endpoints."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(..., ge=0, description="Total matching records")
    offset: int = Field(..., ge=0, description="Current zero-based offset")
    limit: int = Field(..., ge=1, description="Maximum records per page")
    returned: int = Field(..., ge=0, description="Records returned in this page")
    has_more: bool = Field(..., description="Whether additional records remain")
