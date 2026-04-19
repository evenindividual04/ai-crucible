"""Tests for graph tracing integration."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible import graph
from crucible.eval.schemas import AgentType
from crucible.state import CrucibleState, DesignComponent, Vulnerability


def make_tracer_spy():
    return SimpleNamespace(
        iteration_start=MagicMock(),
        iteration_end=MagicMock(),
        agent_invoke=MagicMock(),
        agent_complete=MagicMock(),
        design_validated=MagicMock(),
        vulnerability_found=MagicMock(),
        vulnerability_duplicate=MagicMock(),
        patch_applied=MagicMock(),
        patch_rejected=MagicMock(),
        judge_decision=MagicMock(),
        finalize=MagicMock(),
    )


def make_display_spy():
    return SimpleNamespace(
        show_agent_activity=MagicMock(),
        clear_agent_activity=MagicMock(),
        print_event=MagicMock(),
        print_security_score=MagicMock(),
    )


def test_architect_node_emits_agent_trace(monkeypatch):
    tracer = make_tracer_spy()
    display = make_display_spy()

    class FakeArchitectAgent:
        def invoke(self, user_prompt):
            return SimpleNamespace(
                design_markdown="# Design",
                components=[
                    SimpleNamespace(
                        name="API Gateway",
                        responsibility="Handle requests",
                        assumptions=["TLS is enabled"],
                        dependencies=[],
                    )
                ],
            )

        async def cleanup(self):
            return None

    monkeypatch.setattr(graph, "get_tracer", lambda: tracer)
    monkeypatch.setattr(graph, "get_display", lambda: display)
    monkeypatch.setattr(graph, "ArchitectAgent", FakeArchitectAgent)
    monkeypatch.setattr(graph, "cleanup_agent_sync", lambda agent: None)

    state = CrucibleState(user_prompt="Design a secure API")

    result = graph.architect_node(state)

    tracer.agent_invoke.assert_called_once_with(
        "Architect",
        "ArchitectAgent",
        input_prompt="Design a secure API",
    )
    tracer.agent_complete.assert_called_once_with(
        agent_type="Architect",
        agent_name="ArchitectAgent",
        success=True,
        vulnerabilities_found=0,
        tokens_used=0,
        duration_ms=None,
        error_message=None,
    )
    assert result["status"] == "ROUTING"


def test_validate_design_node_emits_design_validation(monkeypatch):
    tracer = make_tracer_spy()

    class FakeJudge:
        def validate_design(self, state):
            return False, "No components"

    monkeypatch.setattr(graph, "get_tracer", lambda: tracer)
    monkeypatch.setattr(graph, "JudgeController", lambda: FakeJudge())

    state = CrucibleState(user_prompt="Design a system")

    result = graph.validate_design_node(state)

    tracer.design_validated.assert_called_once_with(
        is_valid=False,
        reason="No components",
        components_count=0,
    )
    assert result["status"] == "FAILED"


@pytest.mark.asyncio
async def test_run_single_red_team_agent_emits_agent_trace(monkeypatch):
    tracer = make_tracer_spy()

    class FakeRedTeamAgent:
        async def invoke_async(self, **kwargs):
            return SimpleNamespace(
                vulnerabilities=[
                    {
                        "severity": "HIGH",
                        "confidence": 0.8,
                        "title": "SQL Injection",
                        "description": "Unsanitized input",
                        "attack_vector": "Inject via URL",
                        "affected_components": [1],
                    }
                ]
            )

        async def cleanup(self):
            return None

    monkeypatch.setattr(graph, "get_tracer", lambda: tracer)
    monkeypatch.setitem(graph.RED_TEAM_AGENTS, "SecurityHawk", FakeRedTeamAgent)

    agent_name, vulnerabilities, error = await graph._run_single_red_team_agent(
        "SecurityHawk",
        "# Design",
        [],
        1,
        None,
    )

    tracer.agent_invoke.assert_called_once_with(
        AgentType.SECURITY_HAWK,
        "SecurityHawk",
        input_prompt=None,
    )
    tracer.agent_complete.assert_called_once_with(
        agent_type=AgentType.SECURITY_HAWK,
        agent_name="SecurityHawk",
        success=True,
        vulnerabilities_found=1,
        tokens_used=0,
        duration_ms=None,
        error_message=None,
    )
    assert agent_name == "SecurityHawk"
    assert len(vulnerabilities) == 1
    assert error is None


def test_red_team_node_emits_iteration_and_vulnerability_trace(monkeypatch):
    tracer = make_tracer_spy()
    display = make_display_spy()

    class FakeConfig:
        sequential_mode = True

        class deduplication:
            enabled = False
            similarity_threshold = 0.85

    class FakeJudge:
        def evaluate_attacks(self, state, all_vulns):
            return [], SimpleNamespace(decision="CONTINUE_TO_DEFEND")

    async def fake_single_agent(agent_name, design_markdown, components, iteration, display):
        return (
            agent_name,
            [
                {
                    "severity": "HIGH",
                    "confidence": 0.9,
                    "title": "Rate limit missing",
                    "description": "No throttling",
                    "attack_vector": "Flood requests",
                    "affected_components": [1],
                }
            ],
            None,
        )

    monkeypatch.setattr(graph, "get_tracer", lambda: tracer)
    monkeypatch.setattr(graph, "get_display", lambda: display)
    monkeypatch.setattr(graph, "get_config", lambda: FakeConfig())
    monkeypatch.setattr(graph, "JudgeController", lambda: FakeJudge())
    monkeypatch.setattr(graph, "_run_single_red_team_agent", fake_single_agent)

    state = CrucibleState(
        user_prompt="Design a system",
        design_markdown="# Design",
        active_agents=["SecurityHawk"],
    )

    result = graph.red_team_node(state)

    tracer.iteration_start.assert_called_once()
    tracer.vulnerability_found.assert_called_once()
    assert result["status"] == "PATCHING"


def test_defender_node_emits_patch_trace(monkeypatch):
    tracer = make_tracer_spy()
    display = make_display_spy()

    class FakeConfig:
        class validation:
            enabled = True
            strict_mode = False

    class FakeQuickFixer:
        def invoke(self, **kwargs):
            return SimpleNamespace(
                patches=[
                    {
                        "target_vulnerability_id": 1,
                        "fix_description": "Add validation",
                        "design_changes": ["Validate input"],
                        "introduces_new_assumptions": False,
                    }
                ],
                updated_design_markdown="# Patched",
            )

        async def cleanup(self):
            return None

    class FakeDefenseCoordinator:
        def invoke(self, **kwargs):
            return SimpleNamespace(conflicts_detected=[])

        async def cleanup(self):
            return None

    class FakeValidator:
        def __init__(self, strict_mode=False):
            self.strict_mode = strict_mode

        def batch_validate(self, patches, design_components, vulnerabilities):
            return {patch.patch_id: {"valid": True, "warnings": [], "errors": []} for patch in patches}

    class FakeJudge:
        def verify_patches(self, state, before, after, patches):
            return True, "ok"

    import crucible.agents.specialized_defenders as specialized_defenders

    monkeypatch.setattr(graph, "get_tracer", lambda: tracer)
    monkeypatch.setattr(graph, "get_display", lambda: display)
    monkeypatch.setattr(graph, "get_config", lambda: FakeConfig())
    monkeypatch.setattr(specialized_defenders, "QuickFixer", FakeQuickFixer)
    monkeypatch.setattr(specialized_defenders, "ArchitectRefactorer", FakeQuickFixer)
    monkeypatch.setattr(specialized_defenders, "DefenseCoordinator", FakeDefenseCoordinator)
    monkeypatch.setattr(graph, "PatchValidator", FakeValidator)
    monkeypatch.setattr(graph, "JudgeController", lambda: FakeJudge())
    monkeypatch.setattr(graph, "cleanup_agent_sync", lambda agent: None)

    state = CrucibleState(
        user_prompt="Design a system",
        design_markdown="# Design",
        design_components=[
            DesignComponent(
                component_id=1,
                name="API Gateway",
                responsibility="Handle requests",
            )
        ],
        vulnerabilities=[
            Vulnerability(
                vulnerability_id=1,
                severity="LOW",
                confidence=0.8,
                domain="SECURITY",
                title="Missing validation",
                description="Input is unsanitized",
                attack_vector="Inject invalid values",
                affected_components=[1],
                iteration_found=1,
            )
        ],
        active_vulnerabilities=[1],
        status="PATCHING",
        defender_mode="QUICK_FIX",
    )

    result = graph.defender_node(state)

    tracer.agent_invoke.assert_any_call("Defender", "QuickFixer", input_prompt=None)
    tracer.agent_invoke.assert_any_call("Defender", "DefenseCoordinator", input_prompt=None)
    tracer.patch_applied.assert_called_once()
    assert result["status"] == "EVALUATING"


def test_evaluate_node_emits_iteration_end_and_judge_trace(monkeypatch):
    tracer = make_tracer_spy()

    class FakeJudge:
        def decide_termination(self, state):
            return SimpleNamespace(decision="TERMINATE_STABLE", reason="done")

    monkeypatch.setattr(graph, "get_tracer", lambda: tracer)
    monkeypatch.setattr(graph, "JudgeController", lambda: FakeJudge())
    monkeypatch.setattr(graph, "get_display", lambda: None)

    state = CrucibleState(user_prompt="Design a system")

    result = graph.evaluate_node(state)

    tracer.judge_decision.assert_called_once()
    tracer.iteration_end.assert_called_once()
    assert result["status"] == "STABLE"


def _make_strategy_sim_state() -> CrucibleState:
    return CrucibleState(
        user_prompt="Design a system",
        design_markdown="# Design",
        design_components=[
            DesignComponent(
                component_id=1,
                name="API Gateway",
                responsibility="Handle requests",
            )
        ],
        vulnerabilities=[
            Vulnerability(
                vulnerability_id=1,
                severity="CRITICAL",
                confidence=0.9,
                domain="SECURITY",
                title="Missing auth boundary",
                description="Single tier trust boundary",
                attack_vector="Privilege escalation",
                affected_components=[1],
                iteration_found=0,
            )
        ],
        active_vulnerabilities=[1],
        status="PATCHING",
        defender_strategy="tactical-first",
    )


def _install_strategy_sim_defender_doubles(monkeypatch):
    class FakeConfig:
        class validation:
            enabled = False
            strict_mode = False

        class defender_strategy_sim:
            enabled = True

    class FakeQuickFixer:
        def invoke(self, **kwargs):
            return SimpleNamespace(
                patches=[
                    {
                        "target_vulnerability_id": 1,
                        "fix_description": "Add tactical validation",
                        "design_changes": ["Validate token format"],
                        "introduces_new_assumptions": False,
                    }
                ],
                updated_design_markdown="# Quick Patched",
            )

        async def cleanup(self):
            return None

    class FakeArchitectRefactorer:
        def invoke(self, **kwargs):
            return SimpleNamespace(
                patches=[
                    {
                        "target_vulnerability_id": 1,
                        "fix_description": "Split auth into dedicated boundary",
                        "design_changes": ["Introduce auth service boundary"],
                        "introduces_new_assumptions": True,
                        "fix_category": "STRUCTURAL",
                    }
                ],
                updated_design_markdown="# Architect Patched",
            )

        async def cleanup(self):
            return None

    class FakeDefenseCoordinator:
        def invoke(self, **kwargs):
            return SimpleNamespace(conflicts_detected=[])

        async def cleanup(self):
            return None

    class FakeJudge:
        def verify_patches(self, state, before, after, patches):
            return True, "ok"

    import crucible.agents.specialized_defenders as specialized_defenders

    monkeypatch.setattr(graph, "get_config", lambda: FakeConfig())
    monkeypatch.setattr(graph, "get_display", lambda: None)
    monkeypatch.setattr(graph, "JudgeController", lambda: FakeJudge())
    monkeypatch.setattr(graph, "cleanup_agent_sync", lambda agent: None)
    monkeypatch.setattr(specialized_defenders, "QuickFixer", FakeQuickFixer)
    monkeypatch.setattr(specialized_defenders, "ArchitectRefactorer", FakeArchitectRefactorer)
    monkeypatch.setattr(specialized_defenders, "DefenseCoordinator", FakeDefenseCoordinator)


def test_strategy_simulation_mode_replays_strategies_on_same_vulnerability_snapshot(monkeypatch):
    _install_strategy_sim_defender_doubles(monkeypatch)
    state = _make_strategy_sim_state()

    result = graph.defender_node(state)

    simulation = result["defender_strategy_simulation"]
    runs = simulation["runs"]
    strategies = {run["strategy"] for run in runs}
    snapshot_ids = {tuple(run["vulnerability_snapshot_ids"]) for run in runs}

    assert {"tactical-first", "balanced", "architecture-first"}.issubset(strategies)
    assert snapshot_ids == {(1,)}


def test_strategy_simulation_captures_comparative_metrics(monkeypatch):
    _install_strategy_sim_defender_doubles(monkeypatch)
    state = _make_strategy_sim_state()

    result = graph.defender_node(state)

    simulation = result["defender_strategy_simulation"]
    comparative = simulation["comparative_metrics"]

    assert "by_strategy" in comparative
    assert {"tactical-first", "balanced", "architecture-first"}.issubset(comparative["by_strategy"])
    assert all("patches_applied" in metrics for metrics in comparative["by_strategy"].values())


def test_strategy_simulation_winner_contains_rationale_and_metric_deltas(monkeypatch):
    _install_strategy_sim_defender_doubles(monkeypatch)
    state = _make_strategy_sim_state()

    result = graph.defender_node(state)

    winner = result["defender_strategy_simulation"]["winner"]

    assert winner["strategy"] in {"tactical-first", "balanced", "architecture-first"}
    assert isinstance(winner["rationale"], str)
    assert winner["rationale"].strip()
    assert isinstance(winner["metric_deltas"], dict)
    assert winner["metric_deltas"]