"""
Handshake AI & SWE-bench Physical Simulation Code Evaluation Engine.
Executes candidate Python patches inside an isolated AST-validated subprocess sandbox
against deterministic fail-to-pass edge cases and pass-to-pass physics invariants.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
import time
from typing import Any

DISALLOWED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "http",
    "urllib",
    "ctypes",
    "importlib",
    "builtins",
    "pickle",
    "marshal",
}

DISALLOWED_CALLS = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "input",
    "breakpoint",
}

HANDSHAKE_TASKS: list[dict[str, Any]] = [
    {
        "task_id": "AERO-001",
        "domain": "Aerodynamics / Compressibility Singularities",
        "title": "Prandtl-Glauert Sonic Singularity Hyperbolic Tangent Bridge",
        "difficulty": "Hard",
        "entry_point": "correct_sonic_singularity",
        "signature": "def correct_sonic_singularity(mach: float) -> float:",
        "problem_statement": (
            "Prandtl-Glauert compressibility correction divides by sqrt(|1 - M^2|), which raises "
            "ZeroDivisionError or diverges to infinity at Mach 1.0. Implement a smooth hyperbolic "
            "tangent (tanh) transonic saturation bridge around Mach 1.0 keeping subsonic (M=0.5) "
            "and supersonic (M=2.0) baseline physics accurate."
        ),
        "fail_to_pass_tests": [
            "test_transonic_drag_saturation_finite",
            "test_transonic_drag_monotonic_continuity",
        ],
        "pass_to_pass_tests": ["test_subsonic_drag_polar", "test_supersonic_wave_drag"],
        "starter_buggy_code": (
            "def correct_sonic_singularity(mach: float) -> float:\n"
            "    # BUG: Raises ZeroDivisionError at mach=1.0 and diverges in transonic regime\n"
            "    return 0.25 / math.sqrt(abs(1.0 - mach**2))\n"
        ),
        "reference_solution": (
            "def correct_sonic_singularity(mach: float) -> float:\n"
            "    denom = abs(1.0 - mach**2)\n"
            "    if 0.85 <= mach <= 1.15:\n"
            "        return 0.25 + 0.55 * (1.0 - math.tanh(denom / 0.15))\n"
            "    return 0.25 / math.sqrt(max(0.05, denom))\n"
        ),
    },
    {
        "task_id": "AERO-002",
        "domain": "Astrodynamics / Coordinate Branch Cuts",
        "title": "Ground Station Zenith Pass Azimuth 360-Degree Angle Unwrapping",
        "difficulty": "Medium",
        "entry_point": "unwrap_azimuth_degrees",
        "signature": "def unwrap_azimuth_degrees(angles_deg: list[float]) -> list[float]:",
        "problem_statement": (
            "Ground station antenna tracking azimuth undergoes a 360-degree branch-cut "
            "discontinuity (e.g., 359.5 deg -> 1.0 deg) during zenith passes. Implement phase "
            "unwrapping so consecutive steps stay continuous within physical slew limits."
        ),
        "fail_to_pass_tests": [
            "test_zenith_pass_azimuth_continuity",
            "test_gimbal_slew_rate_within_limits",
        ],
        "pass_to_pass_tests": [
            "test_horizon_acquisition_elevation",
            "test_sequence_length_preserved",
        ],
        "starter_buggy_code": (
            "def unwrap_azimuth_degrees(angles_deg: list[float]) -> list[float]:\n"
            "    # BUG: Returns wrapped [0, 360) values with massive jump across 0/360 seam\n"
            "    return [float(a) % 360.0 for a in angles_deg]\n"
        ),
        "reference_solution": (
            "def unwrap_azimuth_degrees(angles_deg: list[float]) -> list[float]:\n"
            "    if not angles_deg:\n"
            "        return []\n"
            "    unwrapped = [float(angles_deg[0])]\n"
            "    for angle in angles_deg[1:]:\n"
            "        delta = (float(angle) - unwrapped[-1] + 180.0) % 360.0 - 180.0\n"
            "        unwrapped.append(unwrapped[-1] + delta)\n"
            "    return unwrapped\n"
        ),
    },
    {
        "task_id": "AERO-003",
        "domain": "Computational Fluid Dynamics / Discretization",
        "title": "NACA Airfoil Cosine Clustering Discretization & Kutta Condition",
        "difficulty": "Hard",
        "entry_point": "cosine_panel_spacing",
        "signature": "def cosine_panel_spacing(n_panels: int) -> list[float]:",
        "problem_statement": (
            "Uniform panel discretization under-resolves the leading-edge stagnation suction peak "
            "and trailing-edge Kutta condition. Replace uniform spacing with full cosine clustering "
            "x_i = 0.5 * (1 - cos(pi * i / N)) on [0, 1]."
        ),
        "fail_to_pass_tests": [
            "test_symmetric_cosine_clustering_symmetry",
            "test_kutta_condition_trailing_edge_refinement",
        ],
        "pass_to_pass_tests": [
            "test_normalized_chord_endpoints",
            "test_strict_monotonic_progression",
        ],
        "starter_buggy_code": (
            "def cosine_panel_spacing(n_panels: int) -> list[float]:\n"
            "    # BUG: Uniform spacing lacks LE/TE boundary layer clustering\n"
            "    return [i / n_panels for i in range(n_panels + 1)]\n"
        ),
        "reference_solution": (
            "def cosine_panel_spacing(n_panels: int) -> list[float]:\n"
            "    return [0.5 * (1.0 - math.cos(math.pi * i / n_panels)) for i in range(n_panels + 1)]\n"
        ),
    },
    {
        "task_id": "AERO-004",
        "domain": "Structural Mechanics / Analytical Deflection",
        "title": "Euler-Bernoulli Center-Load Beam Maximum Deflection Coefficient Fix",
        "difficulty": "Medium",
        "entry_point": "euler_bernoulli_center_deflection",
        "signature": (
            "def euler_bernoulli_center_deflection("
            "load_n: float, length_m: float, elastic_modulus_pa: float, inertia_m4: float"
            ") -> float:"
        ),
        "problem_statement": (
            "Euler-Bernoulli simply supported center-load deflection hardcoded an erroneous "
            "denominator coefficient (96 instead of 48). Update formula to P * L^3 / (48 * E * I)."
        ),
        "fail_to_pass_tests": ["test_center_load_max_deflection_exact"],
        "pass_to_pass_tests": [
            "test_linear_load_scaling",
            "test_cubic_span_scaling",
        ],
        "starter_buggy_code": (
            "def euler_bernoulli_center_deflection(\n"
            "    load_n: float, length_m: float, elastic_modulus_pa: float, inertia_m4: float\n"
            ") -> float:\n"
            "    # BUG: Incorrect denominator coefficient 96\n"
            "    return (load_n * (length_m**3)) / (96.0 * elastic_modulus_pa * inertia_m4)\n"
        ),
        "reference_solution": (
            "def euler_bernoulli_center_deflection(\n"
            "    load_n: float, length_m: float, elastic_modulus_pa: float, inertia_m4: float\n"
            ") -> float:\n"
            "    return (load_n * (length_m**3)) / (48.0 * elastic_modulus_pa * inertia_m4)\n"
        ),
    },
    {
        "task_id": "AERO-005",
        "domain": "Propulsion & Ballistics / Mass Depletion",
        "title": "Solid Rocket Motor Burnout Non-Negative Propellant Mass Clamp",
        "difficulty": "Hard",
        "entry_point": "burn_propellant_step",
        "signature": "def burn_propellant_step(propellant_mass_kg: float, mdot_kg_s: float, dt_s: float) -> float:",
        "problem_statement": (
            "Solid rocket motor burn integration yields negative propellant mass when timestep dt "
            "exceeds residual propellant at burnout. Implement non-negative residual burn clamping."
        ),
        "fail_to_pass_tests": [
            "test_motor_burnout_propellant_non_negative",
            "test_zero_propellant_residual_clamp",
        ],
        "pass_to_pass_tests": [
            "test_steady_state_mass_depletion",
            "test_zero_mdot_coast_preservation",
        ],
        "starter_buggy_code": (
            "def burn_propellant_step(propellant_mass_kg: float, mdot_kg_s: float, dt_s: float) -> float:\n"
            "    # BUG: Over-depletes into negative propellant mass when mdot * dt > remaining\n"
            "    return propellant_mass_kg - mdot_kg_s * dt_s\n"
        ),
        "reference_solution": (
            "def burn_propellant_step(propellant_mass_kg: float, mdot_kg_s: float, dt_s: float) -> float:\n"
            "    burned = min(propellant_mass_kg, max(0.0, mdot_kg_s * dt_s))\n"
            "    return max(0.0, propellant_mass_kg - burned)\n"
        ),
    },
    {
        "task_id": "AERO-006",
        "domain": "6-DoF Kinematics / Gimbal Lock Singularities",
        "title": "Euler Angle Extraction Singularity Protection at Pitch +/- 90 Degrees",
        "difficulty": "Hard",
        "entry_point": "euler_from_quaternion",
        "signature": "def euler_from_quaternion(q0: float, q1: float, q2: float, q3: float) -> tuple[float, float, float]:",
        "problem_statement": (
            "Euler angle extraction (roll, pitch, yaw in degrees) from slightly drifted quaternions "
            "at pitch +/- 90 degrees passes |sin_p| > 1.0 into math.asin(), crashing with ValueError. "
            "Normalize quaternion and apply copysign(pi/2, sin_p) gimbal-lock protection."
        ),
        "fail_to_pass_tests": [
            "test_gimbal_lock_singularity_avoidance",
            "test_pitch_90_degree_finite_euler",
        ],
        "pass_to_pass_tests": [
            "test_identity_quaternion_zero_euler",
            "test_nonsingular_roll_extraction",
        ],
        "starter_buggy_code": (
            "def euler_from_quaternion(q0: float, q1: float, q2: float, q3: float) -> tuple[float, float, float]:\n"
            "    # BUG: Unnormalized quaternion + unguarded math.asin() crashes at pitch +/-90 deg\n"
            "    sinp = 2.0 * (q0 * q2 - q3 * q1)\n"
            "    pitch = math.degrees(math.asin(sinp))\n"
            "    roll = math.degrees(math.atan2(2.0 * (q0 * q1 + q2 * q3), 1.0 - 2.0 * (q1**2 + q2**2)))\n"
            "    yaw = math.degrees(math.atan2(2.0 * (q0 * q3 + q1 * q2), 1.0 - 2.0 * (q2**2 + q3**2)))\n"
            "    return (roll, pitch, yaw)\n"
        ),
        "reference_solution": (
            "def euler_from_quaternion(q0: float, q1: float, q2: float, q3: float) -> tuple[float, float, float]:\n"
            "    norm = math.sqrt(q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3)\n"
            "    if norm < 1e-12:\n"
            "        return (0.0, 0.0, 0.0)\n"
            "    q0, q1, q2, q3 = q0 / norm, q1 / norm, q2 / norm, q3 / norm\n"
            "    sinp = 2.0 * (q0 * q2 - q3 * q1)\n"
            "    if abs(sinp) >= 0.999999:\n"
            "        pitch = math.degrees(math.copysign(math.pi / 2.0, sinp))\n"
            "        roll = 0.0\n"
            "        yaw = math.degrees(2.0 * math.atan2(q1, q0) * (-1.0 if sinp < 0 else 1.0))\n"
            "    else:\n"
            "        pitch = math.degrees(math.asin(sinp))\n"
            "        roll = math.degrees(math.atan2(2.0 * (q0 * q1 + q2 * q3), 1.0 - 2.0 * (q1 * q1 + q2 * q2)))\n"
            "        yaw = math.degrees(math.atan2(2.0 * (q0 * q3 + q1 * q2), 1.0 - 2.0 * (q2 * q2 + q3 * q3)))\n"
            "    return (roll, pitch, yaw)\n"
        ),
    },
    {
        "task_id": "AERO-007",
        "domain": "Compressible Fluid Dynamics / Oblique Shock Waves",
        "title": "2D Supersonic Oblique Shock Detachment Boundary Pre-Check",
        "difficulty": "Hard",
        "entry_point": "solve_oblique_shock_beta",
        "signature": "def solve_oblique_shock_beta(mach1: float, theta_deg: float, gamma: float = 1.4) -> float:",
        "problem_statement": (
            "The 2D supersonic oblique shock Theta-Beta-Mach solver fails to detect detached bow "
            "shocks when wedge deflection exceeds maximum attachment angle theta_max. Compute "
            "theta_max via golden-section search, raise ValueError on detachment, and return weak "
            "shock wave angle beta in degrees."
        ),
        "fail_to_pass_tests": [
            "test_oblique_shock_detachment_value_error",
            "test_theta_max_golden_section_bound",
        ],
        "pass_to_pass_tests": [
            "test_weak_oblique_shock_mach2_10deg",
            "test_small_deflection_mach_angle_limit",
        ],
        "starter_buggy_code": (
            "def solve_oblique_shock_beta(mach1: float, theta_deg: float, gamma: float = 1.4) -> float:\n"
            "    # BUG: Always approximates linear angle without solving T-B-M or raising ValueError on detachment\n"
            "    return math.degrees(math.asin(1.0 / mach1)) + theta_deg * 0.9\n"
        ),
        "reference_solution": (
            "def solve_oblique_shock_beta(mach1: float, theta_deg: float, gamma: float = 1.4) -> float:\n"
            "    if mach1 <= 1.0:\n"
            "        raise ValueError('Upstream Mach must exceed 1.0')\n"
            "    mu = math.asin(1.0 / mach1)\n"
            "    def tan_theta(b):\n"
            "        sb = math.sin(b)\n"
            "        num = 2.0 * (1.0 / math.tan(b)) * ((mach1 * sb) ** 2 - 1.0)\n"
            "        den = (mach1**2) * (gamma + math.cos(2.0 * b)) + 2.0\n"
            "        return num / den\n"
            "    phi = (math.sqrt(5.0) - 1.0) / 2.0\n"
            "    a, b = mu, math.pi / 2.0 - 1e-4\n"
            "    for _ in range(50):\n"
            "        c = b - phi * (b - a)\n"
            "        d = a + phi * (b - a)\n"
            "        if tan_theta(c) > tan_theta(d):\n"
            "            b = d\n"
            "        else:\n"
            "            a = c\n"
            "    beta_peak = 0.5 * (a + b)\n"
            "    theta_max_deg = math.degrees(math.atan(tan_theta(beta_peak)))\n"
            "    if theta_deg > theta_max_deg:\n"
            "        raise ValueError(f'Detached bow shock: theta {theta_deg} > theta_max {theta_max_deg:.2f}')\n"
            "    target = math.tan(math.radians(theta_deg))\n"
            "    lo, hi = mu + 1e-6, beta_peak\n"
            "    for _ in range(60):\n"
            "        mid = 0.5 * (lo + hi)\n"
            "        if tan_theta(mid) < target:\n"
            "            lo = mid\n"
            "        else:\n"
            "            hi = mid\n"
            "    return math.degrees(0.5 * (lo + hi))\n"
        ),
    },
    {
        "task_id": "AERO-008",
        "domain": "Astrodynamics / Orbital Transfers",
        "title": "3-Impulse Bi-Elliptic Orbit Transfer Efficiency Crossover Criterion",
        "difficulty": "Medium",
        "entry_point": "select_optimal_orbital_transfer",
        "signature": "def select_optimal_orbital_transfer(r1_km: float, r2_km: float, rb_km: float) -> dict:",
        "problem_statement": (
            "Orbital transfer planner hardcodes 2-impulse Hohmann transfers even when r2/r1 > 11.94, "
            "missing fuel-optimal 3-impulse bi-elliptic solutions. Compute both total delta-V budgets "
            "and recommend the true minimum-propellant strategy."
        ),
        "fail_to_pass_tests": [
            "test_bielliptic_crossover_efficiency",
            "test_bielliptic_3_impulse_conservation",
        ],
        "pass_to_pass_tests": [
            "test_hohmann_standard_leo_geo",
            "test_positive_delta_v_outputs",
        ],
        "starter_buggy_code": (
            "def select_optimal_orbital_transfer(r1_km: float, r2_km: float, rb_km: float) -> dict:\n"
            "    # BUG: Always hardcodes 'hohmann' even when r2/r1 > 11.94 makes bielliptic optimal\n"
            "    mu = 398600.4418\n"
            "    a_h = 0.5 * (r1_km + r2_km)\n"
            "    dv_h = abs(math.sqrt(mu * (2/r1_km - 1/a_h)) - math.sqrt(mu/r1_km)) + abs(math.sqrt(mu/r2_km) - math.sqrt(mu * (2/r2_km - 1/a_h)))\n"
            "    return {'recommended': 'hohmann', 'hohmann_dv_km_s': dv_h, 'bielliptic_dv_km_s': dv_h * 1.1}\n"
        ),
        "reference_solution": (
            "def select_optimal_orbital_transfer(r1_km: float, r2_km: float, rb_km: float) -> dict:\n"
            "    mu = 398600.4418\n"
            "    a_h = 0.5 * (r1_km + r2_km)\n"
            "    dv_h = (\n"
            "        abs(math.sqrt(mu * (2.0 / r1_km - 1.0 / a_h)) - math.sqrt(mu / r1_km))\n"
            "        + abs(math.sqrt(mu / r2_km) - math.sqrt(mu * (2.0 / r2_km - 1.0 / a_h)))\n"
            "    )\n"
            "    a1 = 0.5 * (r1_km + rb_km)\n"
            "    a2 = 0.5 * (rb_km + r2_km)\n"
            "    dv_b = (\n"
            "        abs(math.sqrt(mu * (2.0 / r1_km - 1.0 / a1)) - math.sqrt(mu / r1_km))\n"
            "        + abs(math.sqrt(mu * (2.0 / rb_km - 1.0 / a2)) - math.sqrt(mu * (2.0 / rb_km - 1.0 / a1)))\n"
            "        + abs(math.sqrt(mu / r2_km) - math.sqrt(mu * (2.0 / r2_km - 1.0 / a2)))\n"
            "    )\n"
            "    rec = 'bielliptic' if dv_b < dv_h else 'hohmann'\n"
            "    return {'recommended': rec, 'hohmann_dv_km_s': dv_h, 'bielliptic_dv_km_s': dv_b}\n"
        ),
    },
    {
        "task_id": "AERO-009",
        "domain": "Rocket Propulsion CFD / Numerical Stability",
        "title": "Explicit MacCormack CFL Acoustic Wave-Speed Stability Limit",
        "difficulty": "Medium",
        "entry_point": "compute_stable_cfd_timestep",
        "signature": (
            "def compute_stable_cfd_timestep("
            "dx_m: float, velocity_mps: float, sound_speed_mps: float, cfl_target: float = 0.45"
            ") -> float:"
        ),
        "problem_statement": (
            "Explicit MacCormack nozzle solver diverges to NaN during hypersonic exhaust expansion "
            "because the fixed denominator ignores local acoustic wave speed |V| + a and clamps "
            "CFL above 1.0. Enforce Courant-Friedrichs-Lewy bound cfl < 1.0 using max characteristic "
            "speed (|velocity| + sound_speed)."
        ),
        "fail_to_pass_tests": [
            "test_supersonic_cfl_stability_bound",
            "test_reverse_flow_abs_velocity_guard",
        ],
        "pass_to_pass_tests": [
            "test_zero_velocity_acoustic_timestep",
            "test_linear_dx_grid_scaling",
        ],
        "starter_buggy_code": (
            "def compute_stable_cfd_timestep(dx_m: float, velocity_mps: float, sound_speed_mps: float, cfl_target: float = 0.45) -> float:\n"
            "    # BUG: Ignores local velocity + sound speed and allows CFL >= 1.0 blowup\n"
            "    return dx_m / max(1.0, velocity_mps)\n"
        ),
        "reference_solution": (
            "def compute_stable_cfd_timestep(dx_m: float, velocity_mps: float, sound_speed_mps: float, cfl_target: float = 0.45) -> float:\n"
            "    if dx_m <= 0.0 or sound_speed_mps <= 0.0:\n"
            "        raise ValueError('Grid spacing and sound speed must be positive')\n"
            "    safe_cfl = max(0.05, min(0.95, float(cfl_target)))\n"
            "    max_wave_speed = abs(float(velocity_mps)) + float(sound_speed_mps)\n"
            "    return safe_cfl * float(dx_m) / max_wave_speed\n"
        ),
    },
    {
        "task_id": "AERO-010",
        "domain": "Rocket Thrust Chamber / Bartz Regenerative Cooling",
        "title": "Bartz Hot-Wall Convective Thermal Network & Survival Margin",
        "difficulty": "Medium",
        "entry_point": "evaluate_regenerative_wall_thermal_margin",
        "signature": (
            "def evaluate_regenerative_wall_thermal_margin("
            "t_aw_k: float, t_cool_k: float, hg: float, hc: float, k_wall: float, t_wall_m: float, t_limit_k: float"
            ") -> dict:"
        ),
        "problem_statement": (
            "Nozzle thermal designer neglects conduction wall resistance (t_wall / k_wall) and coolant "
            "convection resistance (1 / hc), falsely predicting safe liner wall temperatures on low-conductivity "
            "alloys. Solve the full 1D series thermal resistance network for q'' [MW/m2], hot-gas wall Twg [K], "
            "and safety margin (t_limit_k - Twg)."
        ),
        "fail_to_pass_tests": [
            "test_series_wall_conduction_temperature_jump",
            "test_low_conductivity_inconel_overheat_detection",
        ],
        "pass_to_pass_tests": [
            "test_high_conductivity_copper_survival",
            "test_zero_heat_flux_isothermal_limit",
        ],
        "starter_buggy_code": (
            "def evaluate_regenerative_wall_thermal_margin(t_aw_k: float, t_cool_k: float, hg: float, hc: float, k_wall: float, t_wall_m: float, t_limit_k: float) -> dict:\n"
            "    # BUG: Assumes infinite wall conductivity and infinite coolant HTC -> underpredicts Twg!\n"
            "    twg = t_cool_k + 50.0\n"
            "    return {'heat_flux_mw_m2': 10.0, 'hot_wall_temp_k': twg, 'thermal_margin_k': t_limit_k - twg, 'survives': twg < t_limit_k}\n"
        ),
        "reference_solution": (
            "def evaluate_regenerative_wall_thermal_margin(t_aw_k: float, t_cool_k: float, hg: float, hc: float, k_wall: float, t_wall_m: float, t_limit_k: float) -> dict:\n"
            "    r_total = (1.0 / max(1e-6, hg)) + (t_wall_m / max(1e-6, k_wall)) + (1.0 / max(1e-6, hc))\n"
            "    q_w_m2 = max(0.0, (t_aw_k - t_cool_k) / r_total)\n"
            "    twg = t_cool_k + q_w_m2 * ((t_wall_m / max(1e-6, k_wall)) + (1.0 / max(1e-6, hc)))\n"
            "    margin = t_limit_k - twg\n"
            "    return {'heat_flux_mw_m2': q_w_m2 / 1e6, 'hot_wall_temp_k': twg, 'thermal_margin_k': margin, 'survives': margin > 0.0}\n"
        ),
    },
]

_TASK_TEST_SCRIPTS: dict[str, str] = {
    "AERO-001": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            v_sonic = _fn(1.0)
            v_sub = _fn(0.5)
            results["f2p"]["test_transonic_drag_saturation_finite"] = (
                math.isfinite(v_sonic) and 0.25 < v_sonic < 2.5 and v_sonic > v_sub
            )
        except Exception:
            results["f2p"]["test_transonic_drag_saturation_finite"] = False
        try:
            vals = [_fn(m) for m in (0.95, 0.99, 1.0, 1.01, 1.05)]
            jumps = [abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
            results["f2p"]["test_transonic_drag_monotonic_continuity"] = (
                all(math.isfinite(v) for v in vals) and max(jumps) < 0.5
            )
        except Exception:
            results["f2p"]["test_transonic_drag_monotonic_continuity"] = False
        try:
            v05 = _fn(0.5)
            results["p2p"]["test_subsonic_drag_polar"] = math.isfinite(v05) and 0.15 <= v05 <= 0.65
        except Exception:
            results["p2p"]["test_subsonic_drag_polar"] = False
        try:
            v20 = _fn(2.0)
            results["p2p"]["test_supersonic_wave_drag"] = math.isfinite(v20) and 0.05 <= v20 <= 0.6
        except Exception:
            results["p2p"]["test_supersonic_wave_drag"] = False
    """),
    "AERO-002": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            out = _fn([358.0, 359.5, 1.0, 2.5])
            steps = [abs(out[i + 1] - out[i]) for i in range(len(out) - 1)]
            results["f2p"]["test_zenith_pass_azimuth_continuity"] = len(out) == 4 and max(steps) < 5.0
        except Exception:
            results["f2p"]["test_zenith_pass_azimuth_continuity"] = False
        try:
            rev = _fn([2.0, 0.5, 359.0, 357.5])
            rsteps = [abs(rev[i + 1] - rev[i]) for i in range(len(rev) - 1)]
            results["f2p"]["test_gimbal_slew_rate_within_limits"] = len(rev) == 4 and max(rsteps) < 5.0
        except Exception:
            results["f2p"]["test_gimbal_slew_rate_within_limits"] = False
        try:
            nom = _fn([10.0, 12.0, 14.0])
            results["p2p"]["test_horizon_acquisition_elevation"] = (
                len(nom) == 3 and abs((nom[1] - nom[0]) - 2.0) < 1e-6
            )
        except Exception:
            results["p2p"]["test_horizon_acquisition_elevation"] = False
        try:
            results["p2p"]["test_sequence_length_preserved"] = len(_fn([45.0])) == 1 and _fn([]) == []
        except Exception:
            results["p2p"]["test_sequence_length_preserved"] = False
    """),
    "AERO-003": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            pts = _fn(20)
            sym_err = max(abs(pts[i] + pts[-1 - i] - 1.0) for i in range(len(pts)))
            results["f2p"]["test_symmetric_cosine_clustering_symmetry"] = len(pts) == 21 and sym_err < 1e-6
        except Exception:
            results["f2p"]["test_symmetric_cosine_clustering_symmetry"] = False
        try:
            pts = _fn(20)
            le = pts[1] - pts[0]
            te = pts[-1] - pts[-2]
            mid = pts[11] - pts[10]
            results["f2p"]["test_kutta_condition_trailing_edge_refinement"] = (
                le < 0.4 * mid and te < 0.4 * mid
            )
        except Exception:
            results["f2p"]["test_kutta_condition_trailing_edge_refinement"] = False
        try:
            pts = _fn(10)
            results["p2p"]["test_normalized_chord_endpoints"] = (
                abs(pts[0]) < 1e-9 and abs(pts[-1] - 1.0) < 1e-9
            )
        except Exception:
            results["p2p"]["test_normalized_chord_endpoints"] = False
        try:
            pts = _fn(16)
            results["p2p"]["test_strict_monotonic_progression"] = all(
                pts[i + 1] > pts[i] for i in range(len(pts) - 1)
            )
        except Exception:
            results["p2p"]["test_strict_monotonic_progression"] = False
    """),
    "AERO-004": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            expected = (1000.0 * (2.0**3)) / (48.0 * 2.0e11 * 1.0e-6)
            actual = _fn(1000.0, 2.0, 2.0e11, 1.0e-6)
            results["f2p"]["test_center_load_max_deflection_exact"] = abs(actual - expected) < 1e-9
        except Exception:
            results["f2p"]["test_center_load_max_deflection_exact"] = False
        try:
            d1 = _fn(500.0, 2.0, 2.0e11, 1.0e-6)
            d2 = _fn(1000.0, 2.0, 2.0e11, 1.0e-6)
            results["p2p"]["test_linear_load_scaling"] = d1 > 0 and abs(d2 - 2.0 * d1) < 1e-12
        except Exception:
            results["p2p"]["test_linear_load_scaling"] = False
        try:
            d1 = _fn(500.0, 1.0, 2.0e11, 1.0e-6)
            d2 = _fn(500.0, 2.0, 2.0e11, 1.0e-6)
            results["p2p"]["test_cubic_span_scaling"] = d1 > 0 and abs(d2 - 8.0 * d1) < 1e-12
        except Exception:
            results["p2p"]["test_cubic_span_scaling"] = False
    """),
    "AERO-005": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            rem = _fn(2.0, 5.0, 1.0)
            results["f2p"]["test_motor_burnout_propellant_non_negative"] = abs(rem - 0.0) < 1e-9
        except Exception:
            results["f2p"]["test_motor_burnout_propellant_non_negative"] = False
        try:
            rem0 = _fn(0.0, 3.0, 0.5)
            results["f2p"]["test_zero_propellant_residual_clamp"] = abs(rem0 - 0.0) < 1e-9
        except Exception:
            results["f2p"]["test_zero_propellant_residual_clamp"] = False
        try:
            results["p2p"]["test_steady_state_mass_depletion"] = abs(_fn(10.0, 2.0, 1.5) - 7.0) < 1e-9
        except Exception:
            results["p2p"]["test_steady_state_mass_depletion"] = False
        try:
            results["p2p"]["test_zero_mdot_coast_preservation"] = abs(_fn(8.5, 0.0, 2.0) - 8.5) < 1e-9
        except Exception:
            results["p2p"]["test_zero_mdot_coast_preservation"] = False
    """),
    "AERO-006": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            r, p, y = _fn(0.70710679, 0.0, 0.70710679, 0.0)
            results["f2p"]["test_gimbal_lock_singularity_avoidance"] = (
                all(math.isfinite(v) for v in (r, p, y)) and abs(p - 90.0) < 0.05
            )
        except Exception:
            results["f2p"]["test_gimbal_lock_singularity_avoidance"] = False
        try:
            r2, p2, y2 = _fn(0.70710679, 0.0, -0.70710679, 0.0)
            z0 = _fn(0.0, 0.0, 0.0, 0.0)
            results["f2p"]["test_pitch_90_degree_finite_euler"] = (
                all(math.isfinite(v) for v in (r2, p2, y2, *z0)) and abs(p2 + 90.0) < 0.05
            )
        except Exception:
            results["f2p"]["test_pitch_90_degree_finite_euler"] = False
        try:
            ri, pi, yi = _fn(1.0, 0.0, 0.0, 0.0)
            results["p2p"]["test_identity_quaternion_zero_euler"] = (
                abs(ri) < 1e-6 and abs(pi) < 1e-6 and abs(yi) < 1e-6
            )
        except Exception:
            results["p2p"]["test_identity_quaternion_zero_euler"] = False
        try:
            hr = math.radians(15.0)
            rr, pr, yr = _fn(math.cos(hr), math.sin(hr), 0.0, 0.0)
            results["p2p"]["test_nonsingular_roll_extraction"] = abs(rr - 30.0) < 1e-3 and abs(pr) < 1e-3
        except Exception:
            results["p2p"]["test_nonsingular_roll_extraction"] = False
    """),
    "AERO-007": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            try:
                _fn(2.0, 40.0, 1.4)
                results["f2p"]["test_oblique_shock_detachment_value_error"] = False
            except ValueError:
                results["f2p"]["test_oblique_shock_detachment_value_error"] = True
        except Exception:
            results["f2p"]["test_oblique_shock_detachment_value_error"] = False
        try:
            b_att = _fn(2.0, 22.0, 1.4)
            detached = False
            try:
                _fn(2.0, 24.0, 1.4)
            except ValueError:
                detached = True
            results["f2p"]["test_theta_max_golden_section_bound"] = (
                detached and math.isfinite(b_att) and 50.0 < b_att < 70.0
            )
        except Exception:
            results["f2p"]["test_theta_max_golden_section_bound"] = False
        try:
            b10 = _fn(2.0, 10.0, 1.4)
            results["p2p"]["test_weak_oblique_shock_mach2_10deg"] = math.isfinite(b10) and abs(b10 - 39.314) < 0.35
        except Exception:
            results["p2p"]["test_weak_oblique_shock_mach2_10deg"] = False
        try:
            b1 = _fn(2.0, 1.0, 1.4)
            results["p2p"]["test_small_deflection_mach_angle_limit"] = 30.0 < b1 < 33.0
        except Exception:
            results["p2p"]["test_small_deflection_mach_angle_limit"] = False
    """),
    "AERO-008": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            res = _fn(7000.0, 120000.0, 240000.0)
            results["f2p"]["test_bielliptic_crossover_efficiency"] = (
                isinstance(res, dict) and res.get("recommended") == "bielliptic"
            )
        except Exception:
            results["f2p"]["test_bielliptic_crossover_efficiency"] = False
        try:
            res = _fn(7000.0, 120000.0, 240000.0)
            results["f2p"]["test_bielliptic_3_impulse_conservation"] = (
                isinstance(res, dict)
                and res.get("bielliptic_dv_km_s", 999.0) < res.get("hohmann_dv_km_s", 0.0)
            )
        except Exception:
            results["f2p"]["test_bielliptic_3_impulse_conservation"] = False
        try:
            leo_geo = _fn(6700.0, 42164.0, 80000.0)
            results["p2p"]["test_hohmann_standard_leo_geo"] = (
                isinstance(leo_geo, dict) and leo_geo.get("recommended") == "hohmann"
            )
        except Exception:
            results["p2p"]["test_hohmann_standard_leo_geo"] = False
        try:
            leo_geo = _fn(6700.0, 42164.0, 80000.0)
            results["p2p"]["test_positive_delta_v_outputs"] = (
                leo_geo.get("hohmann_dv_km_s", 0.0) > 3.5 and leo_geo.get("bielliptic_dv_km_s", 0.0) > 3.5
            )
        except Exception:
            results["p2p"]["test_positive_delta_v_outputs"] = False
    """),
    "AERO-009": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            dt = _fn(0.01, 2800.0, 900.0, 0.45)
            courant = dt * (2800.0 + 900.0) / 0.01
            results["f2p"]["test_supersonic_cfl_stability_bound"] = (
                0.0 < courant < 0.99 and abs(courant - 0.45) < 1e-6
            )
        except Exception:
            results["f2p"]["test_supersonic_cfl_stability_bound"] = False
        try:
            dt_rev = _fn(0.01, -1200.0, 800.0, 0.45)
            courant_rev = dt_rev * (1200.0 + 800.0) / 0.01
            results["f2p"]["test_reverse_flow_abs_velocity_guard"] = (
                0.0 < courant_rev < 0.99 and abs(courant_rev - 0.45) < 1e-6
            )
        except Exception:
            results["f2p"]["test_reverse_flow_abs_velocity_guard"] = False
        try:
            dt_zero = _fn(0.02, 0.0, 1000.0, 0.5)
            results["p2p"]["test_zero_velocity_acoustic_timestep"] = abs(dt_zero - 1e-5) < 1e-9
        except Exception:
            results["p2p"]["test_zero_velocity_acoustic_timestep"] = False
        try:
            dt1 = _fn(0.01, 1000.0, 500.0, 0.45)
            dt2 = _fn(0.02, 1000.0, 500.0, 0.45)
            results["p2p"]["test_linear_dx_grid_scaling"] = abs(dt2 - 2.0 * dt1) < 1e-12
        except Exception:
            results["p2p"]["test_linear_dx_grid_scaling"] = False
    """),
    "AERO-010": textwrap.dedent("""\
        results = {"f2p": {}, "p2p": {}}
        try:
            res_inc = _fn(3400.0, 135.0, 22000.0, 95000.0, 21.5, 0.0018, 1250.0)
            results["f2p"]["test_low_conductivity_inconel_overheat_detection"] = (
                isinstance(res_inc, dict)
                and res_inc.get("hot_wall_temp_k", 0.0) > 1500.0
                and res_inc.get("survives") is False
            )
        except Exception:
            results["f2p"]["test_low_conductivity_inconel_overheat_detection"] = False
        try:
            res_cu = _fn(3400.0, 135.0, 22000.0, 95000.0, 310.0, 0.0009, 1050.0)
            results["f2p"]["test_series_wall_conduction_temperature_jump"] = (
                isinstance(res_cu, dict) and 500.0 < res_cu.get("hot_wall_temp_k", 0.0) < 1050.0
            )
        except Exception:
            results["f2p"]["test_series_wall_conduction_temperature_jump"] = False
        try:
            res_cu = _fn(3400.0, 135.0, 22000.0, 95000.0, 310.0, 0.0009, 1050.0)
            results["p2p"]["test_high_conductivity_copper_survival"] = (
                isinstance(res_cu, dict) and res_cu.get("survives") is True and res_cu.get("heat_flux_mw_m2", 0.0) > 30.0
            )
        except Exception:
            results["p2p"]["test_high_conductivity_copper_survival"] = False
        try:
            res_iso = _fn(200.0, 200.0, 20000.0, 80000.0, 310.0, 0.001, 1050.0)
            results["p2p"]["test_zero_heat_flux_isothermal_limit"] = (
                isinstance(res_iso, dict) and abs(res_iso.get("heat_flux_mw_m2", 1.0)) < 1e-6
            )
        except Exception:
            results["p2p"]["test_zero_heat_flux_isothermal_limit"] = False
    """),
}


