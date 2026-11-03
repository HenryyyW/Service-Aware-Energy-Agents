"""Production-ready FastAPI application for Service-Aware Energy Agents."""

import time
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Request, Response, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.config import get_settings
from src.api.config import Settings
from src.api.database import close_db, init_db
from src.api.logging_config import (
    CorrelationIdFilter,
    get_correlation_id,
    set_correlation_id,
    setup_logging,
)
from src.api.routes import network, simulation, scenarios, runs

settings = get_settings()

# Initialize logging
setup_logging(log_level=settings.log_level, log_format=settings.log_format)

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.rate_limit_requests}/{settings.rate_limit_window_seconds}seconds"
    ],
)


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list] = {}

    async def connect(self, websocket: WebSocket, run_id: str):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)

    def disconnect(self, websocket: WebSocket, run_id: str):
        if run_id in self.active_connections:
            self.active_connections[run_id].remove(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def broadcast(self, run_id: str, message: dict):
        if run_id in self.active_connections:
            for connection in self.active_connections[run_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass


manager = ConnectionManager()


def _create_ws_message(
    msg_type: str, payload: dict, run_id: str, meta: dict = None
) -> dict:
    """Create a WebSocket message with standard meta fields."""
    correlation_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat() + "Z"
    default_meta = {
        "timestamp": now,
        "stale": False,
        "reconnecting": False,
        "correlation_id": correlation_id,
    }
    if meta:
        default_meta.update(meta)
    return {
        "type": msg_type,
        "payload": payload,
        "meta": default_meta,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with proper startup/shutdown."""
    # Startup
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)

    # Initialize database
    await init_db()

    # Log startup
    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        "Starting Service-Aware Energy Agents API",
        extra={
            "version": settings.app_version,
            "environment": settings.environment,
            "workers": settings.workers,
        },
    )

    yield

    # Shutdown
    logger = logging.getLogger(__name__)
    logger.info("Shutting down Service-Aware Energy Agents API...")

    await close_db()


def create_app(settings_override: Optional[Settings] = None) -> FastAPI:
    """Create FastAPI application with all middleware and routes."""
    global settings
    if settings_override:
        settings = settings_override

    app = FastAPI(
        title=settings.app_name,
        description="API for Spatio-Temporal Virtual Community Simulator for Renewable Energy Communities",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # Store settings in app state
    app.state.settings = settings

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Request-ID"],
    )

    # Security headers middleware
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # Correlation ID and request timing middleware
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        # Get or generate correlation ID
        correlation_id = (
            request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:8]
        )
        set_correlation_id(correlation_id)

        # Add to request state for access in routes
        request.state.correlation_id = correlation_id
        request.state.start_time = time.time()

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = correlation_id

        # Add timing header
        process_time = time.time() - request.state.start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        return response

    # Request logging middleware
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        logger = logging.getLogger("request")
        start_time = time.time()

        # Log request
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else "unknown",
            },
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                },
                exc_info=True,
            )
            raise

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger("exception")
        logger.error(
            "Unhandled exception",
            extra={
                "method": request.method,
                "url": str(request.url),
                "error": str(exc),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "correlation_id": get_correlation_id(),
            },
        )

    # Health check endpoints
    @app.get("/health", tags=["health"], include_in_schema=False)
    @limiter.limit("100/minute")
    async def health(request: Request):
        """Liveness probe - basic health check."""
        return {"status": "healthy", "version": settings.app_version}

    @app.get("/ready", tags=["health"], include_in_schema=False)
    @limiter.limit("100/minute")
    async def ready(request: Request):
        """Readiness probe - checks database connectivity."""
        from src.api.database import engine
        from sqlalchemy import text

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ready", "database": "connected"}
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not ready",
                    "database": "disconnected",
                    "error": str(e),
                },
            )

    @app.get("/health/details", tags=["health"], include_in_schema=False)
    @limiter.limit("10/minute")
    async def health_details(request: Request):
        """Detailed health check with system info."""
        import psutil
        import sys

        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
            "python_version": sys.version.split()[0],
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }

    # WebSocket endpoints for real-time simulation updates
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """General WebSocket endpoint."""
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                # Echo back for testing
                await websocket.send_json(
                    _create_ws_message("echo", json.loads(data), "general")
                )
        except WebSocketDisconnect:
            pass

    @app.websocket("/ws/simulation/{run_id}")
    async def websocket_simulation(websocket: WebSocket, run_id: str):
        """WebSocket endpoint for real-time simulation updates with stale-data protection."""
        await manager.connect(websocket, run_id)

        # Send initial connection message with meta
        await websocket.send_json(
            _create_ws_message(
                "connected",
                {"run_id": run_id, "message": "WebSocket connected"},
                run_id,
                {"stage": "connected"},
            )
        )

        try:
            while True:
                # Keep connection alive, send periodic updates if simulation is running
                await asyncio.sleep(1)
                # Note: In a full implementation, this would check actual simulation status
                # For now, we just keep the connection alive
        except WebSocketDisconnect:
            manager.disconnect(websocket, run_id)

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "API for Spatio-Temporal Virtual Community Simulator",
            "docs": "/docs" if settings.debug else "disabled in production",
        }

    # Include routers
    app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
    app.include_router(network.router, prefix="/api/network", tags=["network"])
    app.include_router(simulation.router, prefix="/api/simulation", tags=["simulation"])
    app.include_router(runs.runs_router, prefix="/api/simulations", tags=["runs"])
    app.include_router(runs.reports_router, prefix="/api/reports", tags=["reports"])
    app.include_router(
        runs.comparison_router, prefix="/api/compare", tags=["comparison"]
    )

    # Agent API routes
    try:
        from src.api.routes import agent

        app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    except ImportError:
        pass  # Agent routes may not exist yet

    return app


# Create the app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers if not settings.debug else 1,
        reload=settings.debug,
        log_config=None,  # We use our own logging config
    )
