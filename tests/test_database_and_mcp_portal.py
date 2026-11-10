"""
Unit and integration tests for SQLite persistence, MCP Portal, and Handshake AI benchmarks.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from aerospace_ops.db import (
    AIEvaluationRecord,
    DatabaseManager,
    SimulationRunRecord,
    TelemetryEventRecord,
)
from aerospace_ops.gateway import app
from aerospace_ops.handshake import HANDSHAKE_TASKS, evaluate_handshake_candidate_patch
from aerospace_ops.mcp import MCPPortal

# ==============================================================================
# DatabaseManager Unit Tests
# ==============================================================================


def test_database_manager_in_memory_crud():
    """Test SQLite DatabaseManager initialization, atomic insertion, and querying."""
    db = DatabaseManager(":memory:")

    run_uuid = str(uuid.uuid4())
    run = SimulationRunRecord(
        run_uuid=run_uuid,
        mission_name="Sounding Rocket Alpha",
        status="COMPLETED",
        apogee_km=18.45,
        max_mach=2.85,
        max_q_kpa=62.4,
        delta_v_m_s=1650.0,
        duration_s=240.0,
        payload_json='{"experiment": "atmospheric_spectroscopy"}',
    )
    events = [
        TelemetryEventRecord(
            run_id=0,
            event_time_s=0.0,
            event_name="Ignition",
            altitude_m=0.0,
            velocity_m_s=0.0,
            stage_number=1,
        ),
        TelemetryEventRecord(
            run_id=0,
            event_time_s=15.2,
            event_name="Max-Q",
            altitude_m=9200.0,
            velocity_m_s=710.0,
            stage_number=1,
        ),
        TelemetryEventRecord(
            run_id=0,
            event_time_s=85.0,
            event_name="Apogee",
            altitude_m=18450.0,
            velocity_m_s=0.0,
            stage_number=1,
        ),
    ]

    run_id = db.save_simulation_run(run, events)
    assert run_id > 0

    fetched = db.get_simulation_run(run_id)
    assert fetched is not None
    assert fetched["run_uuid"] == run_uuid
    assert fetched["mission_name"] == "Sounding Rocket Alpha"
    assert fetched["apogee_km"] == 18.45
    assert len(fetched["telemetry_events"]) == 3
    assert fetched["telemetry_events"][1]["event_name"] == "Max-Q"
    assert fetched["payload"]["experiment"] == "atmospheric_spectroscopy"

    all_runs = db.list_simulation_runs(limit=10)
    assert len(all_runs) == 1
    assert all_runs[0]["id"] == run_id

    # Test missing run returns None
    assert db.get_simulation_run(999999) is None

    # Test clear_all
    db.clear_all()
    assert len(db.list_simulation_runs()) == 0


def test_database_ai_evaluation_leaderboard():
    """Test AI evaluation persistence and SQL leaderboard aggregation."""
    db = DatabaseManager(":memory:")

    evals = [
        AIEvaluationRecord("AERO-001", "Claude-3.5-Sonnet", True, "2/2", "2/2", 14.5),
        AIEvaluationRecord("AERO-002", "Claude-3.5-Sonnet", True, "2/2", "2/2", 12.0),
        AIEvaluationRecord("AERO-001", "GPT-4o", True, "2/2", "2/2", 18.2),
        AIEvaluationRecord("AERO-002", "GPT-4o", False, "0/2", "2/2", 16.0),
    ]
    for ev in evals:
        db.save_ai_evaluation(ev)

    eval_list = db.list_ai_evaluations(limit=10)
    assert len(eval_list) == 4

    leaderboard = db.get_evaluation_leaderboard()
    assert len(leaderboard) == 2

    claude = next(m for m in leaderboard if m["model_name"] == "Claude-3.5-Sonnet")
    assert claude["total_evaluations"] == 2
    assert claude["resolved_tasks"] == 2
    assert claude["pass_rate_percent"] == 100.0

    gpt4 = next(m for m in leaderboard if m["model_name"] == "GPT-4o")
    assert gpt4["total_evaluations"] == 2
    assert gpt4["resolved_tasks"] == 1
    assert gpt4["pass_rate_percent"] == 50.0


# ==============================================================================
# Model Context Protocol (MCP) Portal Tests
# ==============================================================================


def test_mcp_portal_list_tools():
    """Verify registered MCP tool definitions and schemas."""
    tools = MCPPortal.list_tools()
    assert len(tools) >= 6
    names = {t["name"] for t in tools}
    assert "simulate_staged_rocket" in names
    assert "propagate_attitude_quaternions" in names
    assert "calculate_oblique_shock" in names
    assert "predict_transonic_divergence" in names
    assert "calculate_bielliptic_transfer" in names
    assert "evaluate_handshake_ai_task" in names


def test_mcp_portal_invocations():
    """Verify tool invocations across physics calculation engines."""
    # 1. Supersonic oblique shock
    shock_res = MCPPortal.invoke_tool(
        "calculate_oblique_shock",
        {"mach1": 2.5, "theta_deg": 12.0, "gamma": 1.4},
    )
    assert shock_res["tool"] == "calculate_oblique_shock"
    assert shock_res["mach1"] == 2.5
    assert shock_res["theta_deg"] == 12.0
    assert shock_res["beta_deg"] > 12.0
    assert shock_res["p2_over_p1"] > 1.0

    # 2. Transonic divergence
    cd_res = MCPPortal.invoke_tool(
        "predict_transonic_divergence",
        {"mach": 0.82, "cl": 0.25},
    )
    assert cd_res["tool"] == "predict_transonic_divergence"
    assert "critical_mach" in cd_res

    # 3. Bi-elliptic transfer
    trans_res = MCPPortal.invoke_tool(
        "calculate_bielliptic_transfer",
        {"r1_km": 6700.0, "r2_km": 105000.0, "rb_km": 210000.0},
    )
    assert trans_res["tool"] == "calculate_bielliptic_transfer"
    assert trans_res["total_delta_v_km_s"] > 0

    # 4. Unknown tool error handling
    with pytest.raises(ValueError, match="Unknown MCP tool"):
        MCPPortal.invoke_tool("non_existent_tool", {})


# ==============================================================================
# Handshake AI Benchmark Suite Tests
# ==============================================================================


def test_handshake_ai_registry_and_evaluation():
    """Verify all 8 Handshake challenge tasks and test harness resolution."""
    assert len(HANDSHAKE_TASKS) == 8
    task_ids = [t["task_id"] for t in HANDSHAKE_TASKS]
    assert task_ids == [f"AERO-00{i}" for i in range(1, 9)]

    # Successful patch for AERO-001 (tanh bridge)
    valid_patch = "def transonic_drag(mach): return 0.25 + 0.35 * math.tanh(abs(mach - 1.0) / 0.1)"
    res_pass = evaluate_handshake_candidate_patch("AERO-001", valid_patch, "Sonnet-Agent")
    assert res_pass["is_resolved"] is True
    assert res_pass["status"] == "RESOLVED"
    assert res_pass["fail_to_pass_score"] == "2/2"

    # Failing patch for AERO-001 (missing hyperbolic tangent bridge)
    failing_patch = "def drag(mach): return 0.1 * mach"
    res_fail = evaluate_handshake_candidate_patch("AERO-001", failing_patch, "Baseline-Agent")
    assert res_fail["is_resolved"] is False
    assert res_fail["status"] == "FAILED"
    assert res_fail["fail_to_pass_score"] == "0/2"


# ==============================================================================
# Gateway API Integration Tests
# ==============================================================================


client = TestClient(app)


def test_gateway_health_reports_database_and_mcp():
    """Verify health endpoint surfaces persistent DB, MCP portal, and Handshake evaluator."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    services = data["services"]
    assert services["database"] == "CONNECTED"
    assert services["mcp_portal"] == "READY"
    assert services["handshake_evaluator"] == "READY"


def test_gateway_database_endpoints():
    """Test REST API persistence lifecycle for simulation runs and telemetry."""
    payload = {
        "name": "Sounding Rocket Orbit Insertion",
        "status": "COMPLETED",
        "apogee_km": 145.2,
        "max_mach": 4.15,
        "max_q_kpa": 52.8,
        "delta_v_m_s": 2400.0,
        "duration_s": 320.0,
        "payload": {"scientific_instrument": "Magnetometer"},
        "events": [
            {
                "name": "Stage 1 Separation",
                "time_s": 45.0,
                "alt_m": 35000.0,
                "vel_m_s": 1420.0,
                "stage": 1,
            },
            {
                "name": "Apogee Coast",
                "time_s": 180.0,
                "alt_m": 145200.0,
                "vel_m_s": 450.0,
                "stage": 2,
            },
        ],
    }
    create_resp = client.post("/api/db/runs", json=payload)
    assert create_resp.status_code == 200
    res_data = create_resp.json()
    assert res_data["status"] == "SAVED"
    run_id = res_data["run_id"]

    # Get single run
    get_resp = client.get(f"/api/db/runs/{run_id}")
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["mission_name"] == "Sounding Rocket Orbit Insertion"
    assert run_data["apogee_km"] == 145.2
    assert len(run_data["telemetry_events"]) == 2

    # List runs
    list_resp = client.get("/api/db/runs?limit=5")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] >= 1

    # Missing run 404
    missing_resp = client.get("/api/db/runs/99999999")
    assert missing_resp.status_code == 404


def test_gateway_mcp_endpoints():
    """Test MCP tool catalog discovery and remote invocation."""
    tools_resp = client.get("/api/mcp/tools")
    assert tools_resp.status_code == 200
    tools_data = tools_resp.json()
    assert tools_data["count"] >= 6

    # Invoke tool via API
    invoke_resp = client.post(
        "/api/mcp/invoke",
        json={
            "tool_name": "calculate_oblique_shock",
            "arguments": {"mach1": 2.0, "theta_deg": 10.0},
        },
    )
    assert invoke_resp.status_code == 200
    inv_data = invoke_resp.json()
    assert inv_data["status"] == "SUCCESS"
    assert inv_data["result"]["beta_deg"] > 10.0

    # Invalid tool 400
    bad_invoke = client.post(
        "/api/mcp/invoke",
        json={"tool_name": "invalid_tool_name", "arguments": {}},
    )
    assert bad_invoke.status_code == 400


def test_gateway_handshake_evaluation_and_leaderboard():
    """Test Handshake AI task enumeration, candidate patch evaluation, and DB leaderboard."""
    # List tasks
    tasks_resp = client.get("/api/handshake/tasks")
    assert tasks_resp.status_code == 200
    assert tasks_resp.json()["count"] == 8

    # Evaluate candidate patch
    eval_resp = client.post(
        "/api/handshake/evaluate",
        json={
            "task_id": "AERO-006",
            "patch_text": "def fix_gimbal_lock(q): return [x / 0.999999 for x in q]",
            "model_name": "Test-Agent-v2",
        },
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["status"] == "RESOLVED"
    assert eval_data["is_resolved"] is True
    assert "evaluation_id" in eval_data

    # Check leaderboard reflects new evaluation
    lead_resp = client.get("/api/db/leaderboard")
    assert lead_resp.status_code == 200
    lead_data = lead_resp.json()
    models = [m["model_name"] for m in lead_data["leaderboard"]]
    assert "Test-Agent-v2" in models
