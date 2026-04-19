
import pytest
from pydantic import ValidationError

from crucible.graph import determine_defender_routing
from crucible.state import CrucibleState, Vulnerability
from crucible.config import CrucibleConfig
import crucible.agents.specialized_defenders as specialized_defenders


@pytest.fixture
def make_state():
    def _make_state(
        *,
        iteration_count: int = 0,
        severity: str = "LOW",
        strategy: str = "tactical-first",
    ) -> CrucibleState:
        state = CrucibleState(user_prompt="test", iteration_count=iteration_count)
        state.vulnerabilities.append(
            Vulnerability(
                vulnerability_id=1,
                severity=severity,
                confidence=0.9,
                domain="SECURITY",
                title="test",
                description="test",
                attack_vector="test",
                iteration_found=iteration_count,
            )
        )
        state.active_vulnerabilities = [1]
        state.defender_strategy = strategy
        return state

    return _make_state


def test_defender_strategy_is_explicit_on_state_and_serializable(make_state):
    state = make_state(strategy="architecture-first")

    assert hasattr(state, "defender_strategy")

    payload = state.model_dump()
    assert payload["defender_strategy"] == "architecture-first"

    reloaded = CrucibleState.model_validate(payload)
    assert reloaded.defender_strategy == "architecture-first"


def test_defender_strategy_catalog_contains_three_supported_strategies():
    assert hasattr(specialized_defenders, "DEFENDER_STRATEGIES")

    assert set(specialized_defenders.DEFENDER_STRATEGIES) == {
        "tactical-first",
        "balanced",
        "architecture-first",
    }


def test_default_strategy_matches_current_legacy_routing_behavior(make_state):
    state_low = make_state(iteration_count=0, severity="LOW")
    legacy_low = determine_defender_routing(state_low)
    mode_low = specialized_defenders.select_defender_mode(state_low)

    assert state_low.defender_strategy == "tactical-first"
    assert legacy_low == "quick_fix"
    assert mode_low == "QUICK_FIX"

    state_critical_late = make_state(iteration_count=2, severity="CRITICAL")
    legacy_critical_late = determine_defender_routing(state_critical_late)
    mode_critical_late = specialized_defenders.select_defender_mode(state_critical_late)

    assert legacy_critical_late == "architect"
    assert mode_critical_late == "ARCHITECT"


@pytest.mark.parametrize(
    "strategy,iteration_count,severity,expected_mode",
    [
        ("tactical-first", 3, "CRITICAL", "ARCHITECT"),
        ("balanced", 2, "CRITICAL", "ARCHITECT"),
        ("architecture-first", 0, "CRITICAL", "ARCHITECT"),
        ("balanced", 0, "LOW", "QUICK_FIX"),
    ],
)
def test_strategy_policy_selects_defender_mode_from_state_conditions(
    make_state,
    strategy,
    iteration_count,
    severity,
    expected_mode,
):
    state = make_state(
        strategy=strategy,
        iteration_count=iteration_count,
        severity=severity,
    )

    assert specialized_defenders.select_defender_mode(state) == expected_mode


def test_determine_defender_routing_honors_selected_strategy(make_state):
    state = make_state(
        strategy="architecture-first",
        iteration_count=0,
        severity="CRITICAL",
    )

    assert determine_defender_routing(state) == "architect"


def test_config_rejects_invalid_defender_strategy():
    with pytest.raises(ValidationError):
        CrucibleConfig.load(overrides={
            "defender_strategy_sim": {"default_strategy": "unknown-strategy"}
        })


def test_default_routing_path_is_unchanged_when_strategy_simulation_disabled(make_state):
    state = make_state(iteration_count=2, severity="CRITICAL", strategy="tactical-first")

    cfg = CrucibleConfig.load(overrides={"defender_strategy_sim": {"enabled": False}})

    assert cfg.defender_strategy_sim.enabled is False
    assert determine_defender_routing(state) == "architect"
