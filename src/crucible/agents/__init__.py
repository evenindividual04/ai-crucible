"""Agents module for the AI Crucible."""

from crucible.agents.base import BaseAgent
from crucible.agents.architect import ArchitectAgent
from crucible.agents.defender import DefenderAgent
from crucible.agents.red_team import (
    SecurityHawk,
    ScaleMonster,
    CostAnalyst,
    LogicBreaker,
    RedTeamAgent,
)
# V2 Agents
from crucible.agents.compliance import ComplianceAgent
from crucible.agents.ux_adversary import UXAdversary
from crucible.agents.chaos_engineer import ChaosEngineer

__all__ = [
    "BaseAgent",
    "ArchitectAgent",
    "DefenderAgent",
    "SecurityHawk",
    "ScaleMonster",
    "CostAnalyst",
    "LogicBreaker",
    "RedTeamAgent",
    # V2 Agents
    "ComplianceAgent",
    "UXAdversary",
    "ChaosEngineer",
]

