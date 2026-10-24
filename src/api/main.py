"""FastAPI application for Service-Aware Energy Agents."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.api.routes import network, simulation, scenarios, runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting Service-Aware Energy Agents API...")
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="Service-Aware Energy Agents API",
    description="API for Spatio-Temporal Virtual Community Simulator for Renewable Energy Communities",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(network.router, prefix="/api/network", tags=["network"])
app.include_router(simulation.router, prefix="/api/simulation", tags=["simulation"])
app.include_router(runs.runs_router, prefix="/api/simulations", tags=["runs"])
app.include_router(runs.reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(runs.comparison_router, prefix="/api/compare", tags=["comparison"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Service-Aware Energy Agents API",
        "version": "1.0.0",
        "description": "API for Spatio-Temporal Virtual Community Simulator"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)