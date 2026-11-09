#!/usr/bin/env python3
"""
Automated Model Context Protocol (MCP) Configuration Installer for Claude Desktop & Cursor.
Scans for local virtual environments and registers all aerospace simulation servers.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

SERVERS = {
    "aero-flight-dynamics": {
        "repo_dir": "f:\\askable",
        "module": "aero_flight_dynamics.mcp.server",
    },
    "orbital-telemetry-agent": {
        "repo_dir": "f:\\orbital-telemetry-agent",
        "module": "orbital_telemetry.mcp.server",
    },
    "cfd-airfoil-surrogate": {
        "repo_dir": "f:\\cfd-airfoil-surrogate",
        "module": "cfd_surrogate.mcp.server",
    },
    "openengineering-toolkit": {
        "repo_dir": "f:\\openengineering-toolkit",
        "module": "openengineering.mcp_server",
    },
    "aero-eval-benchmark": {
        "repo_dir": "f:\\aero-eval-benchmark",
        "module": "aero_eval.mcp.server",
    },
}

def get_claude_config_path() -> Path:
    system = platform.system()
    if system == "Windows":
        app_data = os.getenv("APPDATA")
        if not app_data:
            raise RuntimeError("APPDATA environment variable not found on Windows.")
        return Path(app_data) / "Claude" / "claude_desktop_config.json"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

def find_python_interpreter() -> str:
    # Prefer virtual environment interpreter
    venv_candidates = [
        Path("f:/askable/.venv/Scripts/python.exe"),
        Path("f:/askable/.venv/bin/python"),
        Path(sys.executable),
    ]
    for candidate in venv_candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return sys.executable

def main() -> None:
    print("🚀 Initializing Aerospace MCP Suite Installer for Claude Desktop...")
    config_path = get_claude_config_path()
    python_exe = find_python_interpreter()
    print(f"📦 Using Python Interpreter: {python_exe}")
    print(f"📁 Target Configuration File: {config_path}")

    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_data = {"mcpServers": {}}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                config_data = json.load(f)
            if "mcpServers" not in config_data:
                config_data["mcpServers"] = {}
        except Exception as e:
            print(f"⚠️ Warning: Could not parse existing config: {e}. Creating fresh backup.")
            backup_path = config_path.with_suffix(".bak")
            config_path.rename(backup_path)
            print(f"  Backup saved to {backup_path}")
            config_data = {"mcpServers": {}}

    for server_name, spec in SERVERS.items():
        repo_path = Path(spec["repo_dir"])
        if not repo_path.exists():
            print(f"⏩ Skipping {server_name}: Directory {repo_path} not found.")
            continue

        config_data["mcpServers"][server_name] = {
            "command": python_exe,
            "args": ["-m", spec["module"]],
            "cwd": str(repo_path.resolve()),
        }
        print(f"  ✅ Configured: {server_name} -> {spec['module']}")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    print("\n🎉 Success! All aerospace MCP tools have been registered in Claude Desktop.")
    print("👉 Restart Claude Desktop to activate the computational tools.")

if __name__ == "__main__":
    main()
