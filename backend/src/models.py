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

        if self.type in list_payload_events:
            if not isinstance(self.data, list):
                raise ValueError(f"{self.type} requires list payload")
            if not all(isinstance(item, dict) for item in self.data):
                raise ValueError(f"{self.type} payload items must be objects")
            return self

        if self.type in dict_payload_events and not isinstance(self.data, dict):
            raise ValueError(f"{self.type} requires object payload")

        return self
