# Aerospace Operations Stack (AeroOps) 🛰️🚀

[![CI Matrix](https://github.com/perfectalone375/aerospace-ops-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/perfectalone375/aerospace-ops-stack/actions)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/docker--compose-v2%2B-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests Passing](https://img.shields.io/badge/tests-10%20passed-brightgreen.svg)](tests/)

Cloud-Native Aerospace Microservices Stack & Mission Control Telemetry Visualizer orchestrated with **Docker Compose**.

AeroOps acts as a centralized operations hub coordinating 3-DoF computational flight dynamics, real-time SGP4 satellite orbit propagation, physics-informed CFD surrogate aerodynamic modeling, and SWE-bench AI benchmark evaluation harnesses under a unified REST API and mission control user interface.

---

## 🏛️ Microservice Systems Architecture

```mermaid
flowchart TD
    Client([Engineer / Browser / Mission Control]) --> Gateway[AeroOps Gateway & Static Dashboard<br/>FastAPI / Port 8080]

    subgraph DockerMesh[Docker Mesh Bridge Network: aero-mesh]
        Gateway --> FlightEngine[Flight Dynamics Service<br/>3-DoF RK4 Suborbital Solver]
        Gateway --> OrbitEngine[Orbital Telemetry Service<br/>SGP4 / J2 Secular Propagator]
        Gateway --> CFDEngine[CFD Surrogate Service<br/>Vortex Panel & Squire-Young Drag]
        Gateway --> BenchHarness[AeroEval Benchmark Service<br/>SWE-bench LLM Leaderboard]
    end

    FlightEngine --> TelemetryFeed[Telemetry Streams<br/>Altitude, Mach, Dynamic Pressure q]
    OrbitEngine --> GroundTrackFeed[Ground Tracks & Pass Schedules<br/>AOS/LOS, Footprint, RF Doppler]
    CFDEngine --> PolarFeed[Aerodynamic Polar & Cp Distribution]
    BenchHarness --> AIReport[Pass@1 Model Resolution Scores]

    TelemetryFeed --> Gateway
    GroundTrackFeed --> Gateway
    PolarFeed --> Gateway
    AIReport --> Gateway
```

---

## 🚀 Key Platform Capabilities

### 1. Unified Mission Control UI (`/`)
* **Real-time Canvas Telemetry Gauges:** Instantaneous visual rendering of suborbital altitude, axial acceleration, Mach number, and dynamic pressure Max-Q.
* **Interactive Orbital World Map:** Dynamic sine ground-track projection displaying satellite subpoint, velocity vector, and ground station elevation coverage circle.
* **Aerodynamic Surface Pressure Chart ($C_p$):** Chordwise suction loop and stall onset rendering for NACA 4-digit profiles.
* **SWE-bench AI Leaderboard:** Real-time ranking of frontier coding LLMs (Claude 3.5 Sonnet, GPT-4o, DeepSeek-Coder) across aerospace physics tasks.

### 2. Multi-Container Orchestration (`docker-compose.yml`)
* Healthcheck-gated container startup ensuring zero-downtime microservice orchestration.
* Production security sandboxing with slim Python base images and non-root execution.
* Multi-stage caching for minimal container footprint (<150 MB).

---

## ⚡ Quick Start with Docker Compose

### 1. Launch with Docker Compose

```bash
# Clone the repository
git clone https://github.com/perfectalone375/aerospace-ops-stack.git
cd aerospace-ops-stack

# Build and start all services in detached mode
docker compose up --build -d

# Check cluster status
docker compose ps
```

Visit the Mission Control interface in your browser:
👉 **`http://localhost:8080`**

### 2. Run Locally with Python

```bash
pip install -e ".[dev]"
aero-ops
# Or: uvicorn aerospace_ops.gateway:app --port 8080 --reload
```

---

## 📡 REST API Specification

| Endpoint | Method | Tag | Description |
|---|---|---|---|
| `/api/health` | `GET` | `system` | Aggregated microservice health check matrix |
| `/api/simulation/flight` | `POST` | `telemetry` | Runs 3-DoF suborbital trajectory integration |
| `/api/simulation/orbit` | `POST` | `telemetry` | Propagates satellite orbit and ground station pass |
| `/api/simulation/cfd` | `POST` | `telemetry` | Evaluates airfoil pressure distribution and polar |
| `/api/benchmarks` | `GET` | `evaluation` | Returns SWE-bench AI evaluation standings |
| `/` | `GET` | `ui` | Serves interactive Mission Control single-page app |

---

## 🧪 Testing & Verification

```bash
# Run pytest test suite
pytest --cov=aerospace_ops

# Run Ruff code style checks
ruff check .

# Validate Docker Compose syntax
docker compose config
```

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

Engineered with precision by **[Gopi Naga Vignesh Thirupati](https://github.com/perfectalone375)**.
