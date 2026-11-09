"""
Integration test for full end-to-end aerospace mission simulation.
"""

from aerospace_ops.mission import execute_full_aerospace_mission


def test_full_mission_orchestration():
    result = execute_full_aerospace_mission()

    assert result["mission_status"] == "SUCCESS"
    assert result["propulsion"]["c_star_m_s"] > 1000.0
    assert result["propulsion"]["nozzle_expansion_ratio"] > 1.0
    assert result["flight_dynamics"]["apogee_km"] > 100.0  # Above Karman line
    assert result["flight_dynamics"]["max_mach"] > 5.0  # Hypersonic
    assert len(result["flight_dynamics"]["staging_events"]) >= 4
    assert result["aerodynamics"]["cl"] > 0.5
    assert result["aerodynamics"]["ld_ratio"] > 10.0
    assert result["orbital_transfer"]["total_delta_v_m_s"] > 50.0
