"""WebSocket module for real-time updates."""
from app.websocket.manager import ConnectionManager, get_connection_manager  # noqa: F401

__all__ = ["ConnectionManager", "get_connection_manager"]