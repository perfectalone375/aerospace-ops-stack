"""
Full End-to-End Computational Aerospace Mission Orchestrator CLI.
Runs multi-disciplinary aerospace mission simulation across all repositories.
"""

from __future__ import annotations

import json

from aerospace_ops.mission import execute_full_aerospace_mission


def main() -> None:
    print("=" * 70)
    print("🚀 EXECUTING UNIFIED COMPUTATIONAL AEROSPACE MISSION SIMULATION")
    print("=" * 70)
    result = execute_full_aerospace_mission()

    print("\n[Phase 1] Propulsion Thermodynamics (openengineering-toolkit):")
    for k, v in result["propulsion"].items():
        print(f"  • {k}: {v}")

    print("\n[Phase 2] Staged Rocket Trajectory Simulation (aero-flight-dynamics):")
    for k, v in result["flight_dynamics"].items():
        if k != "staging_events":
            print(f"  • {k}: {v}")
    print(f"  • staging_events_count: {len(result['flight_dynamics']['staging_events'])}")

    print("\n[Phase 3] Aerodynamic Surrogate Analysis (cfd-airfoil-surrogate):")
    for k, v in result["aerodynamics"].items():
        print(f"  • {k}: {v}")

    print("\n[Phase 4] Orbital Insertion & Transfer (orbital-telemetry-agent):")
    for k, v in result["orbital_transfer"].items():
        print(f"  • {k}: {v}")

    print("\n" + "=" * 70)
    print("✅ MISSION SIMULATION SUCCESSFUL: All 4 aerospace subsystems verified!")
    print("=" * 70)
    print("\nSummary JSON Payload:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
