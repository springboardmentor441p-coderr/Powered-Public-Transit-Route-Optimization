"""Common Pydantic Schemas and Base Models for RouteRanker.

Includes pagination containers, health statuses, and compatibility base models.
"""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

try:
    from pydantic import BaseModel as _PydanticBaseModel, Field, ConfigDict
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

    class _PydanticBaseModel:
        """Lightweight Pydantic BaseModel fallback when pydantic is not installed."""
        def __init__(self, **data: Any) -> None:
            for k, v in data.items():
                setattr(self, k, v)

        def model_dump(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            res = {}
            for k, v in self.__dict__.items():
                if isinstance(v, _PydanticBaseModel):
                    res[k] = v.model_dump()
                elif isinstance(v, list):
                    res[k] = [x.model_dump() if isinstance(x, _PydanticBaseModel) else x for x in v]
                else:
                    res[k] = v
            return res

        def dict(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return self.model_dump(*args, **kwargs)

        @classmethod
        def model_validate(cls, obj: Any) -> Any:
            if isinstance(obj, dict):
                return cls(**obj)
            return obj

    def Field(default: Any = None, **kwargs: Any) -> Any:
        return default

    class ConfigDict(dict):
        pass

BaseModel = _PydanticBaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized API pagination response envelope."""
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    has_next: bool = False
    has_prev: bool = False
    items: List[T] = []

    def __init__(
        self,
        items: Optional[List[T]] = None,
        total: int = 0,
        page: int = 1,
        page_size: int = 50,
        **kwargs: Any,
    ) -> None:
        items = items or []
        total_pages = max(1, (total + page_size - 1) // max(1, page_size)) if total > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1
        super().__init__(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
            **kwargs,
        )


class HealthResponse(BaseModel):
    """System health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    data_loaded: bool = False
    duckdb_available: bool = False
    timestamp: str = ""
    tables_registered: List[str] = []


class StatusResponse(BaseModel):
    """Data processing status response."""
    status: str
    message: str
    last_processed_at: Optional[str] = None
    quality_score: Optional[float] = None
    raw_files_found: int = 0
    processed_tables: List[str] = []

