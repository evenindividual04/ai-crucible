"""Event type definitions for WebSocket protocol"""

from typing import Literal, Dict, Any, List
from pydantic import BaseModel


# Event types
EventType = Literal[
    "SYSTEM_INIT",
    "SIMULATION_END",
    "ITERATION_START",
    "AGENT_SPAWN",
    "AGENT_THINKING",
    "COMPONENT_CREATED",
    "COMPONENT_RISK_UPDATE",
    "VULNERABILITY_FOUND",
    "PATCH_APPLIED",
    "SCORE_UPDATE",
    "ATTACK_EFFECTIVENESS_UPDATE",
    "DEFENSE_QUALITY_UPDATE",
    "CONVERGENCE_UPDATE",
    "JUDGE_DECISION",
    "ERROR"
]


class WebSocketEvent(BaseModel):
    """Base WebSocket event"""
    type: EventType
    data: Dict[str, Any] | List[Dict[str, Any]]
