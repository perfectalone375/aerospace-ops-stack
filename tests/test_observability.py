"""
Tests for cloud-native Prometheus observability metrics and mission control UI.
"""

from fastapi.testclient import TestClient

from aerospace_ops.gateway import app

client = TestClient(app)


def test_prometheus_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text

    assert "# HELP gateway_requests_total" in body
    assert "# TYPE gateway_requests_total counter" in body
    assert "gateway_requests_total" in body
    assert "aerospace_service_up" in body
    assert "simulation_execution_seconds" in body


def test_static_dashboard_contains_mission_orchestrator():
    response = client.get("/")
    assert response.status_code == 200
    assert "Unified Multi-Disciplinary Aerospace Mission Orchestrator" in response.text
    assert "runFullMission" in response.text
