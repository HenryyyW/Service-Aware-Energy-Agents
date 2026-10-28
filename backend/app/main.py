"""FastAPI application entry point."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio

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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """General WebSocket endpoint."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for testing
            await websocket.send_json({"type": "echo", "payload": json.loads(data)})
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/simulation/{run_id}")
async def websocket_simulation(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time simulation updates."""
    await manager.connect(websocket, run_id)
    try:
        while True:
            # Keep connection alive, send periodic updates if simulation is running
            await asyncio.sleep(1)
            if run_id in simulations._runs:
                run = simulations._runs[run_id]
                if run["status"] == "running":
                    await websocket.send_json({
                        "type": "simulation_update",
                        "payload": {
                            "run_id": run_id,
                            "status": run["status"],
                            "current_step": run.get("current_step", 0),
                            "total_steps": run.get("total_steps", 0),
                            "progress": run.get("current_step", 0) / max(run.get("total_steps", 1), 1),
                        }
                    })
    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "service-aware-energy-agents"}