"""FastAPI application entry point."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
import uuid
from datetime import datetime

from app.routers import scenarios, simulations, agent, reports, compare, network


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Service-Aware Energy Agents API",
    description="API for renewable energy community simulation with grid constraints",
    version="0.1.0",
    lifespan=lifespan,
)

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


def _create_ws_message(msg_type: str, payload: dict, run_id: str, meta: dict = None) -> dict:
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
            await websocket.send_json(_create_ws_message("echo", json.loads(data), "general"))
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/simulation/{run_id}")
async def websocket_simulation(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time simulation updates with stale-data protection."""
    await manager.connect(websocket, run_id)
    
    # Send initial connection message with meta
    await websocket.send_json(_create_ws_message(
        "connected",
        {"run_id": run_id, "message": "WebSocket connected"},
        run_id,
        {"stage": "connected"}
    ))
    
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
                    await websocket.send_json(_create_ws_message(
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
                        meta
                    ))
                elif run["status"] in ["completed", "failed", "cancelled"]:
                    # Send final update then close
                    meta = {
                        "stage": run.get("stage", run["status"]),
                        "stale": False,
                        "reconnecting": False,
                    }
                    await websocket.send_json(_create_ws_message(
                        "simulation_complete" if run["status"] == "completed" else "simulation_error",
                        {
                            "run_id": run_id,
                            "status": run["status"],
                            "outcome_sentence": run.get("outcome_sentence"),
                            "error": run.get("error"),
                        },
                        run_id,
                        meta
                    ))
                    break
    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "service-aware-energy-agents"}