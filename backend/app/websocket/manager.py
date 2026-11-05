"""WebSocket connection manager for real-time updates."""
from typing: Dict, List, Optional, Set
from uuid import UUID
import json
import asyncio
from datetime import datetime

from fastapi import WebSocket
from socketio import AsyncServer

from app.core.redis import publish, subscribe
from app.core.config import settings


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        # Active connections: {client_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Subscriptions: {channel: Set[client_id]}
        self.subscriptions: Dict[str, Set[str]] = {}
        # User to client mapping: {user_id: Set[client_id]}
        self.user_clients: Dict[str, Set[str]] = {}
        # Socket.IO server
        self.sio: Optional[AsyncServer] = None

    def set_socketio(self, sio: AsyncServer):
        """Set Socket.IO server instance."""
        self.sio = sio

    async def connect(self, websocket: WebSocket, client_id: str, user_id: Optional[str] = None):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket

        if user_id:
            if user_id not in self.user_clients:
                self.user_clients[user_id] = set()
            self.user_clients[user_id].add(client_id)

    def disconnect(self, client_id: str, user_id: Optional[str] = None):
        """Remove WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Remove from subscriptions
        for channel, clients in self.subscriptions.items():
            clients.discard(client_id)

        # Remove from user mapping
        if user_id and user_id in self.user_clients:
            self.user_clients[user_id].discard(client_id)
            if not self.user_clients[user_id]:
                del self.user_clients[user_id]

    async def subscribe(self, client_id: str, channel: str):
        """Subscribe client to a channel."""
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()
        self.subscriptions[channel].add(client_id)

    async def unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe client from a channel."""
        if channel in self.subscriptions:
            self.subscriptions[channel].discard(client_id)

    async def send_personal_message(self, client_id: str, message: dict):
        """Send message to specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, channel: str, message: dict):
        """Broadcast message to all subscribers of a channel."""
        if channel in self.subscriptions:
            disconnected = []
            for client_id in self.subscriptions[channel]:
                if client_id in self.active_connections:
                    try:
                        await self.active_connections[client_id].send_json(message)
                    except Exception:
                        disconnected.append(client_id)

            # Clean up disconnected clients
            for client_id in disconnected:
                self.disconnect(client_id)

    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast message to all connections of a user."""
        if user_id in self.user_clients:
            for client_id in self.user_clients[user_id]:
                await self.send_personal_message(client_id, message)

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    def get_connection_count(self) -> int:
        """Get total active connections."""
        return len(self.active_connections)

    def get_channel_subscribers(self, channel: str) -> int:
        """Get subscriber count for a channel."""
        return len(self.subscriptions.get(channel, set()))


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


# Channel names
class Channels:
    """WebSocket channel names."""
    ALERTS = "alerts"
    CONGESTION = "congestion"
    TRAIN_UPDATES = "train_updates"
    STATION_UPDATES = "station_updates"
    SYSTEM_STATUS = "system_status"
    PREDICTIONS = "predictions"


# Helper functions for broadcasting specific events
async def broadcast_alert(alert_data: dict):
    """Broadcast new alert to subscribers."""
    manager = get_connection_manager()
    await manager.broadcast(Channels.ALERTS, {
        "type": "alert",
        "data": alert_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
    # Also publish to Redis for multi-instance support
    await publish(Channels.ALERTS, alert_data)


async def broadcast_congestion_update(congestion_data: dict):
    """Broadcast congestion update."""
    manager = get_connection_manager()
    await manager.broadcast(Channels.CONGESTION, {
        "type": "congestion_update",
        "data": congestion_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
    await publish(Channels.CONGESTION, congestion_data)


async def broadcast_train_update(train_data: dict):
    """Broadcast train status update."""
    manager = get_connection_manager()
    await manager.broadcast(Channels.TRAIN_UPDATES, {
        "type": "train_update",
        "data": train_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
    await publish(Channels.TRAIN_UPDATES, train_data)


async def broadcast_station_update(station_data: dict):
    """Broadcast station status update."""
    manager = get_connection_manager()
    await manager.broadcast(Channels.STATION_UPDATES, {
        "type": "station_update",
        "data": station_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
    await publish(Channels.STATION_UPDATES, station_data)


async def broadcast_system_status(status_data: dict):
    """Broadcast system status update."""
    manager = get_connection_manager()
    await manager.broadcast(Channels.SYSTEM_STATUS, {
        "type": "system_status",
        "data": status_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
    await publish(Channels.SYSTEM_STATUS, status_data)


async def broadcast_prediction(prediction_data: dict):
    """Broadcast new prediction."""
    manager = get_connection_manager()
    await manager.broadcast(Channels.PREDICTIONS, {
        "type": "prediction",
        "data": prediction_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
    await publish(Channels.PREDICTIONS, prediction_data)


# Redis listener for multi-instance support
async def start_redis_listener():
    """Start Redis listener for cross-instance messaging."""
    channels = [
        Channels.ALERTS,
        Channels.CONGESTION,
        Channels.TRAIN_UPDATES,
        Channels.STATION_UPDATES,
        Channels.SYSTEM_STATUS,
        Channels.PREDICTIONS,
    ]

    for channel in channels:
        pubsub = await subscribe(channel)
        asyncio.create_task(_listen_redis_channel(channel, pubsub))


async def _listen_redis_channel(channel: str, pubsub):
    """Listen to Redis channel and broadcast to local connections."""
    manager = get_connection_manager()
    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                await manager.broadcast(channel, {
                    "type": channel.rstrip("s"),  # singular
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception:
                pass  # Ignore parsing errors