def _extract_python_code(patch_text: str) -> str:
    """Extract executable Python source from either raw Python code or unified diff patches."""
    lines = patch_text.splitlines()
    is_diff = any(line.startswith(("+++ ", "--- ", "@@ ")) for line in lines)
    if not is_diff:
        return patch_text

    extracted: list[str] = []
    for line in lines:
        if line.startswith(("+++ ", "--- ", "@@ ", "diff --git ", "index ")):
            continue
        if line.startswith("+"):
            extracted.append(line[1:])
        elif line.startswith(" "):
            extracted.append(line[1:])
    return "\n".join(extracted) if extracted else patch_text


def _inspect_ast_safety(tree: ast.AST, preferred_entry: str) -> tuple[bool, str | None, str | None]:
    """Verify AST safety constraints and locate primary candidate function."""
    defined_funcs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in DISALLOWED_MODULES:
                    return False, None, f"Disallowed import '{alias.name}' blocked by sandbox."
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in DISALLOWED_MODULES:
                return False, None, f"Disallowed import from '{node.module}' blocked by sandbox."
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in DISALLOWED_CALLS:
                return (
                    False,
                    None,
                    f"Disallowed builtin call '{node.func.id}()' blocked by sandbox.",
                )
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                return False, None, f"Disallowed dunder attribute '{node.attr}' blocked by sandbox."
        elif isinstance(node, ast.FunctionDef):
            defined_funcs.append(node.name)

    if preferred_entry in defined_funcs:
        return True, preferred_entry, None
    if defined_funcs:
        return True, defined_funcs[0], None
    return False, None, f"No callable function definition found (expected '{preferred_entry}')."


