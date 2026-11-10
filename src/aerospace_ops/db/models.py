"""
Database domain models and dataclass records for telemetry and AI evaluation persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SimulationRunRecord:
    """Record of an executed flight, orbit, or multi-disciplinary aerospace simulation."""

    run_uuid: str
    mission_name: str
    status: str
    apogee_km: float
    max_mach: float
    max_q_kpa: float
    delta_v_m_s: float
    duration_s: float
    payload_json: str = "{}"
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_uuid": self.run_uuid,
            "mission_name": self.mission_name,
            "status": self.status,
            "apogee_km": self.apogee_km,
            "max_mach": self.max_mach,
            "max_q_kpa": self.max_q_kpa,
            "delta_v_m_s": self.delta_v_m_s,
            "duration_s": self.duration_s,
            "payload_json": self.payload_json,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass
class TelemetryEventRecord:
    """Discrete flight staging or ground station tracking telemetry event."""

    run_id: int
    event_time_s: float
    event_name: str
    altitude_m: float
    velocity_m_s: float
    stage_number: int = 1
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "event_time_s": self.event_time_s,
            "event_name": self.event_name,
            "altitude_m": self.altitude_m,
            "velocity_m_s": self.velocity_m_s,
            "stage_number": self.stage_number,
        }


@dataclass
class AIEvaluationRecord:
    """Execution record for Handshake AI / SWE-bench code evaluation tasks."""

    task_id: str
    model_name: str
    is_resolved: bool
    fail_to_pass_score: str
    pass_to_pass_score: str
    execution_time_ms: float
    candidate_patch: str = ""
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "model_name": self.model_name,
            "is_resolved": self.is_resolved,
            "fail_to_pass_score": self.fail_to_pass_score,
            "pass_to_pass_score": self.pass_to_pass_score,
            "execution_time_ms": self.execution_time_ms,
            "candidate_patch": self.candidate_patch,
            "timestamp_utc": self.timestamp_utc,
        }
