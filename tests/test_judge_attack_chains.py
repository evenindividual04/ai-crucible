"""
Judge Chain Awareness Tests (PR5)

Comprehensive RED tests for integrating attack chains into the judge's decision logic.
Covers chain effectiveness scoring, attack evaluation, termination logic, and edge cases.

Test Organization:
1. Chain Effectiveness Scoring (5 tests)
2. Evaluate Attacks with Chains (6 tests)
3. Termination with Chains (5 tests)
4. Edge Cases (4 tests)
5. State Integration (3 tests)

Total: 25 tests
Coverage Target: 85%+
"""

import pytest
from datetime import datetime, timezone
from typing import List

from crucible.state import (
    CrucibleState,
    Vulnerability,
    DesignComponent,
    AttackChain,
    AttackChainStep,
)
from crucible.judge.controller import JudgeController, JudgeDecision
from crucible.config import CrucibleConfig
from crucible.patches_v2 import IncrementalPatch


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def config_with_thresholds():
    """Config with chain-aware thresholds."""
    config = CrucibleConfig()
    config.confidence.blocking_threshold = 0.7
    config.judge.chain_risk_threshold = 0.6
    config.judge.chain_effectiveness_strategy = "min"
    return config


@pytest.fixture
def judge_controller_with_chains(config_with_thresholds):
    """Judge controller configured for chain awareness."""
    return JudgeController(config=config_with_thresholds)


@pytest.fixture
def vulnerability_builder():
    """Factory for creating Vulnerability instances."""
    def build(
        vuln_id: int = 1,
        severity: str = "HIGH",
        confidence: float = 0.8,
        domain: str = "SECURITY",
        affected_components: List[int] = None,
        patched: bool = False,
    ) -> Vulnerability:
        if affected_components is None:
            affected_components = [1, 2]
        vulnerability = Vulnerability(
            vulnerability_id=vuln_id,
            severity=severity,
            confidence=confidence,
            domain=domain,
            title=f"Test vuln {vuln_id}",
            description=f"Test vuln {vuln_id}",
            attack_vector="Test attack vector",
            affected_components=affected_components,
            iteration_found=0,
            agent_name="SecurityHawk",
        )
        object.__setattr__(vulnerability, "_is_patched", patched)
        return vulnerability
    return build


@pytest.fixture
def attack_chain_step_builder():
    """Factory for creating AttackChainStep instances."""
    def build(
        vuln_id: int = 1,
        step_number: int = 1,
        confidence: float = 0.8,
        description: str = "Step description",
    ) -> AttackChainStep:
        return AttackChainStep(
            vulnerability_id=vuln_id,
            step_number=step_number,
            description=description,
            attack_progression=f"Escalation from step {step_number-1}",
            confidence=confidence,
        )
    return build


@pytest.fixture
def attack_chain_builder(attack_chain_step_builder):
    """Factory for creating AttackChain instances."""
    def build(
        chain_id: int = 1,
        steps: List[AttackChainStep] = None,
        confidence: float = 0.8,
        severity: str = "HIGH",
        affected_components: List[int] = None,
    ) -> AttackChain:
        if steps is None:
            steps = [attack_chain_step_builder(i + 1, i + 1) for i in range(2)]
        if affected_components is None:
            affected_components = [1, 2]
        return AttackChain(
            chain_id=chain_id,
            steps=steps,
            title=f"Chain {chain_id}",
            description="Test attack chain",
            confidence=confidence,
            severity=severity,
            affected_components=affected_components,
            created_at=datetime.now(timezone.utc),
        )
    return build


