"""
Judge Controller for the AI Crucible.

The Judge is the deterministic decision-maker that:
- Validates designs
- Evaluates attacks
- Verifies patches
- Decides termination
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional
import logging

from crucible.config import get_config, CrucibleConfig
from crucible.state import CrucibleState, Vulnerability, Patch
from crucible.judge.novelty import NoveltyChecker
from crucible.judge.verification import PatchVerifier

logger = logging.getLogger(__name__)


@dataclass
class JudgeDecision:
    """Represents a decision made by the Judge."""
    
    decision: Literal[
        "CONTINUE_TO_ATTACK",
        "CONTINUE_TO_DEFEND",
        "TERMINATE_STABLE",
        "TERMINATE_UNRESOLVED",
        "TERMINATE_FAILED",
    ]
    reason: str
    timestamp: datetime
    iteration: int
    
    # Metrics at decision time
    novel_critical_count: int = 0
    total_critical_count: int = 0
    duplicates_rejected: int = 0


class JudgeController:
    """
    Deterministic controller for the adversarial loop.
    
    The Judge is NOT an LLM - it's a rule-based decision maker.
    """
    
    def __init__(self, config: Optional[CrucibleConfig] = None):
        self.config = config or get_config()
        self.novelty_checker = NoveltyChecker(self.config)
        self.patch_verifier = PatchVerifier(self.config)
        self.decisions: List[JudgeDecision] = []
    
    def validate_design(self, state: CrucibleState) -> tuple[bool, str]:
        """
        Validate that the Architect produced a valid design.
        
        Checks:
        - At least 1 component exists
        - Each component has at least 1 assumption
        """
        if not state.design_components:
            return False, "FAILED_INCOMPLETE_DESIGN: No components generated"
        
        for comp in state.design_components:
            if not comp.assumptions:
                return False, f"FAILED_INCOMPLETE_DESIGN: Component '{comp.name}' has no assumptions"
        
        if not state.design_markdown.strip():
            return False, "FAILED_INCOMPLETE_DESIGN: Empty design markdown"
        
        return True, "Design validated successfully"
    
    def evaluate_attacks(
        self,
        state: CrucibleState,
        new_vulnerabilities: List[Vulnerability]
    ) -> tuple[List[Vulnerability], JudgeDecision]:
        """
        Evaluate new vulnerabilities and decide next action.
        
        Returns (filtered_vulnerabilities, decision).
        """
        # Filter to novel vulnerabilities
        novel = self.novelty_checker.filter_novel(
            new_vulnerabilities,
            state.vulnerabilities
        )
        
        duplicates_rejected = len(new_vulnerabilities) - len(novel)
        
        # Count novel criticals with sufficient confidence
        confidence_threshold = self.config.confidence.blocking_threshold
        novel_criticals = [
            v for v in novel
            if v.severity == "CRITICAL" and v.confidence >= confidence_threshold
        ]
        
        total_criticals = sum(
            1 for v in novel if v.severity == "CRITICAL"
        )
        
        # Make decision
        if novel_criticals:
            decision = JudgeDecision(
                decision="CONTINUE_TO_DEFEND",
                reason=f"Found {len(novel_criticals)} novel critical vulnerabilities",
                timestamp=datetime.utcnow(),
                iteration=state.iteration_count,
                novel_critical_count=len(novel_criticals),
                total_critical_count=total_criticals,
                duplicates_rejected=duplicates_rejected,
            )
        elif novel:
            # Has novel but no blocking criticals
            decision = JudgeDecision(
                decision="CONTINUE_TO_DEFEND",
                reason=f"Found {len(novel)} novel vulnerabilities (no blocking criticals)",
                timestamp=datetime.utcnow(),
                iteration=state.iteration_count,
                novel_critical_count=0,
                total_critical_count=total_criticals,
                duplicates_rejected=duplicates_rejected,
            )
        else:
            # No novel vulnerabilities
            decision = JudgeDecision(
                decision="TERMINATE_STABLE",
                reason="No novel vulnerabilities found",
                timestamp=datetime.utcnow(),
                iteration=state.iteration_count,
                novel_critical_count=0,
                total_critical_count=0,
                duplicates_rejected=duplicates_rejected,
            )
        
        self.decisions.append(decision)
        return novel, decision
    
    def verify_patches(
        self,
        state: CrucibleState,
        old_design: str,
        new_design: str,
        patches: List[Patch]
    ) -> tuple[bool, str]:
        """
        Verify patches are valid and didn't introduce regressions.
        
        Returns (is_valid, reason).
        """
        if not patches:
            logger.warning("No patches applied")
            return True, "No patches to verify"
        
        # Check each patch references a valid vulnerability
        for patch in patches:
            vuln = state.get_vulnerability_by_id(patch.target_vulnerability_id)
            if vuln is None:
                return False, f"FAILED_INVALID_REFERENCE: Patch references non-existent vulnerability {patch.target_vulnerability_id}"
        
        # Check patch count limit
        max_patches = self.config.agents.defender.max_patches_per_iteration
        if len(patches) > max_patches:
            logger.warning(f"Patch count {len(patches)} exceeds limit {max_patches}")
            # Don't fail, just warn (patches will be truncated by graph)
        
        # Check for meaningful change
        is_effective, reason = self.patch_verifier.verify_patch_impact(
            old_design, new_design, patches[0]  # Check first patch
        )
        
        if not is_effective:
            logger.warning(f"Patch may be ineffective: {reason}")
            # Don't fail, but log for audit
        
        # Check for regressions
        patched_vulns = [
            state.get_vulnerability_by_id(p.target_vulnerability_id)
            for p in patches
        ]
        patched_vulns = [v for v in patched_vulns if v is not None]
        
        regressions = self.patch_verifier.detect_regression(new_design, patched_vulns)
        
        if regressions:
            return False, f"FAILED_REGRESSION: Potential regression detected for {len(regressions)} vulnerabilities"
        
        return True, "Patches verified successfully"
    
    def decide_termination(self, state: CrucibleState) -> JudgeDecision:
        """
        Decide if the loop should terminate.
        
        Called after each iteration.
        """
        iteration = state.iteration_count
        max_iter = state.max_iterations
        
        # Check iteration cap
        if iteration >= max_iter:
            unpatched_criticals = state.get_unpatched_critical_count()
            
            if unpatched_criticals > 0:
                decision = JudgeDecision(
                    decision="TERMINATE_UNRESOLVED",
                    reason=f"Iteration cap reached ({max_iter}) with {unpatched_criticals} unpatched critical vulnerabilities",
                    timestamp=datetime.utcnow(),
                    iteration=iteration,
                    novel_critical_count=0,
                    total_critical_count=unpatched_criticals,
                )
            else:
                decision = JudgeDecision(
                    decision="TERMINATE_STABLE",
                    reason=f"Iteration cap reached ({max_iter}) with all criticals patched",
                    timestamp=datetime.utcnow(),
                    iteration=iteration,
                )
            
            self.decisions.append(decision)
            return decision
        
        # Check if we have unpatched criticals
        unpatched_criticals = state.get_unpatched_critical_count()
        
        if unpatched_criticals > 0:
            decision = JudgeDecision(
                decision="CONTINUE_TO_ATTACK",
                reason=f"Continuing: {unpatched_criticals} unpatched critical vulnerabilities remain",
                timestamp=datetime.utcnow(),
                iteration=iteration,
                total_critical_count=unpatched_criticals,
            )
        else:
            decision = JudgeDecision(
                decision="TERMINATE_STABLE",
                reason="All critical vulnerabilities have been patched",
                timestamp=datetime.utcnow(),
                iteration=iteration,
            )
        
        self.decisions.append(decision)
        return decision
