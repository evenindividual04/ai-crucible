"""RED tests for PR9 evaluator comparison and leaderboard reporting.

These tests define the expected output contract for PR9 reporting features.
"""

from datetime import datetime, timezone

from crucible.eval import reporters
from crucible.eval.evaluator import BatchEvaluator
from crucible.eval.schemas import CriterionScore, EvaluationMetadata, EvaluationReport


def _report(
    run_id: str,
    aggregate: float,
    strategy: str,
    scenario: str,
) -> EvaluationReport:
    return EvaluationReport(
        trace_id=run_id,
        run_id=run_id,
        aggregate_score=aggregate,
        aggregation_strategy="weighted_average",
        scores={
            "chain_quality": CriterionScore(name="chain_quality", value=aggregate),
            "strategy_quality": CriterionScore(name="strategy_quality", value=aggregate),
        },
        metadata=EvaluationMetadata(
            crucible_version="0.1.0",
            llm_provider="test",
            llm_model="test",
            max_iterations=3,
            dataset_id=scenario,
            config_hash=strategy,
            evaluation_timestamp=datetime.now(timezone.utc),
        ),
    )


def test_pr9_batch_evaluator_exposes_scenario_strategy_delta_api_red():
    """PR9: BatchEvaluator exposes per-scenario/per-strategy delta comparison API."""
    assert hasattr(BatchEvaluator, "compare_scenario_strategy_deltas")


def test_pr9_comparison_outputs_per_scenario_per_strategy_deltas_red():
    """PR9: delta comparison output includes scenario and strategy granular deltas."""
    assert hasattr(BatchEvaluator, "compare_scenario_strategy_deltas")

    evaluator = BatchEvaluator()
    reports = {
        "s1-tactical": _report("s1-tactical", 0.40, "tactical-first", "scenario-1"),
        "s1-arch": _report("s1-arch", 0.70, "architecture-first", "scenario-1"),
        "s2-tactical": _report("s2-tactical", 0.55, "tactical-first", "scenario-2"),
        "s2-arch": _report("s2-arch", 0.50, "architecture-first", "scenario-2"),
    }

    comparison = evaluator.compare_scenario_strategy_deltas(reports)

    assert "per_scenario_deltas" in comparison
    assert "per_strategy_deltas" in comparison
    assert set(comparison["per_scenario_deltas"]) == {"scenario-1", "scenario-2"}
    assert set(comparison["per_strategy_deltas"]) == {
        "tactical-first",
        "architecture-first",
    }
    assert comparison["per_scenario_deltas"]["scenario-1"]["delta"] > 0
    assert comparison["per_scenario_deltas"]["scenario-2"]["delta"] < 0


def test_pr9_leaderboard_reporter_exists_red():
    """PR9: reporters module provides leaderboard report generation utility."""
    assert hasattr(reporters, "LeaderboardReporter")


def test_pr9_leaderboard_stability_and_explainability_red():
    """PR9: leaderboard ordering is deterministic and includes explainability fields."""
    assert hasattr(reporters, "LeaderboardReporter")

    leaderboard = reporters.LeaderboardReporter()
    rows = [
        {
            "strategy": "balanced",
            "scenario": "scenario-1",
            "aggregate_score": 0.80,
            "wins": 1,
            "rationale": "Balanced mitigation with low regression risk.",
        },
        {
            "strategy": "architecture-first",
            "scenario": "scenario-1",
            "aggregate_score": 0.80,
            "wins": 1,
            "rationale": "High chain disruption at moderate cost.",
        },
        {
            "strategy": "tactical-first",
            "scenario": "scenario-1",
            "aggregate_score": 0.70,
            "wins": 0,
            "rationale": "Fast partial fixes.",
        },
    ]

    first = leaderboard.build(rows)
    second = leaderboard.build(rows)

    assert first == second
    assert "rows" in first
    assert "explanations" in first
    assert all("rationale" in row for row in first["rows"])
    assert all("why_ranked" in explanation for explanation in first["explanations"])
