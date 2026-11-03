"""FastAPI application entry point."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import json
import asyncio
import uuid
import os
import time
from datetime import datetime
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response

from app.state import (
    REDIS_AVAILABLE,
    TASK_DURATION,
    TASKS_TOTAL,
    TASK_QUEUE_SIZE,
    LLM_TOKENS_TOTAL,
    LLM_COST_TOTAL,
    TASK_RETRIES,
    get_redis_client,
    get_task_queue,
    get_job,
)

from app.routers import scenarios, simulations, agent, reports, compare, network


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if REDIS_AVAILABLE:
        client = get_redis_client()
        if client:
            print(f"Connected to Redis at {redis_url}")
        else:
            print("Warning: Redis not available, using in-memory queue")
    else:
        print("Warning: Redis/RQ not available, using in-memory queue")
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Service-Aware Energy Agents API",
    description="API for renewable energy community simulation with grid constraints",
    version="0.1.0",
    lifespan=lifespan,
)


# Exception handlers for RFC 7807 structured errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "type": "https://tools.ietf.org/html/rfc7807#section-3.2",
            "title": "Validation Error",
            "status": 422,
            "detail": "Request validation failed",
            "instance": str(request.url),
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://tools.ietf.org/html/rfc7807#section-3.2",
            "title": "Internal Server Error",
            "status": 500,
            "detail": str(exc),
            "instance": str(request.url),
        },
    )


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
app.include_router(simulations.router, prefix="/api", tags=["simulations"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(compare.router, prefix="/api", tags=["comparison"])
app.include_router(network.router, prefix="/api", tags=["network"])


# OpenAPI schema endpoint for frontend code generation
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema():
    """Return OpenAPI schema for frontend client generation."""
    return app.openapi()


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

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
            if run_id in simulations._runs:
                run = simulations._runs[run_id]
                if run["status"] == "running":
                    meta = {
                        "stage": run.get("stage", "simulating"),
                        "eta_seconds": run.get("eta_seconds"),
                        "stale": False,
                        "reconnecting": False,
                    }
                    await websocket.send_json(
                        _create_ws_message(
                            "simulation_update",
                            {
                                "run_id": run_id,
                                "status": run["status"],
                                "current_step": run.get("current_step", 0),
                                "total_steps": run.get("total_steps", 0),
                                "progress": run.get("progress", 0),
                                "stage": run.get("stage"),
                                "eta_seconds": run.get("eta_seconds"),
                            },
                            run_id,
                            meta,
                        )
                    )
                elif run["status"] in ["completed", "failed", "cancelled"]:
                    # Send final update then close
                    meta = {
                        "stage": run.get("stage", run["status"]),
                        "stale": False,
                        "reconnecting": False,
                    }
                    await websocket.send_json(
                        _create_ws_message(
                            (
                                "simulation_complete"
                                if run["status"] == "completed"
                                else "simulation_error"
                            ),
                            {
                                "run_id": run_id,
                                "status": run["status"],
                                "outcome_sentence": run.get("outcome_sentence"),
                                "error": run.get("error"),
                            },
                            run_id,
                            meta,
                        )
                    )
                    break
    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id)


@app.websocket("/ws/p2p/{run_id}")
async def websocket_p2p(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time P2P orderbook and trade updates."""
    await manager.connect(websocket, run_id)

    # Send initial connection message
    await websocket.send_json(
        _create_ws_message(
            "connected",
            {"run_id": run_id, "message": "P2P WebSocket connected"},
            run_id,
            {"stage": "connected", "market_type": "p2p"},
        )
    )

    try:
        while True:
            await asyncio.sleep(0.5)  # Faster updates for P2P real-time data

            # Check if run exists and get P2P engine
            if run_id not in simulations._couplers:
                # Run not started yet, wait
                await websocket.send_json(
                    _create_ws_message(
                        "p2p_waiting",
                        {
                            "run_id": run_id,
                            "message": "Waiting for simulation to start",
                        },
                        run_id,
                        {"stage": "waiting", "reconnecting": False},
                    )
                )
                continue

            coupler = simulations._couplers[run_id]

            # Access P2P engine through settlement engine
            p2p_engine = None
            if coupler.settlement_engine and hasattr(
                coupler.settlement_engine, "market_engine"
            ):
                market_engine = coupler.settlement_engine.market_engine
                if hasattr(market_engine, "p2p_engine"):
                    p2p_engine = market_engine.p2p_engine

            if p2p_engine is None:
                # Not a P2P market or not initialized yet
                await websocket.send_json(
                    _create_ws_message(
                        "p2p_unavailable",
                        {
                            "run_id": run_id,
                            "message": "P2P market not active for this run",
                        },
                        run_id,
                        {"stage": "unavailable", "reconnecting": False},
                    )
                )
                continue

            # Get order book snapshot
            order_book = p2p_engine.get_order_book_snapshot()

            # Get recent trades (last 10)
            trade_history = p2p_engine.get_trade_history()[-10:]

            # Build payload
            payload = {
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "order_book": order_book,
                "recent_trades": trade_history,
                "stats": {
                    "total_buy_orders": len(order_book["buy_orders"]),
                    "total_sell_orders": len(order_book["sell_orders"]),
                    "total_trades": len(p2p_engine.trades),
                    "total_volume_kwh": sum(t.quantity_kwh for t in p2p_engine.trades),
                    "total_value_usd": sum(
                        t.buyer_payment_usd for t in p2p_engine.trades
                    ),
                },
            }

            meta = {
                "stage": "active",
                "stale": False,
                "reconnecting": False,
            }

            await websocket.send_json(
                _create_ws_message("p2p_update", payload, run_id, meta)
            )

    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id)


