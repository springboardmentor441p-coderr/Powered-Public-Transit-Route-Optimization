"""AI MetroFlow - Main FastAPI application."""
from contextlib import asynccontextmanager
from typing: Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from socketio import ASGIApp, AsyncServer

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.mongodb import connect_mongodb, close_mongodb
from app.core.redis import connect_redis, close_redis, start_redis_listener
from app.api.v1 import api_router
from app.websocket.manager import get_connection_manager, start_redis_listener as start_ws_redis_listener


# Socket.IO server for real-time updates
sio = AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.SOCKET_IO_CORS_ORIGINS,
    logger=settings.DEBUG,
    engineio_logger=settings.DEBUG,
)

# Create combined ASGI app
socket_app = ASGIApp(sio, socketio_path="/socket.io")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("Starting AI MetroFlow...")

    # Initialize databases
    await init_db()
    print("PostgreSQL initialized")

    await connect_mongodb()
    print("MongoDB connected")

    await connect_redis()
    print("Redis connected")

    # Set up WebSocket manager
    manager = get_connection_manager()
    manager.set_socketio(sio)

    # Start Redis listener for WebSocket
    asyncio.create_task(start_ws_redis_listener())
    print("WebSocket Redis listener started")

    # Initialize default data
    await init_default_data()
    print("Default data initialized")

    print(f"AI MetroFlow started on {settings.HOST}:{settings.PORT}")

    yield

    # Shutdown
    print("Shutting down AI MetroFlow...")
    await close_db()
    await close_mongodb()
    await close_redis()
    print("AI MetroFlow stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Platform for Metro Crowd Management and Scheduling",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO app
app.mount("/socket.io", socket_app)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# Socket.IO event handlers
@sio.event
async def connect(sid, environ, auth):
    """Handle client connection."""
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    print(f"Client disconnected: {sid}")


@sio.event
async def subscribe(sid, data):
    """Handle channel subscription."""
    channel = data.get("channel")
    if channel:
        manager = get_connection_manager()
        await manager.subscribe(sid, channel)
        await sio.emit("subscribed", {"channel": channel}, room=sid)


@sio.event
async def unsubscribe(sid, data):
    """Handle channel unsubscription."""
    channel = data.get("channel")
    if channel:
        manager = get_connection_manager()
        await manager.unsubscribe(sid, channel)
        await sio.emit("unsubscribed", {"channel": channel}, room=sid)


# WebSocket endpoint (alternative to Socket.IO)
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates."""
    manager = get_connection_manager()
    await manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming messages
            if data.get("type") == "subscribe":
                await manager.subscribe(client_id, data.get("channel"))
            elif data.get("type") == "unsubscribe":
                await manager.unsubscribe(client_id, data.get("channel"))
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(client_id)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "AI Platform for Metro Crowd Management and Scheduling",
        "docs": "/docs",
        "health": "/health",
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


async def init_default_data():
    """Initialize default data for development."""
    from app.core.database import get_db_context
    from app.services.auth import AuthService
    from app.services.station import StationService
    from app.services.train import TrainService
    from app.models.user import UserRole
    from app.models.train import TrainStatus, DayType
    from uuid import uuid4

    async with get_db_context() as db:
        auth_service = AuthService(db)
        station_service = StationService(db)
        train_service = TrainService(db)

        # Create default admin user
        admin = await auth_service.get_user_by_email("admin@metroflow.com")
        if not admin:
            from app.schemas.auth import RegisterRequest
            await auth_service.create_user(RegisterRequest(
                email="admin@metroflow.com",
                password="admin123",
                full_name="System Admin",
                role="admin",
            ))

        # Create default operator user
        operator = await auth_service.get_user_by_email("operator@metroflow.com")
        if not operator:
            from app.schemas.auth import RegisterRequest
            await auth_service.create_user(RegisterRequest(
                email="operator@metroflow.com",
                password="operator123",
                full_name="Metro Operator",
                role="operator",
            ))

        # Create default viewer user
        viewer = await auth_service.get_user_by_email("viewer@metroflow.com")
        if not viewer:
            from app.schemas.auth import RegisterRequest
            await auth_service.create_user(RegisterRequest(
                email="viewer@metroflow.com",
                password="viewer123",
                full_name="Metro Viewer",
                role="viewer",
            ))

        # Create sample lines and stations
        line1 = await station_service.get_line_by_code("RED")
        if not line1:
            from app.schemas.station import LineCreate, StationCreate
            line1 = await station_service.create_line(LineCreate(
                name="Red Line",
                code="RED",
                color="#FF0000",
                description="Main north-south line",
            ))

            # Create stations for Red Line
            stations_data = [
                {"name": "Central Station", "code": "CEN", "order": 0, "lat": 40.7580, "lon": -73.9855, "capacity": 2000, "zone": "1", "interchange": True},
                {"name": "Times Square", "code": "TSQ", "order": 1, "lat": 40.7589, "lon": -73.9851, "capacity": 1500, "zone": "1"},
                {"name": "Grand Central", "code": "GCT", "order": 2, "lat": 40.7527, "lon": -73.9772, "capacity": 1800, "zone": "1", "interchange": True},
                {"name": "Union Square", "code": "USQ", "order": 3, "lat": 40.7359, "lon": -73.9911, "capacity": 1200, "zone": "2"},
                {"name": "Brooklyn Bridge", "code": "BBR", "order": 4, "lat": 40.7061, "lon": -73.9969, "capacity": 1000, "zone": "2"},
            ]

            for s in stations_data:
                await station_service.create_station(StationCreate(
                    line_id=line1.id,
                    name=s["name"],
                    code=s["code"],
                    order=s["order"],
                    latitude=s["lat"],
                    longitude=s["lon"],
                    capacity=s["capacity"],
                    zone=s["zone"],
                    is_interchange=s.get("interchange", False),
                ))

        line2 = await station_service.get_line_by_code("BLU")
        if not line2:
            from app.schemas.station import LineCreate, StationCreate
            line2 = await station_service.create_line(LineCreate(
                name="Blue Line",
                code="BLU",
                color="#0000FF",
                description="East-west line",
            ))

            stations_data = [
                {"name": "Airport", "code": "APT", "order": 0, "lat": 40.6413, "lon": -73.7781, "capacity": 1500, "zone": "3"},
                {"name": "Jamaica Center", "code": "JAM", "order": 1, "lat": 40.7036, "lon": -73.8031, "capacity": 2000, "zone": "3", "interchange": True},
                {"name": "Forest Hills", "code": "FHS", "order": 2, "lat": 40.7196, "lon": -73.8460, "capacity": 1200, "zone": "2"},
                {"name": "Roosevelt Ave", "code": "RVA", "order": 3, "lat": 40.7458, "lon": -73.8942, "capacity": 1500, "zone": "2"},
                {"name": "Queens Plaza", "code": "QPL", "order": 4, "lat": 40.7505, "lon": -73.9370, "capacity": 1800, "zone": "1", "interchange": True},
            ]

            for s in stations_data:
                await station_service.create_station(StationCreate(
                    line_id=line2.id,
                    name=s["name"],
                    code=s["code"],
                    order=s["order"],
                    latitude=s["lat"],
                    longitude=s["lon"],
                    capacity=s["capacity"],
                    zone=s["zone"],
                    is_interchange=s.get("interchange", False),
                ))

        # Create sample trains
        red_line_stations = await station_service.get_stations_by_line(line1.id)
        blue_line_stations = await station_service.get_stations_by_line(line2.id)

        for i, train_num in enumerate(["RED-001", "RED-002", "RED-003"]):
            existing = await train_service.get_train_by_number(train_num)
            if not existing:
                from app.schemas.train import TrainCreate
                await train_service.create_train(TrainCreate(
                    train_number=train_num,
                    line_id=line1.id,
                    capacity=500,
                ))

        for i, train_num in enumerate(["BLU-001", "BLU-002"]):
            existing = await train_service.get_train_by_number(train_num)
            if not existing:
                from app.schemas.train import TrainCreate
                await train_service.create_train(TrainCreate(
                    train_number=train_num,
                    line_id=line2.id,
                    capacity=500,
                ))

        # Create sample schedules
        red_trains = await train_service.list_trains(line_id=line1.id)
        blue_trains = await train_service.list_trains(line_id=line2.id)

        for train in red_trains:
            # Create basic schedule for each train
            for day_type in DayType:
                for seq, station in enumerate(red_line_stations):
                    from app.schemas.train import ScheduleCreate
                    from datetime import time
                    hour = 6 + seq * 2  # 6am, 8am, 10am, etc.
                    minute = (seq * 3) % 60
                    existing_schedules = await train_service.db.execute(
                        train_service.db.query.select().where(
                            train_service.db.query.select().where(
                                # Simplified check
                            )
                        )
                    )
                    # Just create if not exists (simplified)
                    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )