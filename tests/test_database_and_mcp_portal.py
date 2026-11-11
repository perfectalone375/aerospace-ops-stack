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
    assert len(tools) >= 7
    names = {t["name"] for t in tools}
    assert "simulate_staged_rocket" in names
    assert "propagate_attitude_quaternions" in names
    assert "calculate_oblique_shock" in names
    assert "predict_transonic_divergence" in names
    assert "calculate_bielliptic_transfer" in names
    assert "evaluate_handshake_ai_task" in names
    assert "simulate_rocket_nozzle_cfd" in names


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

    # 4. Rocket Nozzle CFD simulation
    nozzle_res = MCPPortal.invoke_tool(
        "simulate_rocket_nozzle_cfd",
        {"propellant": "HYDROLOX", "chamber_pressure_mpa": 10.0, "expansion_ratio": 16.0},
    )
    assert nozzle_res["tool"] == "simulate_rocket_nozzle_cfd"
    assert nozzle_res["isp_vacuum_s"] > 380.0
    assert nozzle_res["exit_mach"] > 3.0

    # 5. Unknown tool error handling
    with pytest.raises(ValueError, match="Unknown MCP tool"):
        MCPPortal.invoke_tool("non_existent_tool", {})


# ==============================================================================
# Handshake AI Benchmark Suite Tests
# ==============================================================================


def test_handshake_ai_registry_and_evaluation():
    """Verify all 10 Handshake tasks fail on buggy starter code and pass on gold fixes."""
    assert len(HANDSHAKE_TASKS) == 10
    task_ids = [t["task_id"] for t in HANDSHAKE_TASKS]
    assert task_ids == [f"AERO-{i:03d}" for i in range(1, 11)]

    for task in HANDSHAKE_TASKS:
        tid = task["task_id"]
        res_buggy = evaluate_handshake_candidate_patch(
            tid, task["starter_buggy_code"], "Buggy-Baseline"
        )
        assert res_buggy["is_resolved"] is False, f"{tid} buggy code should fail"
        assert res_buggy["status"] == "FAILED"

        res_gold = evaluate_handshake_candidate_patch(
            tid, task["reference_solution"], "Gold-Baseline"
        )
        assert res_gold["is_resolved"] is True, f"{tid} gold code failed: {res_gold}"
        assert res_gold["status"] == "RESOLVED"
        assert res_gold["sandbox_engine"] == "isolated-subprocess-ast-v2"


def test_handshake_unified_diff_and_sandbox_security():
    """Verify unified diff extraction, syntax errors, disallowed imports, and infinite-loop timeouts."""
    diff_patch = (
        "--- a/aero.py\n"
        "+++ b/aero.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def burn_propellant_step(propellant_mass_kg: float, mdot_kg_s: float, dt_s: float) -> float:\n"
        "-    return propellant_mass_kg - mdot_kg_s * dt_s\n"
        "+    burned = min(propellant_mass_kg, max(0.0, mdot_kg_s * dt_s))\n"
        "+    return max(0.0, propellant_mass_kg - burned)\n"
    )
    res_diff = evaluate_handshake_candidate_patch("AERO-005", diff_patch, "Diff-Agent")
    assert res_diff["status"] == "RESOLVED"
    assert res_diff["is_resolved"] is True

    res_syntax = evaluate_handshake_candidate_patch("AERO-001", "def broken(:", "Syntax-Agent")
    assert res_syntax["status"] == "SYNTAX_ERROR"
    assert res_syntax["is_resolved"] is False

    res_sec = evaluate_handshake_candidate_patch(
        "AERO-001", "import os\ndef f(m):\n    return 0.5\n", "Malicious-Agent"
    )
    assert res_sec["status"] == "SECURITY_VIOLATION"
    assert res_sec["is_resolved"] is False

    res_timeout = evaluate_handshake_candidate_patch(
        "AERO-001",
        "def correct_sonic_singularity(m):\n    while True:\n        pass\n",
        "Timeout-Agent",
    )
    assert res_timeout["status"] == "TIMEOUT"
    assert res_timeout["is_resolved"] is False


# ==============================================================================
# Gateway API Integration Tests
# ==============================================================================


client = TestClient(app)


def test_gateway_health_reports_database_and_mcp():
    """Verify health endpoint surfaces persistent DB, MCP JSON-RPC, and Handshake evaluator."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    services = data["services"]
    assert services["database"] == "CONNECTED"
    assert services["mcp_portal"] == "READY"
    assert services["mcp_jsonrpc_transport"] == "READY"
    assert services["handshake_evaluator"] == "isolated-subprocess-ast-v2"


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
    tasks_resp = client.get("/api/handshake/tasks")
    assert tasks_resp.status_code == 200
    data = tasks_resp.json()
    assert data["count"] == 10

    nozzle_resp = client.post(
        "/api/simulation/nozzle-cfd",
        json={"propellant": "METHALOX", "chamber_pressure_mpa": 10.0, "expansion_ratio": 16.0},
    )
    assert nozzle_resp.status_code == 200
    nozzle_data = nozzle_resp.json()
    assert nozzle_data["exit_mach"] > 3.0
    assert len(nozzle_data["axial_profile"]) == 36

    aero6_gold = next(t for t in data["tasks"] if t["task_id"] == "AERO-006")["reference_solution"]

    eval_resp = client.post(
        "/api/handshake/evaluate",
        json={
            "task_id": "AERO-006",
            "patch_text": aero6_gold,
            "model_name": "Test-Agent-v2",
        },
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["status"] == "RESOLVED"
    assert eval_data["is_resolved"] is True
    assert "evaluation_id" in eval_data

    lead_resp = client.get("/api/db/leaderboard")
    assert lead_resp.status_code == 200
    lead_data = lead_resp.json()
    models = [m["model_name"] for m in lead_data["leaderboard"]]
    assert "Test-Agent-v2" in models


def test_mcp_jsonrpc_server_protocol():
    """Test native MCP JSON-RPC 2.0 HTTP transport across initialize, tools, and resources."""
    init_resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp.status_code == 200
    assert init_resp.json()["result"]["protocolVersion"] == "2024-11-05"

    notif_resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert notif_resp.status_code == 204

    tools_resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert tools_resp.status_code == 200
    assert len(tools_resp.json()["result"]["tools"]) >= 6

    call_resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "calculate_oblique_shock",
                "arguments": {"mach1": 2.0, "theta_deg": 10.0},
            },
        },
    )
    assert call_resp.status_code == 200
    call_result = call_resp.json()["result"]
    assert call_result["isError"] is False
    assert "beta_deg" in call_result["content"][0]["text"]

    res_list = client.post("/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
    assert res_list.status_code == 200
    uris = {r["uri"] for r in res_list.json()["result"]["resources"]}
    assert "aeroops://handshake/tasks" in uris
    assert "aeroops://db/runs" in uris

    res_read = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "aeroops://handshake/tasks"},
        },
    )
    assert res_read.status_code == 200
    assert "AERO-001" in res_read.json()["result"]["contents"][0]["text"]

    unknown_resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 6, "method": "unknown/method"})
    assert unknown_resp.json()["error"]["code"] == -32601


def test_live_prometheus_metrics_increment():
    """Verify HTTP telemetry middleware dynamically increments /metrics counters."""
    client.get("/api/health")
    m1 = client.get("/metrics").text
    client.get("/api/health")
    m2 = client.get("/metrics").text

    assert 'gateway_requests_total{handler="/api/health",status="200"}' in m2
    # Extract integer counts for /api/health
    line1 = next(line for line in m1.splitlines() if 'handler="/api/health",status="200"' in line)
    line2 = next(line for line in m2.splitlines() if 'handler="/api/health",status="200"' in line)
    assert int(line2.split()[-1]) > int(line1.split()[-1])
