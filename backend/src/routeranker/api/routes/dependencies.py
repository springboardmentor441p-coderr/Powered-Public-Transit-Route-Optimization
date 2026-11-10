"""Request-scoped access to the process-cached service."""

from fastapi import Request

from ..services import RouteRankerService


def get_service(request: Request) -> RouteRankerService:
    return request.app.state.service