def _build_sandbox_runner_script(code: str, entry_name: str, test_body: str) -> str:
    """Construct self-contained script executed inside `python -I` subprocess."""
    indented_tests = textwrap.indent(test_body, "    ")
    return (
        "import json, math\n\n"
        f"{code}\n\n"
        f"_fn = globals().get({entry_name!r})\n"
        "def _run():\n"
        f"{indented_tests}\n"
        "    return results\n"
        "print(json.dumps(_run()))\n"
    )


def evaluate_handshake_candidate_patch(
    task_id: str,
    patch_text: str,
    model_name: str = "Candidate-Agent",
) -> dict[str, Any]:
    """
    Execute isolated subprocess evaluation of a candidate patch against a Handshake AI task.
    Performs AST syntax & security inspection followed by real numerical physics assertions.
    """
    start_time = time.perf_counter()
    normalized_id = task_id.upper()
    task = next((t for t in HANDSHAKE_TASKS if t["task_id"] == normalized_id), None)
    if not task:
        return {
            "task_id": task_id,
            "model_name": model_name,
            "status": "ERROR",
            "is_resolved": False,
            "fail_to_pass_score": "0/0",
            "pass_to_pass_score": "0/0",
            "execution_time_ms": 0.0,
            "sandbox_engine": "isolated-subprocess-ast-v2",
            "test_details": {},
            "message": f"Task instance '{task_id}' not found in Handshake AI benchmark matrix.",
        }

    n_f2p = len(task["fail_to_pass_tests"])
    n_p2p = len(task["pass_to_pass_tests"])

    if not patch_text or not patch_text.strip():
        elapsed = (time.perf_counter() - start_time) * 1000.0
        return {
            "task_id": normalized_id,
            "model_name": model_name,
            "status": "FAILED",
            "is_resolved": False,
            "fail_to_pass_score": f"0/{n_f2p}",
            "pass_to_pass_score": f"0/{n_p2p}",
            "execution_time_ms": round(elapsed, 2),
            "sandbox_engine": "isolated-subprocess-ast-v2",
            "test_details": {},
            "message": "Empty candidate patch supplied. Zero modifications verified.",
        }

    candidate_code = _extract_python_code(patch_text)
    try:
        tree = ast.parse(candidate_code)
    except SyntaxError as exc:
        elapsed = (time.perf_counter() - start_time) * 1000.0
        return {
            "task_id": normalized_id,
            "model_name": model_name,
            "status": "SYNTAX_ERROR",
            "is_resolved": False,
            "fail_to_pass_score": f"0/{n_f2p}",
            "pass_to_pass_score": f"0/{n_p2p}",
            "execution_time_ms": round(elapsed, 2),
            "sandbox_engine": "isolated-subprocess-ast-v2",
            "test_details": {},
            "message": f"SyntaxError at line {exc.lineno}: {exc.msg}",
        }

    safe, entry_name, err_msg = _inspect_ast_safety(tree, task["entry_point"])
    if not safe or not entry_name:
        elapsed = (time.perf_counter() - start_time) * 1000.0
        status = "SECURITY_VIOLATION" if err_msg and "blocked by sandbox" in err_msg else "FAILED"
        return {
            "task_id": normalized_id,
            "model_name": model_name,
            "status": status,
            "is_resolved": False,
            "fail_to_pass_score": f"0/{n_f2p}",
            "pass_to_pass_score": f"0/{n_p2p}",
            "execution_time_ms": round(elapsed, 2),
            "sandbox_engine": "isolated-subprocess-ast-v2",
            "test_details": {},
            "message": err_msg or "Invalid candidate function.",
        }

    harness_script = _build_sandbox_runner_script(
        candidate_code, entry_name, _TASK_TEST_SCRIPTS[normalized_id]
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-"],
            input=harness_script,
            text=True,
            capture_output=True,
            timeout=3.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - start_time) * 1000.0
        return {
            "task_id": normalized_id,
            "model_name": model_name,
            "status": "TIMEOUT",
            "is_resolved": False,
            "fail_to_pass_score": f"0/{n_f2p}",
            "pass_to_pass_score": f"0/{n_p2p}",
            "execution_time_ms": round(elapsed, 2),
            "sandbox_engine": "isolated-subprocess-ast-v2",
            "test_details": {},
            "message": "Candidate execution exceeded 3.0s isolated sandbox timeout.",
        }

    elapsed = (time.perf_counter() - start_time) * 1000.0
    if proc.returncode != 0 or not proc.stdout.strip():
        stderr_preview = (proc.stderr or "Runtime execution failure").strip().splitlines()[-1]
        return {
            "task_id": normalized_id,
            "model_name": model_name,
            "status": "FAILED",
            "is_resolved": False,
            "fail_to_pass_score": f"0/{n_f2p}",
            "pass_to_pass_score": f"0/{n_p2p}",
            "execution_time_ms": round(elapsed, 2),
            "sandbox_engine": "isolated-subprocess-ast-v2",
            "test_details": {},
            "message": f"Sandbox runtime error: {stderr_preview}",
        }

    parsed = json.loads(proc.stdout.strip().splitlines()[-1])
    f2p_map: dict[str, bool] = parsed.get("f2p", {})
    p2p_map: dict[str, bool] = parsed.get("p2p", {})

    f2p_passed = sum(1 for v in f2p_map.values() if v)
    p2p_passed = sum(1 for v in p2p_map.values() if v)
    f2p_total = max(n_f2p, len(f2p_map))
    p2p_total = max(n_p2p, len(p2p_map))
    resolved = f2p_passed == f2p_total and p2p_passed == p2p_total

    return {
        "task_id": normalized_id,
        "model_name": model_name,
        "status": "RESOLVED" if resolved else "FAILED",
        "is_resolved": resolved,
        "fail_to_pass_score": f"{f2p_passed}/{f2p_total}",
        "pass_to_pass_score": f"{p2p_passed}/{p2p_total}",
        "execution_time_ms": round(elapsed, 2),
        "sandbox_engine": "isolated-subprocess-ast-v2",
        "test_details": {"fail_to_pass": f2p_map, "pass_to_pass": p2p_map},
        "message": (
            "All isolated AST & numerical physics assertions passed."
            if resolved
            else "One or more fail-to-pass or regression invariants failed in sandbox execution."
        ),
    }
