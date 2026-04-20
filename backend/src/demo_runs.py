"""Precomputed demo runs for zero-friction time-to-value."""

from __future__ import annotations

from typing import Any


DEMO_RUNS: dict[str, dict[str, Any]] = {
    "payments-gateway": {
        "title": "Distributed payments gateway",
        "prompt": "Design a distributed payment gateway with fraud controls",
        "events": [
            {"type": "SYSTEM_INIT", "data": {"prompt": "Design a distributed payment gateway with fraud controls", "config": {}, "timestamp": 0}},
            {"type": "ITERATION_START", "data": {"iteration": 1, "max_iterations": 3}},
            {"type": "AGENT_SPAWN", "data": {"id": "red-1", "name": "Security Hawk", "type": "RED_TEAM"}},
            {"type": "VULNERABILITY_FOUND", "data": {"id": 101, "severity": "CRITICAL", "title": "Replay window gap"}},
            {"type": "PATCH_APPLIED", "data": {"id": 501, "target_vulnerability_id": 101, "description": "Nonce + idempotency enforcement"}},
            {"type": "SCORE_UPDATE", "data": {"score": 83, "grade": "B", "risk_level": "LOW"}},
            {"type": "SIMULATION_END", "data": {"status": "STABLE", "iterations": 3, "security_score": 83}},
        ],
    },
    "healthcare-auth": {
        "title": "Healthcare auth & PHI boundaries",
        "prompt": "Design healthcare auth with PHI isolation and auditability",
        "events": [
            {"type": "SYSTEM_INIT", "data": {"prompt": "Design healthcare auth with PHI isolation and auditability", "config": {}, "timestamp": 0}},
            {"type": "ITERATION_START", "data": {"iteration": 1, "max_iterations": 2}},
            {"type": "AGENT_SPAWN", "data": {"id": "red-2", "name": "Compliance Agent", "type": "RED_TEAM"}},
            {"type": "VULNERABILITY_FOUND", "data": {"id": 202, "severity": "HIGH", "title": "Audit retention mismatch"}},
            {"type": "PATCH_APPLIED", "data": {"id": 602, "target_vulnerability_id": 202, "description": "Retention policy + immutable ledger"}},
            {"type": "SCORE_UPDATE", "data": {"score": 89, "grade": "B", "risk_level": "LOW"}},
            {"type": "SIMULATION_END", "data": {"status": "STABLE", "iterations": 2, "security_score": 89}},
        ],
    },
}


def list_demo_runs() -> list[dict[str, str]]:
    return [
        {
            "demo_id": demo_id,
            "title": payload["title"],
            "prompt": payload["prompt"],
        }
        for demo_id, payload in DEMO_RUNS.items()
    ]
