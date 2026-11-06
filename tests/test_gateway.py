from fastapi.testclient import TestClient

from aerospace_ops.gateway import app

client = TestClient(app)


def test_system_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["services"]["gateway"] == "UP"


def test_flight_simulation_endpoint():
    payload = {
        "initial_mass_kg": 45.0,
        "dry_mass_kg": 25.0,
        "thrust_n": 2200.0,
        "burn_time_s": 3.0,
        "drag_area_m2": 0.030,
    }
    response = client.post("/api/simulation/flight", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["apogee_m"] > 1000.0
    assert data["max_mach"] > 0.40
    assert len(data["trajectory"]) > 10


def test_orbit_prediction_endpoint():
    payload = {"norad_cat_id": 25544, "observer_lat_deg": 17.385, "observer_lon_deg": 78.486}
    response = client.post("/api/simulation/orbit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["satellite"] == "ISS (ZARYA)"
    assert data["altitude_km"] > 400.0
    assert len(data["ground_track"]) == 10


def test_cfd_surrogate_endpoint():
    payload = {"airfoil_code": "2412", "alpha_deg": 5.0, "reynolds": 1e6}
    response = client.post("/api/simulation/cfd", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["cl"] > 0.6
    assert data["cd"] > 0.008
    assert len(data["cp_distribution"]["x"]) == 21


def test_benchmarks_endpoint():
    response = client.get("/api/benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert len(data["leaderboard"]) == 5
    assert data["leaderboard"][0]["pass_rate"] == 100.0


def test_root_dashboard_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "AeroOps Mission Control" in response.text


def test_orbital_transfer_endpoint():
    payload = {"r1_km": 6700.0, "r2_km": 42164.0, "inclination_deg": 28.5}
    response = client.post("/api/simulation/transfer", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_delta_v_km_s"] > 3.5
    assert data["transfer_duration_hours"] > 5.0


def test_compressible_gas_endpoint():
    payload = {"mach": 2.0, "gamma": 1.4}
    response = client.post("/api/simulation/compressible", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["t0_over_t"] == 1.8
    assert data["normal_shock"]["mach2"] < 1.0
