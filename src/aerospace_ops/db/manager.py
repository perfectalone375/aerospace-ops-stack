"""
Thread-safe SQLite Database Manager for Aerospace Operations and Handshake AI Benchmarks.
Features ACID transactions, WAL mode, foreign keys, and indexed analytical queries.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import AIEvaluationRecord, SimulationRunRecord, TelemetryEventRecord


class DatabaseManager:
    """Manages SQLite persistence for mission telemetry, flight staging, and AI evaluations."""

    def __init__(self, db_path: str | Path = "aero_ops.db") -> None:
        self.db_path = str(db_path)
        self._shared_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA foreign_keys = ON;")
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create or return a connection with WAL mode and foreign key constraints enabled."""
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_database(self) -> None:
        """Initialize database tables and performance indices if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS simulation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_uuid TEXT UNIQUE NOT NULL,
                    mission_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    apogee_km REAL NOT NULL,
                    max_mach REAL NOT NULL,
                    max_q_kpa REAL NOT NULL,
                    delta_v_m_s REAL NOT NULL,
                    duration_s REAL NOT NULL,
                    payload_json TEXT DEFAULT '{}',
                    timestamp_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    event_time_s REAL NOT NULL,
                    event_name TEXT NOT NULL,
                    altitude_m REAL NOT NULL,
                    velocity_m_s REAL NOT NULL,
                    stage_number INTEGER DEFAULT 1,
                    FOREIGN KEY (run_id) REFERENCES simulation_runs (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ai_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    is_resolved INTEGER NOT NULL,
                    fail_to_pass_score TEXT NOT NULL,
                    pass_to_pass_score TEXT NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    candidate_patch TEXT DEFAULT '',
                    timestamp_utc TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_simulation_timestamp ON simulation_runs(timestamp_utc DESC);
                CREATE INDEX IF NOT EXISTS idx_telemetry_run_id ON telemetry_events(run_id);
                CREATE INDEX IF NOT EXISTS idx_eval_model ON ai_evaluations(model_name);
                CREATE INDEX IF NOT EXISTS idx_eval_task ON ai_evaluations(task_id);
            """)

    def save_simulation_run(
        self,
        run: SimulationRunRecord,
        events: list[TelemetryEventRecord] | None = None,
    ) -> int:
        """Insert a simulation run and optional telemetry events atomically."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO simulation_runs (
                    run_uuid, mission_name, status, apogee_km, max_mach,
                    max_q_kpa, delta_v_m_s, duration_s, payload_json, timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_uuid,
                    run.mission_name,
                    run.status,
                    run.apogee_km,
                    run.max_mach,
                    run.max_q_kpa,
                    run.delta_v_m_s,
                    run.duration_s,
                    run.payload_json,
                    run.timestamp_utc,
                ),
            )
            run_id = cur.lastrowid
            assert run_id is not None

            if events:
                for e in events:
                    cur.execute(
                        """
                        INSERT INTO telemetry_events (
                            run_id, event_time_s, event_name, altitude_m, velocity_m_s, stage_number
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            e.event_time_s,
                            e.event_name,
                            e.altitude_m,
                            e.velocity_m_s,
                            e.stage_number,
                        ),
                    )

            conn.commit()
            return run_id

    def list_simulation_runs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Retrieve recent simulation runs ordered by timestamp."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, run_uuid, mission_name, status, apogee_km, max_mach,
                       max_q_kpa, delta_v_m_s, duration_s, payload_json, timestamp_utc
                FROM simulation_runs
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def get_simulation_run(self, run_id: int) -> dict[str, Any] | None:
        """Retrieve a specific run along with its associated telemetry events."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM simulation_runs WHERE id = ?", (run_id,))
            run_row = cur.fetchone()
            if not run_row:
                return None

            run_dict = dict(run_row)
            try:
                run_dict["payload"] = json.loads(run_dict["payload_json"])
            except json.JSONDecodeError:
                run_dict["payload"] = {}

            cur.execute(
                "SELECT * FROM telemetry_events WHERE run_id = ? ORDER BY event_time_s ASC",
                (run_id,),
            )
            events = [dict(e) for e in cur.fetchall()]
            run_dict["telemetry_events"] = events
            return run_dict

    def save_ai_evaluation(self, record: AIEvaluationRecord) -> int:
        """Record a Handshake AI / SWE-bench model evaluation outcome."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO ai_evaluations (
                    task_id, model_name, is_resolved, fail_to_pass_score,
                    pass_to_pass_score, execution_time_ms, candidate_patch, timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.task_id,
                    record.model_name,
                    1 if record.is_resolved else 0,
                    record.fail_to_pass_score,
                    record.pass_to_pass_score,
                    record.execution_time_ms,
                    record.candidate_patch,
                    record.timestamp_utc,
                ),
            )
            conn.commit()
            record_id = cur.lastrowid
            assert record_id is not None
            return record_id

    def list_ai_evaluations(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent AI evaluations."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, task_id, model_name, is_resolved, fail_to_pass_score,
                       pass_to_pass_score, execution_time_ms, timestamp_utc
                FROM ai_evaluations
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_evaluation_leaderboard(self) -> list[dict[str, Any]]:
        """Compute aggregated model pass rates and latency statistics from evaluation history."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    model_name,
                    COUNT(*) as total_evaluations,
                    SUM(is_resolved) as resolved_tasks,
                    ROUND((CAST(SUM(is_resolved) AS REAL) / COUNT(*)) * 100.0, 2) as pass_rate_percent,
                    ROUND(AVG(execution_time_ms), 2) as mean_latency_ms
                FROM ai_evaluations
                GROUP BY model_name
                ORDER BY pass_rate_percent DESC, total_evaluations DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def clear_all(self) -> None:
        """Clear all records from database tables (useful for test suites)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM telemetry_events;")
            conn.execute("DELETE FROM simulation_runs;")
            conn.execute("DELETE FROM ai_evaluations;")
            conn.commit()
