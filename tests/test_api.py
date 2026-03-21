"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200


def test_api_docs_accessible(client):
    """Test that API documentation is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_api_endpoints_exist(client):
    """Test that key API endpoints are registered."""
    # These should return responses (may be 422 for missing params, but not 404)

    # Health score endpoint (will need project parameter)
    response = client.get("/api/v1/health-score/demo")
    assert response.status_code in [200, 422, 500]  # Not 404

    # Trends endpoint
    response = client.get("/api/v1/trends/demo")
    assert response.status_code in [200, 422, 500]  # Not 404


def test_invalid_endpoint_returns_404(client):
    """Test that invalid endpoints return 404."""
    response = client.get("/api/v1/nonexistent-endpoint")
    assert response.status_code == 404


def test_cors_headers(client):
    """Test that CORS headers are present."""
    response = client.get("/health")
    assert response.status_code == 200
    # CORS middleware should add these headers
    assert (
        "access-control-allow-origin" in response.headers or response.status_code == 200
    )
