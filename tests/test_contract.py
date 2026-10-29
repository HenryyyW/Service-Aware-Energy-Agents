"""OpenAPI contract tests - validates that API responses match the OpenAPI schema."""
import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_module

app = main_module.app
client = TestClient(app)


def test_health_endpoint():
    """Test health endpoint returns correct format."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "service-aware-energy-agents"


def test_openapi_endpoint():
    """Test OpenAPI schema endpoint is accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert data["info"]["title"] == "Service-Aware Energy Agents API"


# Scenario endpoints
def test_scenarios_list():
    """Test scenarios list endpoint."""
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_simulations_list():
    """Test simulations list endpoint."""
    response = client.get("/api/simulations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_network_geometry():
    """Test network geometry endpoint."""
    response = client.get("/api/network/geometry", params={"scenario_id": "scenario_a"})
    # Should return 200 or 404 (not 500)
    assert response.status_code in [200, 404]


def test_agent_tasks():
    """Test agent tasks endpoint."""
    response = client.get("/api/agent/tasks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_comparison_endpoint():
    """Test comparison endpoint."""
    response = client.get("/api/compare", params={"run_id_a": "test_a", "run_id_b": "test_b"})
    # Should return 404 for non-existent runs, not 500
    assert response.status_code in [404, 200]


def test_reports_endpoint():
    """Test reports endpoint."""
    response = client.get("/api/reports/test_run")
    # Should return 404 for non-existent run, not 500
    assert response.status_code in [404, 200]


# OpenAPI schema validation test
def test_openapi_schema_valid():
    """Test that OpenAPI schema is valid and accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data
    assert "components" in data
    # Verify key endpoints exist
    assert "/api/scenarios" in data["paths"]
    assert "/api/simulations" in data["paths"]
    assert "/api/reports/{run_id}" in data["paths"]
    assert "/api/compare" in data["paths"]
    assert "/api/network/geometry" in data["paths"]
    assert "/api/agent/tasks" in data["paths"]


def test_openapi_components_schemas():
    """Test that key schemas are defined in OpenAPI."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    components = data.get("components", {})
    schemas = components.get("schemas", {})
    # Verify key schemas exist
    assert "SimulationRun" in schemas
    assert "SimulationCreateRequest" in schemas
    assert "ReportResponse" in schemas
    assert "ComparisonResult" in schemas
    assert "NetworkGeometryResponse" in schemas
    assert "AgentTask" in schemas
    assert "AgentTaskCreate" in schemas


if __name__ == "__main__":
    pytest.main([__file__, "-v"])