"""Event type definitions for WebSocket protocol"""

from typing import Literal, Dict, Any, List
from pydantic import BaseModel, model_validator


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

    @model_validator(mode="after")
    def validate_payload_shape(self):
        list_payload_events = {"ATTACK_EFFECTIVENESS_UPDATE"}
        dict_payload_events = {
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
            "DEFENSE_QUALITY_UPDATE",
            "CONVERGENCE_UPDATE",
            "JUDGE_DECISION",
            "ERROR",
        }
        required_keys: dict[str, set[str]] = {
            "SYSTEM_INIT": {"prompt", "config", "timestamp"},
            "SIMULATION_END": {"status", "iterations"},
            "ITERATION_START": {"iteration", "max_iterations"},
            "AGENT_SPAWN": {"id", "name", "type"},
            "COMPONENT_CREATED": {"id", "name", "type"},
            "COMPONENT_RISK_UPDATE": {"component_id", "risk_level", "vulnerability_count"},
            "VULNERABILITY_FOUND": {"id", "severity", "title"},
            "PATCH_APPLIED": {"id", "target_vulnerability_id", "description"},
            "SCORE_UPDATE": {"score"},
            "DEFENSE_QUALITY_UPDATE": set(),
            "CONVERGENCE_UPDATE": set(),
            "JUDGE_DECISION": {"decision", "reason"},
            "ERROR": {"message"},
            "AGENT_THINKING": set(),
        }

        if self.type in list_payload_events:
            if not isinstance(self.data, list):
                raise ValueError(f"{self.type} requires list payload")
            if not all(isinstance(item, dict) for item in self.data):
                raise ValueError(f"{self.type} payload items must be objects")
            return self

        if self.type in dict_payload_events and not isinstance(self.data, dict):
            raise ValueError(f"{self.type} requires object payload")

        if self.type in required_keys and isinstance(self.data, dict):
            missing = required_keys[self.type] - set(self.data.keys())
            if missing:
                raise ValueError(f"{self.type} missing required keys: {sorted(missing)}")

        return self
