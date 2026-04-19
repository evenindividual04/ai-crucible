"""RED tests for PR9 evaluation criteria extensions.

These tests codify expected behavior for new criterion implementations.
They should fail until PR9 introduces the corresponding production code.
"""

from datetime import datetime, timezone

from crucible.eval import criteria_v2
from crucible.eval.schemas import Trace
from crucible.state import AttackChain, AttackChainStep, CrucibleState


def _minimal_trace(run_id: str = "pr9-test") -> Trace:
    return Trace(
        run_id=run_id,
        user_prompt="Design a secure auth and payments architecture",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        status="STABLE",
        max_iterations=3,
        events=[],
    )


def _state_with_chains(chain_count: int, confidence: float) -> CrucibleState:
    state = CrucibleState(user_prompt="test")
    for idx in range(1, chain_count + 1):
        state.attack_chains.append(
            AttackChain(
                chain_id=idx,
                steps=[
                    AttackChainStep(
                        vulnerability_id=idx,
                        step_number=1,
                        description=f"step-{idx}",
                        attack_progression="initial compromise",
                        confidence=confidence,
                    ),
                ],
                title=f"chain-{idx}",
                description="test chain",
                confidence=confidence,
                severity="HIGH",
                affected_components=[1],
            )
        )
    return state


def test_pr9_chain_quality_criterion_name_and_contract_red():
    """PR9: chain criterion exists and exposes expected name."""
    assert hasattr(criteria_v2, "ChainQualityCriterion")

    criterion = criteria_v2.ChainQualityCriterion()
    assert criterion.name == "chain_quality"


def test_pr9_chain_quality_scoring_monotonicity_red():
    """PR9: better chain outcomes must produce a higher chain quality score."""
    assert hasattr(criteria_v2, "ChainQualityCriterion")
    criterion = criteria_v2.ChainQualityCriterion()

    trace = _minimal_trace()
    weak_state = _state_with_chains(chain_count=1, confidence=0.2)
    strong_state = _state_with_chains(chain_count=3, confidence=0.9)

    weak = criterion.evaluate(trace, weak_state)
    strong = criterion.evaluate(trace, strong_state)

    assert 0.0 <= weak.value <= 1.0
    assert 0.0 <= strong.value <= 1.0
    assert strong.value > weak.value
    assert "total_chains" in strong.details
    assert "mean_chain_confidence" in strong.details


def test_pr9_strategy_quality_criterion_name_and_contract_red():
    """PR9: strategy criterion exists and exposes expected name."""
    assert hasattr(criteria_v2, "StrategyQualityCriterion")

    criterion = criteria_v2.StrategyQualityCriterion()
    assert criterion.name == "strategy_quality"


def test_pr9_strategy_quality_scoring_uses_simulation_payload_red():
    """PR9: strategy scoring must reflect comparative strategy simulation payload."""
    assert hasattr(criteria_v2, "StrategyQualityCriterion")
    criterion = criteria_v2.StrategyQualityCriterion()

    trace = _minimal_trace()
    state = CrucibleState(user_prompt="test")
    state.defender_strategy_simulation = {
        "runs": [
            {"strategy": "tactical-first", "patches_applied": 1, "mode": "QUICK_FIX"},
            {"strategy": "balanced", "patches_applied": 2, "mode": "QUICK_FIX"},
            {"strategy": "architecture-first", "patches_applied": 3, "mode": "ARCHITECT"},
        ],
        "comparative_metrics": {
            "by_strategy": {
                "tactical-first": {"patches_applied": 1, "mode": "QUICK_FIX"},
                "balanced": {"patches_applied": 2, "mode": "QUICK_FIX"},
                "architecture-first": {"patches_applied": 3, "mode": "ARCHITECT"},
            }
        },
        "winner": {
            "strategy": "architecture-first",
            "rationale": "Selected for strongest patch coverage.",
            "metric_deltas": {
                "tactical-first": 3.0,
                "balanced": 2.0,
                "architecture-first": 1.0,
            },
        },
    }

    score = criterion.evaluate(trace, state)

    assert 0.0 <= score.value <= 1.0
    assert score.details.get("winner_strategy") == "architecture-first"
    assert "metric_deltas" in score.details
    assert set(score.details["metric_deltas"]) == {
        "tactical-first",
        "balanced",
        "architecture-first",
    }
