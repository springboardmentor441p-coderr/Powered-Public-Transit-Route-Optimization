"""FastAPI Compatibility Layer.

Allows standard FastAPI definitions while providing a lightweight fallback
when run in restricted offline environments.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

try:
    from fastapi import APIRouter as _APIRouter, FastAPI as _FastAPI, HTTPException, Query, Path, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: Any = None) -> None:
            self.status_code = status_code
            self.detail = detail
            super().__init__(f"HTTP {status_code}: {detail}")

    class status:
        HTTP_200_OK = 200
        HTTP_201_CREATED = 201
        HTTP_400_BAD_REQUEST = 400
        HTTP_404_NOT_FOUND = 404
        HTTP_500_INTERNAL_SERVER_ERROR = 500

    def Query(default: Any = None, **kwargs: Any) -> Any:
        return default

    def Path(default: Any = None, **kwargs: Any) -> Any:
        return default

    class _APIRouter:
        """Lightweight APIRouter fallback."""
        def __init__(self, prefix: str = "", tags: Optional[List[str]] = None) -> None:
            self.prefix = prefix
            self.tags = tags or []
            self.routes: List[Dict[str, Any]] = []

        def get(self, path: str, response_model: Any = None, **kwargs: Any) -> Callable:
            def decorator(func: Callable) -> Callable:
                self.routes.append({"method": "GET", "path": self.prefix + path, "func": func})
                return func
            return decorator

        def post(self, path: str, response_model: Any = None, **kwargs: Any) -> Callable:
            def decorator(func: Callable) -> Callable:
                self.routes.append({"method": "POST", "path": self.prefix + path, "func": func})
                return func
            return decorator

    class _FastAPI:
        """Lightweight FastAPI fallback."""
        def __init__(self, title: str = "", version: str = "", **kwargs: Any) -> None:
            self.title = title
            self.version = version
            self.routes: List[Dict[str, Any]] = []
            self.startup_handlers: List[Callable] = []

        def include_router(self, router: Any, prefix: str = "", tags: Optional[List[str]] = None) -> None:
            for r in getattr(router, "routes", []):
                self.routes.append(r)

        def add_middleware(self, *args: Any, **kwargs: Any) -> None:
            pass

        def on_event(self, event_type: str) -> Callable:
            def decorator(func: Callable) -> Callable:
                if event_type == "startup":
                    self.startup_handlers.append(func)
                return func
            return decorator

        def get(self, path: str, **kwargs: Any) -> Callable:
            def decorator(func: Callable) -> Callable:
                self.routes.append({"method": "GET", "path": path, "func": func})
                return func
            return decorator

    class CORSMiddleware:
        pass

    class JSONResponse:
        def __init__(self, content: Any, status_code: int = 200) -> None:
            self.content = content
            self.status_code = status_code

APIRouter = _APIRouter
FastAPI = _FastAPI

