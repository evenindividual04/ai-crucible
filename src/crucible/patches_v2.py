"""
Enhanced Patch model and Defender specialization for v2.

Provides patch confidence, trade-offs, and defense justification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Literal

from pydantic import BaseModel, Field


class FixCategory(str, Enum):
    """Category of fix complexity."""
    
    TACTICAL = "TACTICAL"           # Quick fix, minimal change (max 5 lines)
    STRUCTURAL = "STRUCTURAL"       # Requires component modification
    ARCHITECTURAL = "ARCHITECTURAL"  # Requires system redesign


class PatchV2(BaseModel):
    """
    Enhanced patch model with confidence and trade-offs.
    
    Extends the basic Patch with v2 features for better decision-making.
    """
    
    patch_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    target_vulnerability_id: int
    fix_description: str
    design_changes: List[str]
    introduces_new_assumptions: bool = False
    
    # V2: Confidence and rationale
    patch_confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    confidence_rationale: str = ""
    
    # V2: Trade-offs
    trade_offs: Optional[str] = None  # e.g., "Adds 50ms latency but prevents race condition"
    
    # V2: Rollback
    rollback_hint: Optional[str] = None  # How to undo if needed
    
    # V2: Alternatives
    alternative_approaches: Optional[List[str]] = None
    
    # V2: Fix complexity
    fix_category: FixCategory = FixCategory.TACTICAL

    # PR7: Strategy attribution
    defender_strategy: Optional[Literal["tactical-first", "balanced", "architecture-first"]] = None

    # Compatibility / wiring fields
    description: Optional[str] = None               # alias for fix_description (test compatibility)
    vulnerability_summary: Optional[str] = None
    affected_components: List[str] = Field(default_factory=list)  # component names (str)
    defense_justification: Optional["DefenseJustification"] = None


class IncrementalPatch(PatchV2):
    """
    Patch that reduces severity without fully eliminating vulnerability.
    
    Useful when full fix requires more time/effort.
    """
    
    full_fix: bool = True
    severity_before: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "HIGH"
    severity_after: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    remaining_risk: str = ""


class DefenseJustification(BaseModel):
    """
    Explanation of WHY a patch works.
    
    Helps with verification and understanding.
    """
    
    patch_id: int
    attack_vector_addressed: str
    mechanism: str  # HOW the fix prevents the attack
    assumptions_required: List[str] = Field(default_factory=list)
    verification_method: Literal[
        "CODE_REVIEW",
        "UNIT_TEST",
        "INTEGRATION_TEST",
        "MANUAL_CHECK",
        "STATIC_ANALYSIS"
    ] = "CODE_REVIEW"


# Resolve forward reference from PatchV2
PatchV2.model_rebuild()
IncrementalPatch.model_rebuild()


class AttackEffectiveness(BaseModel):
    """Metrics for how effective each agent's attacks were."""
    
    agent: str
    total_attacks: int
    accepted_attacks: int  # Not rejected as duplicate/invalid
    patched_attacks: int   # Successfully addressed
    
    @property
    def effectiveness_ratio(self) -> float:
        """Ratio of accepted attacks to total."""
        return self.accepted_attacks / self.total_attacks if self.total_attacks > 0 else 0
    
    @property
    def impact_ratio(self) -> float:
        """Ratio of patched attacks to total."""
        return self.patched_attacks / self.total_attacks if self.total_attacks > 0 else 0


class DefenseQuality(BaseModel):
    """Metrics for defense quality."""
    
    total_patches: int
    regression_count: int  # Patches that introduced new issues
    full_fix_count: int
    partial_fix_count: int
    
    @property
    def regression_rate(self) -> float:
        """Rate of patches that caused regressions."""
        return self.regression_count / self.total_patches if self.total_patches > 0 else 0
    
    @property
    def first_time_fix_rate(self) -> float:
        """Rate of full fixes."""
        return self.full_fix_count / self.total_patches if self.total_patches > 0 else 0


class ConvergenceMetrics(BaseModel):
    """Metrics for how quickly the system converged."""
    
    iterations_completed: int
    critical_at_start: int
    critical_at_end: int
    
    @property
    def vulnerability_reduction_rate(self) -> float:
        """How much critical vulnerabilities were reduced."""
        if self.critical_at_start == 0:
            return 1.0
        return 1.0 - (self.critical_at_end / self.critical_at_start)


class SeverityCalibration(BaseModel):
    """
    Domain-specific calibration for severity levels.
    
    What counts as CRITICAL varies by domain.
    """
    
    domain: str  # e.g., "fintech", "healthcare", "social"
    
    critical_criteria: str  # What counts as CRITICAL
    high_criteria: str      # What counts as HIGH
    
    # Example thresholds
    # fintech: any money loss > $1 = CRITICAL
    # healthcare: any PHI exposure = CRITICAL
    # social: any account takeover = CRITICAL


# Pre-built calibrations for common domains
SEVERITY_CALIBRATIONS = {
    "fintech": SeverityCalibration(
        domain="fintech",
        critical_criteria="Any unauthorized money movement or financial data exposure",
        high_criteria="Data accuracy issues or transaction delays > 24 hours",
    ),
    "healthcare": SeverityCalibration(
        domain="healthcare",
        critical_criteria="Any PHI exposure or patient safety risk",
        high_criteria="Audit trail gaps or access control failures",
    ),
    "social": SeverityCalibration(
        domain="social",
        critical_criteria="Account takeover, impersonation, or harassment enablement",
        high_criteria="Privacy leakage or content moderation bypass",
    ),
    "ecommerce": SeverityCalibration(
        domain="ecommerce",
        critical_criteria="Payment fraud, inventory manipulation, or customer data theft",
        high_criteria="Cart manipulation or pricing errors",
    ),
}


def calculate_attack_effectiveness(
    agent_name: str,
    all_vulns: List[dict],
    patched_vulns: List[int]
) -> AttackEffectiveness:
    """Calculate attack effectiveness for an agent."""
    agent_vulns = [v for v in all_vulns if v.get("agent") == agent_name]
    patched = sum(1 for v in agent_vulns if v.get("vulnerability_id") in patched_vulns)
    
    return AttackEffectiveness(
        agent=agent_name,
        total_attacks=len(agent_vulns),
        accepted_attacks=len(agent_vulns),  # Assume all passed validation
        patched_attacks=patched,
    )


def calculate_convergence_metrics(
    iterations: int,
    initial_critical: int,
    final_critical: int
) -> ConvergenceMetrics:
    """Calculate convergence metrics for a run."""
    return ConvergenceMetrics(
        iterations_completed=iterations,
        critical_at_start=initial_critical,
        critical_at_end=final_critical,
    )