@app.websocket("/ws/agent/{task_id}")
async def websocket_agent_task(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time agent task status updates."""
    await manager.connect(websocket, task_id)

    # Send initial connection message
    await websocket.send_json(
        _create_ws_message(
            "connected",
            {"task_id": task_id, "message": "Agent task WebSocket connected"},
            task_id,
            {"stage": "connected"},
        )
    )

    try:
        from app.routers import agent as agent_router

        while True:
            await asyncio.sleep(1)

            # Check if task exists
            if task_id not in agent_router._tasks:
                await websocket.send_json(
                    _create_ws_message(
                        "task_not_found",
                        {"task_id": task_id, "message": "Task not found"},
                        task_id,
                        {"stage": "not_found"},
                    )
                )
                break

            task = agent_router._tasks[task_id]

            # Send current status
            meta = {
                "stage": task.get("status", "unknown"),
                "stale": False,
                "reconnecting": False,
            }

            payload = {
                "task_id": task_id,
                "status": task.get("status", "unknown"),
                "progress": _calculate_progress(task),
                "current_stage": task.get("status", "unknown"),
                "execution_log": task.get("execution_log", [])[
                    -5:
                ],  # Last 5 log entries
                "verification": task.get("verification"),
                "repairs_count": len(task.get("repairs", [])),
            }

            await websocket.send_json(
                _create_ws_message("task_update", payload, task_id, meta)
            )

            # Close if task is complete
            if task.get("status") in ["completed", "failed"]:
                final_payload = {
                    "task_id": task_id,
                    "status": task.get("status"),
                    "verification": task.get("verification"),
                    "repairs": task.get("repairs", []),
                    "report": task.get("report"),
                    "total_time": (
                        task.get("plan", {}).get("total_time", 0)
                        if task.get("plan")
                        else 0
                    ),
                }
                await websocket.send_json(
                    _create_ws_message(
                        (
                            "task_complete"
                            if task.get("status") == "completed"
                            else "task_failed"
                        ),
                        final_payload,
                        task_id,
                        {"stage": task.get("status"), "final": True},
                    )
                )
                break

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)


def _calculate_progress(task: dict) -> float:
    """Calculate task progress based on status."""
    status_progress = {
        "planning": 0.1,
        "coding": 0.2,
        "executing": 0.4,
        "verifying": 0.6,
        "reporting": 0.8,
        "completed": 1.0,
        "failed": 1.0,
    }
    return status_progress.get(task.get("status", "planning"), 0.0)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "service-aware-energy-agents"}


@app.get("/ready")
async def ready_check():
    """Readiness check endpoint."""
    return {"status": "ready", "service": "service-aware-energy-agents"}