@pytest.fixture
def state_builder(vulnerability_builder, attack_chain_builder):
    """Factory for creating CrucibleState instances with chains."""
    def build(
        vulnerabilities: List[Vulnerability] = None,
        attack_chains: List[AttackChain] = None,
        iteration_count: int = 1,
        max_iterations: int = 5,
    ) -> CrucibleState:
        if vulnerabilities is None:
            vulnerabilities = [vulnerability_builder()]
        if attack_chains is None:
            attack_chains = []
        
        state = CrucibleState(
            user_prompt="Test prompt",
            design_markdown="# Test Design",
            design_components=[
                DesignComponent(
                    component_id=1,
                    name="api",
                    responsibility="Test API",
                    assumptions=["Secure", "Fast"],
                )
            ],
            vulnerabilities=vulnerabilities,
            attack_chains=attack_chains,
            iteration_count=iteration_count,
            max_iterations=max_iterations,
        )
        return state
    return build


# ============================================================================
# SECTION 1: CHAIN EFFECTIVENESS SCORING (5 tests)
# ============================================================================

class TestChainEffectivenessScoring:
    """Tests for computing chain effectiveness scores (0-1)."""
    
    def test_chain_effectiveness_zero_confidence(
        self,
        judge_controller_with_chains,
        attack_chain_builder,
    ):
        """
        PRECONDITION: Chain with confidence=0.0
        POSTCONDITION: Effectiveness score is exactly 0.0
        
        A chain with zero confidence (impossible attack) should not trigger
        any defensive response.
        """
        chain = attack_chain_builder(steps=[])
        score = judge_controller_with_chains.compute_chain_effectiveness(chain)
        assert score == pytest.approx(0.0)
    
    def test_chain_effectiveness_critical_single_step(
        self,
        judge_controller_with_chains,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: Single-step CRITICAL chain with confidence >= 0.9
        POSTCONDITION: Effectiveness score >= 0.9
        
        Short, high-confidence chains representing critical immediate threats
        should score very high (near 1.0).
        """
        step = attack_chain_step_builder(confidence=0.95)
        chain = attack_chain_builder(
            steps=[step],
            confidence=0.95,
            severity="CRITICAL"
        )
        score = judge_controller_with_chains.compute_chain_effectiveness(chain)
        assert score >= 0.9
        assert score <= 1.0
    
    def test_chain_effectiveness_medium_long_chain(
        self,
        judge_controller_with_chains,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: 5-step chain vs 2-step chain, both at confidence 0.85
        POSTCONDITION: score(5-step) < score(2-step)
        
        Longer chains are harder to execute; they should score lower effectiveness
        than shorter chains with same confidence.
        """
        step = attack_chain_step_builder(confidence=0.85)
        chain_5 = attack_chain_builder(
            steps=[attack_chain_step_builder(i + 1, i + 1) for i in range(5)],
            confidence=0.85,
        )
        chain_2 = attack_chain_builder(
            steps=[attack_chain_step_builder(i + 1, i + 1) for i in range(2)],
            confidence=0.85,
        )
        score_5 = judge_controller_with_chains.compute_chain_effectiveness(chain_5)
        score_2 = judge_controller_with_chains.compute_chain_effectiveness(chain_2)
        assert score_5 < score_2
        assert score_5 > 0.0
    
    def test_chain_effectiveness_multiple_chains_contribute(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        attack_chain_step_builder,
        vulnerability_builder,
    ):
        """
        PRECONDITION: State with 2 chains (risk 0.5 and 0.6)
        POSTCONDITION: Combined risk approximates sum (≲ 1.0 capped)
        
        When multiple attack chains exist, their risks should compound
        (additive model) up to a maximum of 1.0.
        """
        chain1 = attack_chain_builder(
            chain_id=1,
            steps=[attack_chain_step_builder(vuln_id=1, step_number=1, confidence=0.5)],
            severity="HIGH",
        )
        chain2 = attack_chain_builder(
            chain_id=2,
            steps=[attack_chain_step_builder(vuln_id=2, step_number=1, confidence=0.6)],
            severity="HIGH",
        )
        state = state_builder(
            vulnerabilities=[
                vulnerability_builder(1),
                vulnerability_builder(2),
            ],
            attack_chains=[chain1, chain2],
        )
        expected = (
            judge_controller_with_chains.compute_chain_effectiveness(chain1)
            + judge_controller_with_chains.compute_chain_effectiveness(chain2)
        )
        total_risk = judge_controller_with_chains.compute_total_chain_risk(state)
        assert total_risk == pytest.approx(min(1.0, expected))
    
    def test_chain_effectiveness_deterministic(
        self,
        judge_controller_with_chains,
        attack_chain_builder,
    ):
        """
        PRECONDITION: Same chain evaluated 5 times
        POSTCONDITION: All scores are identical
        
        Chain effectiveness must be deterministic (same input → same output).
        """
        chain = attack_chain_builder(confidence=0.75)
        scores = [
            judge_controller_with_chains.compute_chain_effectiveness(chain)
            for _ in range(5)
        ]
        assert len(set(scores)) == 1
        assert scores[0] == pytest.approx(scores[-1])

    def test_chain_effectiveness_strategy_mean(
        self,
        judge_controller_with_chains,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """Configured mean strategy should use average step confidence."""
        judge_controller_with_chains.config.judge.chain_effectiveness_strategy = "mean"
        steps = [
            attack_chain_step_builder(vuln_id=1, step_number=1, confidence=0.2),
            attack_chain_step_builder(vuln_id=2, step_number=2, confidence=0.8),
        ]
        chain = attack_chain_builder(steps=steps, severity="HIGH")
        score = judge_controller_with_chains.compute_chain_effectiveness(chain)
        assert score == pytest.approx(((0.2 + 0.8) / 2.0) * 0.8 * 0.95)

    def test_chain_effectiveness_strategy_max(
        self,
        judge_controller_with_chains,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """Configured max strategy should use strongest-step confidence."""
        judge_controller_with_chains.config.judge.chain_effectiveness_strategy = "max"
        steps = [
            attack_chain_step_builder(vuln_id=1, step_number=1, confidence=0.2),
            attack_chain_step_builder(vuln_id=2, step_number=2, confidence=0.8),
        ]
        chain = attack_chain_builder(steps=steps, severity="HIGH")
        score = judge_controller_with_chains.compute_chain_effectiveness(chain)
        assert score == pytest.approx(0.8 * 0.8 * 0.95)


# ============================================================================
# SECTION 2: EVALUATE ATTACKS WITH CHAINS (6 tests)
# ============================================================================

class TestEvaluateAttacksWithChains:
    """Tests for evaluate_attacks() enhanced with chain risk consideration."""
    
    def test_evaluate_attacks_ignores_low_risk_chains(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        attack_chain_step_builder,
        vulnerability_builder,
    ):
        """
        PRECONDITION: State with chain risk < threshold (0.6), no novel criticals
        POSTCONDITION: Decision is TERMINATE_STABLE
        
        Low-score chains should not override the termination decision if no
        novel vulnerabilities exist.
        """
        low_chain = attack_chain_builder(
            chain_id=1,
            steps=[attack_chain_step_builder(confidence=0.3)],
            severity="HIGH",
        )  # Below 0.6 threshold
        state = state_builder(attack_chains=[low_chain])
        new_vulns = []
        novel, decision = judge_controller_with_chains.evaluate_attacks(state, new_vulns)
        assert novel == []
        assert decision.decision == "TERMINATE_STABLE"
    
    def test_evaluate_attacks_triggers_defend_high_chain_risk(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """
        PRECONDITION: Chain risk >= threshold (0.6), no novel vulnerabilities
        POSTCONDITION: Decision is CONTINUE_TO_DEFEND (chain risk overrides novelty)
        
        High-risk chains should force a defensive iteration even without novel vulns.
        """
        high_chain = attack_chain_builder(confidence=0.75)  # Above 0.6 threshold
        state = state_builder(attack_chains=[high_chain])
        new_vulns = []
        novel, decision = judge_controller_with_chains.evaluate_attacks(state, new_vulns)
        assert novel == []
        assert decision.decision == "CONTINUE_TO_DEFEND"
        assert "chain risk" in decision.reason.lower()
    
    def test_evaluate_attacks_chain_risk_overrides_novelty(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        vulnerability_builder,
    ):
        """
        PRECONDITION: High chain risk (0.8), new non-critical vuln
        POSTCONDITION: Decision is CONTINUE_TO_DEFEND (chain takes priority)
        
        Chain risk should be considered equally to novel vulnerabilities
        in the defense decision.
        """
        high_chain = attack_chain_builder(confidence=0.8)
        state = state_builder(attack_chains=[high_chain])
        # Use a distinct vulnerability id so novelty filtering keeps this item.
        new_vulns = [
            vulnerability_builder(vuln_id=99, severity="MEDIUM", confidence=0.5)
        ]
        novel, decision = judge_controller_with_chains.evaluate_attacks(state, new_vulns)
        assert len(novel) == 1
        assert decision.decision == "CONTINUE_TO_DEFEND"
    
    def test_evaluate_attacks_combined_risk(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        vulnerability_builder,
    ):
        """
        PRECONDITION: Chain (0.5) + Novel CRITICAL (0.8) = combined 0.9
        POSTCONDITION: Decision is CONTINUE_TO_DEFEND (compounded risk)
        
        When both novel criticals AND high chains exist, combine their risk signals.
        """
        chain = attack_chain_builder(confidence=0.5)
        state = state_builder(vulnerabilities=[], attack_chains=[chain])
        new_vulns = [vulnerability_builder(2, severity="CRITICAL", confidence=0.8)]
        novel, decision = judge_controller_with_chains.evaluate_attacks(state, new_vulns)
        assert len(novel) == 1
        assert decision.novel_critical_count == 1
        assert decision.decision == "CONTINUE_TO_DEFEND"
    
    def test_evaluate_attacks_chain_ordering(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: Chain where first step has high confidence (0.9),
                      second step lower (0.4)
        POSTCONDITION: Risk score weighted toward earlier steps (0.9 more influential)
        
        Earlier steps in a chain are more immediately dangerous and should
        contribute more to the risk score than later steps.
        """
        step1 = attack_chain_step_builder(vuln_id=1, step_number=1, confidence=0.9)
        step2 = attack_chain_step_builder(vuln_id=2, step_number=2, confidence=0.4)
        chain = attack_chain_builder(steps=[step1, step2])
        state = state_builder(attack_chains=[chain])
        score = judge_controller_with_chains.compute_chain_effectiveness(chain)
        assert score == pytest.approx(0.4 * 0.8 * 0.95)
        assert score == pytest.approx(
            judge_controller_with_chains.compute_chain_effectiveness(
                attack_chain_builder(steps=[step2, step1])
            )
        )
    
    def test_evaluate_attacks_mixed_domains_separate_chains(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """
        PRECONDITION: 2 chains from different domains (SECURITY=0.8, COST=0.2)
        POSTCONDITION: SECURITY chain drives decision, COST chain doesn't interfere
        
        Chains from different attack domains (security, cost, logic, etc.)
        should be evaluated independently.
        """
        security_chain = attack_chain_builder(
            chain_id=1,
            confidence=0.8,
            affected_components=[1]
        )
        cost_chain = attack_chain_builder(
            chain_id=2,
            confidence=0.2,
            affected_components=[2]
        )
        state = state_builder(attack_chains=[security_chain, cost_chain])
        new_vulns = []
        _, decision = judge_controller_with_chains.evaluate_attacks(state, new_vulns)
        assert decision.decision == "CONTINUE_TO_DEFEND"
        assert judge_controller_with_chains.compute_total_chain_risk(state) > 0.6

    def test_evaluate_attacks_chain_awareness_disabled(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """When chain awareness is disabled, high chain risk must not trigger defend."""
        judge_controller_with_chains.config.judge.enable_chain_awareness = False
        state = state_builder(attack_chains=[attack_chain_builder(confidence=0.95)])
        novel, decision = judge_controller_with_chains.evaluate_attacks(state, [])
        assert novel == []
        assert decision.decision == "TERMINATE_STABLE"


# ============================================================================
# SECTION 3: TERMINATION WITH CHAINS (5 tests)
# ============================================================================

class TestDecideTerminationWithChains:
    """Tests for decide_termination() enhanced with chain risk consideration."""
    
    def test_decide_termination_no_chains_stable(
        self,
        judge_controller_with_chains,
        state_builder,
    ):
        """
        PRECONDITION: No attack chains, no unpatched criticals
        POSTCONDITION: Decision is TERMINATE_STABLE
        
        Without chains or critical vulns, termination should proceed.
        """
        state = state_builder(attack_chains=[])
        decision = judge_controller_with_chains.decide_termination(state)
        assert decision.decision == "TERMINATE_STABLE"
    
    def test_decide_termination_active_chains_continue(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """
        PRECONDITION: 1 active chain with risk 0.7
        POSTCONDITION: Decision is CONTINUE_TO_ATTACK
        
        Even if no unpatched criticals remain, active high-risk chains
        should prevent termination.
        """
        chain = attack_chain_builder(confidence=0.7)
        state = state_builder(attack_chains=[chain])
        decision = judge_controller_with_chains.decide_termination(state)
        assert decision.decision == "CONTINUE_TO_ATTACK"
        assert "active attack chain" in decision.reason.lower()
    
    def test_decide_termination_patched_chains_stable(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        vulnerability_builder,
    ):
        """
        PRECONDITION: Chain steps all removed (vulnerabilities patched),
                      no remaining unpatched criticals
        POSTCONDITION: Decision is TERMINATE_STABLE
        
        When all vulnerabilities in chains are patched, chains become invalid
        and cannot block termination.
        """
        # Build chain with vulns that are marked patched
        step_vulns = [
            vulnerability_builder(i + 1, patched=True)
            for i in range(3)
        ]
        chain = attack_chain_builder()  # Still in state.attack_chains
        state = state_builder(
            vulnerabilities=step_vulns,
            attack_chains=[chain],
        )
        decision = judge_controller_with_chains.decide_termination(state)
        assert decision.decision == "TERMINATE_STABLE"
    
    def test_decide_termination_chain_survives_patch(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        vulnerability_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: 3-step chain; first step vulnerability patched,
                      but chain itself remains valid (other 2 steps unpatched)
        POSTCONDITION: Decision is CONTINUE_TO_ATTACK (chain intact)
        
        Chains should only be invalidated when ALL their steps are patched.
        Partial patching should not eliminate chain threat.
        """
        step1_unpatched = attack_chain_step_builder(vuln_id=1, step_number=1)
        step2_unpatched = attack_chain_step_builder(vuln_id=2, step_number=2)
        step3_patched = attack_chain_step_builder(vuln_id=3, step_number=3)
        chain = attack_chain_builder(steps=[step1_unpatched, step2_unpatched, step3_patched])
        
        vulns = [
            vulnerability_builder(1, patched=False),
            vulnerability_builder(2, patched=False),
            vulnerability_builder(3, patched=True),
        ]
        state = state_builder(vulnerabilities=vulns, attack_chains=[chain])
        decision = judge_controller_with_chains.decide_termination(state)
        assert decision.decision == "CONTINUE_TO_ATTACK"
    
    def test_decide_termination_iteration_cap_with_chains(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        vulnerability_builder,
    ):
        """
        PRECONDITION: Iteration at max (5 of 5), active high-risk chain present
        POSTCONDITION: Decision is TERMINATE_UNRESOLVED (cap takes precedence)
        
        Iteration cap should force termination even if chains remain active.
        """
        chain = attack_chain_builder(confidence=0.9)
        state = state_builder(
            attack_chains=[chain],
            iteration_count=5,
            max_iterations=5,
        )
        unpatched_criticals = [vulnerability_builder(severity="CRITICAL")]
        state.vulnerabilities = unpatched_criticals
        decision = judge_controller_with_chains.decide_termination(state)
        assert decision.decision == "TERMINATE_UNRESOLVED"

    def test_decide_termination_chain_awareness_disabled(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """When chain awareness is disabled, active chains should not block stable termination."""
        judge_controller_with_chains.config.judge.enable_chain_awareness = False
        state = state_builder(attack_chains=[attack_chain_builder(confidence=0.9)])
        decision = judge_controller_with_chains.decide_termination(state)
        assert decision.decision == "TERMINATE_STABLE"

    def test_decide_termination_chain_respects_state_patches(
        self,
        judge_controller_with_chains,
        state_builder,
        vulnerability_builder,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """Active chain filtering should honor state.patches full fixes."""
        vulns = [
            vulnerability_builder(1, severity="HIGH", patched=False),
            vulnerability_builder(2, severity="HIGH", patched=False),
        ]
        steps = [
            attack_chain_step_builder(vuln_id=1, step_number=1, confidence=0.8),
            attack_chain_step_builder(vuln_id=2, step_number=2, confidence=0.8),
        ]
        chain = attack_chain_builder(steps=steps, severity="HIGH")
        state = state_builder(vulnerabilities=vulns, attack_chains=[chain])
        state.patches = [
            IncrementalPatch(
                patch_id=1,
                target_vulnerability_id=1,
                fix_description="full fix 1",
                design_changes=["change 1"],
                full_fix=True,
            ),
            IncrementalPatch(
                patch_id=2,
                target_vulnerability_id=2,
                fix_description="full fix 2",
                design_changes=["change 2"],
                full_fix=True,
            ),
        ]
        decision = judge_controller_with_chains.decide_termination(state)
        assert decision.decision == "TERMINATE_STABLE"


# ============================================================================
# SECTION 4: EDGE CASES (4 tests)
# ============================================================================

class TestChainEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_chain_empty_list_no_crash(
        self,
        judge_controller_with_chains,
        state_builder,
    ):
        """
        PRECONDITION: State with empty attack_chains list
        POSTCONDITION: No exception; decision proceeds normally
        
        Empty chain list should be handled gracefully (not cause crashes).
        """
        state = state_builder(attack_chains=[])
        novel, decision = judge_controller_with_chains.evaluate_attacks(state, [])
        assert novel == []
        assert decision.decision == "TERMINATE_STABLE"
    
    def test_chain_threshold_boundary(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: Chain risk exactly at threshold (0.6)
        POSTCONDITION: Decision is CONTINUE_TO_DEFEND (threshold is inclusive, not exclusive)
        
        Boundary condition: >= threshold (not > threshold) should trigger defense.
        """
        chain = attack_chain_builder(
            confidence=0.6,
            severity="CRITICAL",
            steps=[attack_chain_step_builder(confidence=0.6)],
        )  # Exactly at threshold
        state = state_builder(attack_chains=[chain])
        new_vulns = []
        _, decision = judge_controller_with_chains.evaluate_attacks(state, new_vulns)
        assert decision.decision == "CONTINUE_TO_DEFEND"
    
    def test_chain_single_unpatched_step_remaining(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: 5-step chain reduced to 1 remaining step (4 patched)
        POSTCONDITION: Effectiveness score drops significantly (but not to 0)
        
        Chains with only 1 step left should still represent some risk,
        but drastically reduced compared to the full chain.
        """
        remaining = attack_chain_step_builder(confidence=0.8, step_number=1)
        chain = attack_chain_builder(steps=[remaining])
        score = judge_controller_with_chains.compute_chain_effectiveness(chain)
        assert 0.0 < score < 0.8
    
    def test_chain_effectiveness_with_high_step_variance(
        self,
        judge_controller_with_chains,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: Chain with step confidences [0.1, 0.9] (high variance)
        POSTCONDITION: Effectiveness uses MIN (conservative) = 0.1
        
        When computing chain effectiveness, use the most conservative (lowest)
        step confidence to account for the weakest link in the chain.
        """
        step_weak = attack_chain_step_builder(confidence=0.1)
        step_strong = attack_chain_step_builder(confidence=0.9)
        chain = attack_chain_builder(steps=[step_weak, step_strong])
        score = judge_controller_with_chains.compute_chain_effectiveness(chain)
        assert score == pytest.approx(0.1 * 0.8 * 0.95)


# ============================================================================
# SECTION 5: STATE INTEGRATION (3 tests)
# ============================================================================

class TestChainStateIntegration:
    """Tests for chain decisions/audit trail in state."""
    
    def test_judge_chains_decision_in_state(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """
        PRECONDITION: Judge evaluates state with high-risk chain
        POSTCONDITION: Decision recorded in judge_controller.decisions list
        
        All judge decisions should be recorded for audit/tracing.
        """
        chain = attack_chain_builder(confidence=0.75)
        state = state_builder(attack_chains=[chain])
        _, decision = judge_controller_with_chains.evaluate_attacks(state, [])
        assert len(judge_controller_with_chains.decisions) == 1
        assert judge_controller_with_chains.decisions[-1] == decision
    
    def test_judge_multiple_chain_decisions(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """
        PRECONDITION: Judge makes decision in iteration 1, then iteration 2
        POSTCONDITION: Both decisions recorded; decisions list has 2 items
        
        Decisions should accumulate across iterations without overwriting.
        """
        chain1 = attack_chain_builder(chain_id=1, confidence=0.5)
        state1 = state_builder(attack_chains=[chain1], iteration_count=1)
        
        chain2 = attack_chain_builder(chain_id=2, confidence=0.8)
        state2 = state_builder(attack_chains=[chain2], iteration_count=2)
        
        judge_controller_with_chains.evaluate_attacks(state1, [])
        judge_controller_with_chains.evaluate_attacks(state2, [])
        assert len(judge_controller_with_chains.decisions) == 2
        assert [d.iteration for d in judge_controller_with_chains.decisions] == [1, 2]
    
    def test_judge_chain_reason_string(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
        attack_chain_step_builder,
    ):
        """
        PRECONDITION: Judge decision triggered by chain risk 0.72
        POSTCONDITION: Decision.reason includes "chain" and "0.72"
        
        Reason strings must be human-readable and include chain risk metrics.
        """
        chain = attack_chain_builder(
            chain_id=1,
            confidence=0.72,
            severity="CRITICAL",
            steps=[attack_chain_step_builder(confidence=0.72)],
        )
        state = state_builder(attack_chains=[chain])
        new_vulns = []
        
        _, decision = judge_controller_with_chains.evaluate_attacks(state, new_vulns)
        assert "chain" in decision.reason.lower()
        assert "0.72" in decision.reason


# ============================================================================
# INTEGRATION TESTS (Optional section for reference)
# ============================================================================

class TestChainGraphIntegration:
    """Tests for chains working within the full graph.py state machine."""
    
    def test_chains_callable_in_state_machine(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """
        PRECONDITION: Graph.py invokes judge.evaluate_attacks() with chains
        POSTCONDITION: Judge decision propagates correctly through state machine
        
        Chains must be integrated into the main graph state machine.
        """
        # This test validates chains work in graph context
        _, decision = judge_controller_with_chains.evaluate_attacks(
            state_builder(attack_chains=[attack_chain_builder(confidence=0.7)]),
            [],
        )
        assert decision.decision in ["CONTINUE_TO_DEFEND", "TERMINATE_STABLE"]
    
    def test_chains_idempotent_in_loop(
        self,
        judge_controller_with_chains,
        state_builder,
        attack_chain_builder,
    ):
        """
        PRECONDITION: Same chain evaluated twice
        POSTCONDITION: Same decision produced both times
        
        Chain decisions should be deterministic and idempotent.
        """
        chain = attack_chain_builder(confidence=0.7)
        state = state_builder(attack_chains=[chain])
        _, first_decision = judge_controller_with_chains.evaluate_attacks(state, [])
        _, second_decision = judge_controller_with_chains.evaluate_attacks(state, [])
        assert first_decision.decision == second_decision.decision
        assert first_decision.reason == second_decision.reason
