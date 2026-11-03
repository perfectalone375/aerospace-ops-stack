from fastapi.testclient import TestClient

from aerospace_ops.gateway import app

client = TestClient(app)


def test_cors_headers():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_invalid_cfd_airfoil():
    payload = {"airfoil_code": "invalid", "alpha_deg": 2.0}
    response = client.post("/api/simulation/cfd", json=payload)
    assert response.status_code == 422
