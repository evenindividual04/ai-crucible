"""
Judge Controller for the AI Crucible.

The Judge is the deterministic decision-maker that:
- Validates designs
- Evaluates attacks
- Verifies patches
- Decides termination
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Literal, Optional
import logging

from crucible.config import get_config, CrucibleConfig
from crucible.state import CrucibleState, Vulnerability, Patch, AttackChain
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
        Evaluate new vulnerabilities and attack chains, decide next action.
        
        Considers both novel vulnerabilities and attack chain risk.
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
        
        # PR5: Compute chain risk (feature-flagged)
        chain_awareness_enabled = self.config.judge.enable_chain_awareness
        chain_risk = self.compute_total_chain_risk(state) if chain_awareness_enabled else 0.0
        chain_risk_threshold = self.config.judge.chain_risk_threshold
        
        # Decision logic: novel criticals OR chain risk threshold
        if novel_criticals:
            decision = JudgeDecision(
                decision="CONTINUE_TO_DEFEND",
                reason=f"Found {len(novel_criticals)} novel critical vulnerabilities (chain risk: {chain_risk:.2f})",
                timestamp=datetime.now(timezone.utc),
                iteration=state.iteration_count,
                novel_critical_count=len(novel_criticals),
                total_critical_count=total_criticals,
                duplicates_rejected=duplicates_rejected,
            )
        elif chain_awareness_enabled and chain_risk >= chain_risk_threshold:
            # High chain risk triggers defense even without novel vulns
            decision = JudgeDecision(
                decision="CONTINUE_TO_DEFEND",
                reason=f"High attack chain risk: {chain_risk:.2f} (threshold: {chain_risk_threshold:.2f})",
                timestamp=datetime.now(timezone.utc),
                iteration=state.iteration_count,
                novel_critical_count=0,
                total_critical_count=total_criticals,
                duplicates_rejected=duplicates_rejected,
            )
        elif novel:
            # Has novel but no blocking criticals, low chain risk
            decision = JudgeDecision(
                decision="CONTINUE_TO_DEFEND",
                reason=f"Found {len(novel)} novel vulnerabilities (chain risk: {chain_risk:.2f})",
                timestamp=datetime.now(timezone.utc),
                iteration=state.iteration_count,
                novel_critical_count=0,
                total_critical_count=total_criticals,
                duplicates_rejected=duplicates_rejected,
            )
        else:
            # No novel vulnerabilities, low chain risk
            decision = JudgeDecision(
                decision="TERMINATE_STABLE",
                reason=f"No novel vulnerabilities; chain risk: {chain_risk:.2f}",
                timestamp=datetime.now(timezone.utc),
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
            
            # V2 Check: Validate fix category vs severity
            if vuln.severity == "CRITICAL" and patch.fix_category == "TACTICAL":
                logger.warning(
                    f"Patch {patch.patch_id} uses TACTICAL fix for CRITICAL vulnerability. "
                    "This is risky but allowed."
                )

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
                    timestamp=datetime.now(timezone.utc),
                    iteration=iteration,
                    novel_critical_count=0,
                    total_critical_count=unpatched_criticals,
                )
            else:
                decision = JudgeDecision(
                    decision="TERMINATE_STABLE",
                    reason=f"Iteration cap reached ({max_iter}) with all criticals patched",
                    timestamp=datetime.now(timezone.utc),
                    iteration=iteration,
                )
            
            self.decisions.append(decision)
            return decision
        
        # PR5: Check for active attack chains (feature-flagged)
        chain_awareness_enabled = self.config.judge.enable_chain_awareness
        active_chains = self._filter_active_chains(state) if chain_awareness_enabled else []
        chain_risk = self.compute_total_chain_risk(state) if chain_awareness_enabled else 0.0
        
        # Check if we have unpatched criticals
        unpatched_criticals = state.get_unpatched_critical_count()
        
        if unpatched_criticals > 0:
            decision = JudgeDecision(
                decision="CONTINUE_TO_ATTACK",
                reason=f"Continuing: {unpatched_criticals} unpatched critical vulnerabilities remain (chain risk: {chain_risk:.2f})",
                timestamp=datetime.now(timezone.utc),
                iteration=iteration,
                total_critical_count=unpatched_criticals,
            )
        elif active_chains:
            # Even if no unpatched criticals, active chains require continuation
            decision = JudgeDecision(
                decision="CONTINUE_TO_ATTACK",
                reason=f"Continuing: {len(active_chains)} active attack chain(s) remain (risk: {chain_risk:.2f})",
                timestamp=datetime.now(timezone.utc),
                iteration=iteration,
                total_critical_count=0,
            )
        else:
            # No unpatched criticals, no active chains
            decision = JudgeDecision(
                decision="TERMINATE_STABLE",
                reason=f"All critical vulnerabilities patched; no active chains (risk: {chain_risk:.2f})",
                timestamp=datetime.now(timezone.utc),
                iteration=iteration,
            )
        
        self.decisions.append(decision)
        return decision


    # ========================================================================
    # CHAIN-AWARE DECISION LOGIC (PR5)
    # ========================================================================

    def compute_chain_effectiveness(self, chain: AttackChain) -> float:
        """
        Compute effectiveness score (0-1) for a single attack chain.
        
        Based on:
        - Step confidences (min for conservative strategy)
        - Chain severity (CRITICAL > HIGH > MEDIUM > LOW)
        - Chain length penalty (longer chains = lower score)
        
        Returns float in [0.0, 1.0].
        """
        if not chain.steps:
            return 0.0
        
        # Extract confidences from steps and apply configured strategy.
        confidences = [step.confidence for step in chain.steps]
        strategy = self.config.judge.chain_effectiveness_strategy.lower()
        if strategy == "mean":
            confidence_score = sum(confidences) / len(confidences) if confidences else 0.0
        elif strategy == "max":
            confidence_score = max(confidences) if confidences else 0.0
        else:
            if strategy != "min":
                logger.warning(
                    "Unknown chain_effectiveness_strategy '%s'; falling back to 'min'",
                    self.config.judge.chain_effectiveness_strategy,
                )
            confidence_score = min(confidences) if confidences else 0.0
        
        # Severity multiplier
        severity_multipliers = {
            "CRITICAL": 1.0,
            "HIGH": 0.8,
            "MEDIUM": 0.6,
            "LOW": 0.4,
        }
        severity_mult = severity_multipliers.get(chain.severity, 0.5)
        
        # Length penalty: longer chains are harder to execute
        # 1-step: 1.0, 2-step: 0.95, 3-step: 0.90, 4-step: 0.85, 5+: 0.80
        num_steps = len(chain.steps)
        length_penalty = max(0.80, 1.0 - (num_steps - 1) * 0.05)
        
        # Combined effectiveness
        effectiveness = confidence_score * severity_mult * length_penalty
        
        return effectiveness

    def compute_total_chain_risk(self, state: CrucibleState) -> float:
        """
        Compute total risk score from all active attack chains in state.
        
        Active chains are those where at least one step's vulnerability
        is not yet patched.
        
        Returns float in [0.0, 1.0], capped at 1.0.
        """
        active_chains = self._filter_active_chains(state)
        
        if not active_chains:
            return 0.0
        
        # Compute effectiveness for each chain
        effectiveness_scores = [
            self.compute_chain_effectiveness(chain)
            for chain in active_chains
        ]
        
        # Sum with cap at 1.0 (additive risk model)
        total_risk = min(1.0, sum(effectiveness_scores))
        
        return total_risk

    def _filter_active_chains(self, state: CrucibleState) -> List[AttackChain]:
        """
        Filter chains to only those with at least one unpatched step.
        
        A chain is "active" if ANY of its steps reference an unpatched vulnerability.
        """
        from crucible.patches_v2 import IncrementalPatch as IncPatch

        active = []
        fully_patched_ids = {
            p.target_vulnerability_id for p in state.patches
            if not (isinstance(p, IncPatch) and not p.full_fix)
        }
        
        for chain in state.attack_chains:
            # Check if at least one step is unpatched
            for step in chain.steps:
                vuln = state.get_vulnerability_by_id(step.vulnerability_id)
                if not vuln:
                    continue

                is_step_patched = (
                    step.vulnerability_id in fully_patched_ids
                    or vuln.is_patched
                )
                if not is_step_patched:
                    # Chain has at least one unpatched step
                    active.append(chain)
                    break
        
        return active

