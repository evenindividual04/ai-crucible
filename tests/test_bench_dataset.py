"""Tests for benchmark dataset execution in bench command (PR3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crucible.bench import (
    BenchRegressionError,
    _aggregate_bench_results,
    _compute_bench_config_hash,
    _load_bench_dataset,
    _run_bench_dataset,
)
from crucible.eval.schemas import EvaluationMetadata, EvaluationReport


class _DummyEvaluator:
    def __init__(self, should_fail_run_ids: set[str] | None = None, score_by_run_id: dict[str, float] | None = None):
        self.should_fail_run_ids = should_fail_run_ids or set()
        self.score_by_run_id = score_by_run_id or {}
        self.saved_reports: list[tuple[Path, EvaluationReport, tuple[str, ...]]] = []

    def evaluate_checkpoint(self, checkpoint_path: Path, user_prompt: str, run_id: str) -> EvaluationReport:
        if run_id in self.should_fail_run_ids:
            raise RuntimeError(f"failed run: {run_id}")
        aggregate_score = self.score_by_run_id.get(run_id, 0.8)
        return EvaluationReport(
            trace_id=run_id,
            run_id=run_id,
            scores={},
            aggregate_score=aggregate_score,
            aggregation_strategy="weighted_average",
            metadata=EvaluationMetadata(),
            summary=f"report for {run_id}",
        )

    def save_report(self, report: EvaluationReport, output_path: Path, formats: list[str] | None = None) -> None:
        self.saved_reports.append((output_path, report, tuple(formats or [])))



def test_load_bench_dataset_valid(tmp_path: Path) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_id": "auth_suite_v1",
                "cases": [
                    {"case_id": "case_001", "run_id": "run_a", "user_prompt": "Design auth"},
                    {"case_id": "case_002", "run_id": "run_b", "user_prompt": "Design billing"},
                ],
            }
        ),
        encoding="utf-8",
    )

    dataset = _load_bench_dataset(dataset_path)

    assert dataset["dataset_id"] == "auth_suite_v1"
    assert len(dataset["cases"]) == 2
    assert dataset["cases"][0]["case_id"] == "case_001"



def test_load_bench_dataset_rejects_invalid_case(tmp_path: Path) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_id": "auth_suite_v1",
                "cases": [
                    {"case_id": "case_001", "run_id": "run_a", "user_prompt": "Design auth"},
                    {"run_id": "run_b", "user_prompt": "Design billing"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"case\[1\].*case_id"):
        _load_bench_dataset(dataset_path)


def test_load_bench_dataset_rejects_non_object_root(tmp_path: Path) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(json.dumps([{"case_id": "x"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        _load_bench_dataset(dataset_path)


def test_load_bench_dataset_rejects_path_like_identifiers(tmp_path: Path) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_id": "auth_suite_v1",
                "cases": [
                    {
                        "case_id": "case_001",
                        "run_id": "../escape",
                        "user_prompt": "Design auth",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid run_id"):
        _load_bench_dataset(dataset_path)


def test_load_bench_dataset_rejects_invalid_case_id_characters(tmp_path: Path) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_id": "auth_suite_v1",
                "cases": [
                    {
                        "case_id": "case bad",
                        "run_id": "run_a",
                        "user_prompt": "Design auth",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid case_id"):
        _load_bench_dataset(dataset_path)


def test_load_bench_dataset_rejects_non_numeric_expected_min_score(tmp_path: Path) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_id": "auth_suite_v1",
                "cases": [
                    {
                        "case_id": "case_001",
                        "run_id": "run_a",
                        "user_prompt": "Design auth",
                        "expected_min_score": "high",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_min_score"):
        _load_bench_dataset(dataset_path)


def test_load_bench_dataset_rejects_out_of_range_expected_min_score(tmp_path: Path) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_id": "auth_suite_v1",
                "cases": [
                    {
                        "case_id": "case_001",
                        "run_id": "run_a",
                        "user_prompt": "Design auth",
                        "expected_min_score": 1.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_min_score"):
        _load_bench_dataset(dataset_path)


@pytest.mark.parametrize("bool_threshold", [True, False])
def test_load_bench_dataset_rejects_boolean_expected_min_score(tmp_path: Path, bool_threshold: bool) -> None:
    dataset_path = tmp_path / "suite.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_id": "auth_suite_v1",
                "cases": [
                    {
                        "case_id": "case_001",
                        "run_id": "run_a",
                        "user_prompt": "Design auth",
                        "expected_min_score": bool_threshold,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_min_score"):
        _load_bench_dataset(dataset_path)



def test_aggregate_bench_results() -> None:
    aggregate = _aggregate_bench_results(
        [
            {"status": "ok", "aggregate_score": 0.9},
            {"status": "ok", "aggregate_score": 0.7},
            {"status": "error", "error": "boom"},
        ]
    )

    assert aggregate["cases_total"] == 3
    assert aggregate["cases_succeeded"] == 2
    assert aggregate["cases_failed"] == 1
    assert aggregate["aggregate_score_mean"] == pytest.approx(0.8)
    assert aggregate["aggregate_score_min"] == pytest.approx(0.7)
    assert aggregate["aggregate_score_max"] == pytest.approx(0.9)



def test_run_bench_dataset_writes_summary_and_sets_repro_metadata(tmp_path: Path) -> None:
    dataset = {
        "dataset_id": "auth_suite_v1",
        "cases": [
            {"case_id": "case_001", "run_id": "run_a", "user_prompt": "Design auth", "seed": 11, "repeat_index": 0},
            {"case_id": "case_002", "run_id": "run_b", "user_prompt": "Design billing", "seed": 11, "repeat_index": 1},
        ],
    }
    checkpoint_dir = tmp_path / "outputs"
    output_dir = tmp_path / "evaluations"

    evaluator = _DummyEvaluator(should_fail_run_ids={"run_b"})

    summary = _run_bench_dataset(
        dataset=dataset,
        checkpoint_dir=checkpoint_dir,
        output_dir=output_dir,
        evaluator=evaluator,
    )

    assert summary["dataset_id"] == "auth_suite_v1"
    assert summary["cases_total"] == 2
    assert summary["cases_succeeded"] == 1
    assert summary["cases_failed"] == 1
    assert len(summary["config_hash"]) == 64

    summary_file = output_dir / "bench_summary.json"
    assert summary_file.exists()

    successful_report = evaluator.saved_reports[0][1]
    assert successful_report.metadata.dataset_id == "auth_suite_v1"
    assert successful_report.metadata.config_hash == summary["config_hash"]


def test_run_bench_dataset_uses_repeat_index_in_output_paths(tmp_path: Path) -> None:
    dataset = {
        "dataset_id": "repeat_suite",
        "cases": [
            {"case_id": "case_001", "run_id": "run_same", "user_prompt": "A", "repeat_index": 0},
            {"case_id": "case_001", "run_id": "run_same", "user_prompt": "A", "repeat_index": 1},
        ],
    }

    evaluator = _DummyEvaluator()
    _run_bench_dataset(
        dataset=dataset,
        checkpoint_dir=tmp_path / "outputs",
        output_dir=tmp_path / "evaluations",
        evaluator=evaluator,
    )

    saved_paths = [entry[0].name for entry in evaluator.saved_reports]
    assert "case_001__run_same__r0" in saved_paths
    assert "case_001__run_same__r1" in saved_paths
    assert len(set(saved_paths)) == 2


def test_run_bench_dataset_enforces_identifier_safety_even_without_loader(tmp_path: Path) -> None:
    dataset = {
        "dataset_id": "unsafe",
        "cases": [
            {
                "case_id": "case_001",
                "run_id": "../escape",
                "user_prompt": "A",
            }
        ],
    }

    evaluator = _DummyEvaluator()
    with pytest.raises(ValueError, match="invalid run_id"):
        _run_bench_dataset(
            dataset=dataset,
            checkpoint_dir=tmp_path / "outputs",
            output_dir=tmp_path / "evaluations",
            evaluator=evaluator,
        )


def test_compute_bench_config_hash_changes_when_expected_threshold_changes(tmp_path: Path) -> None:
    dataset_a = {
        "dataset_id": "golden_suite",
        "cases": [
            {
                "case_id": "case_001",
                "run_id": "run_a",
                "user_prompt": "Design auth",
                "expected_min_score": 0.70,
            }
        ],
    }
    dataset_b = {
        "dataset_id": "golden_suite",
        "cases": [
            {
                "case_id": "case_001",
                "run_id": "run_a",
                "user_prompt": "Design auth",
                "expected_min_score": 0.80,
            }
        ],
    }

    hash_a = _compute_bench_config_hash(dataset_a, tmp_path / "outputs")
    hash_b = _compute_bench_config_hash(dataset_b, tmp_path / "outputs")

    assert hash_a != hash_b


def test_run_bench_dataset_tracks_regressions_against_expected_min_scores(tmp_path: Path) -> None:
    dataset = {
        "dataset_id": "golden_suite",
        "cases": [
            {
                "case_id": "case_pass",
                "run_id": "run_pass",
                "user_prompt": "Auth design",
                "expected_min_score": 0.75,
            },
            {
                "case_id": "case_regress",
                "run_id": "run_regress",
                "user_prompt": "Payments design",
                "expected_min_score": 0.70,
            },
        ],
    }

    evaluator = _DummyEvaluator(
        score_by_run_id={
            "run_pass": 0.80,
            "run_regress": 0.65,
        }
    )

    summary = _run_bench_dataset(
        dataset=dataset,
        checkpoint_dir=tmp_path / "outputs",
        output_dir=tmp_path / "evaluations",
        evaluator=evaluator,
    )

    assert summary["regression_count"] == 1
    assert summary["gated_case_count"] == 2
    assert summary["regression_rate"] == pytest.approx(0.5)
    assert summary["regression_rate_gated"] == pytest.approx(0.5)
    assert summary["has_regressions"] is True
    assert summary["regressions"][0]["case_id"] == "case_regress"


def test_run_bench_dataset_reports_gated_regression_rate_separately(tmp_path: Path) -> None:
    dataset = {
        "dataset_id": "mixed_suite",
        "cases": [
            {
                "case_id": "case_regress",
                "run_id": "run_regress",
                "user_prompt": "Payments design",
                "expected_min_score": 0.70,
            },
            {
                "case_id": "case_ungated",
                "run_id": "run_ungated",
                "user_prompt": "General design",
            },
        ],
    }

    evaluator = _DummyEvaluator(
        score_by_run_id={
            "run_regress": 0.60,
            "run_ungated": 0.20,
        }
    )

    summary = _run_bench_dataset(
        dataset=dataset,
        checkpoint_dir=tmp_path / "outputs",
        output_dir=tmp_path / "evaluations",
        evaluator=evaluator,
    )

    assert summary["regression_count"] == 1
    assert summary["gated_case_count"] == 1
    assert summary["regression_rate"] == pytest.approx(0.5)
    assert summary["regression_rate_gated"] == pytest.approx(1.0)


def test_run_bench_dataset_fail_on_regression_raises_and_writes_rollback_guide(tmp_path: Path) -> None:
    dataset = {
        "dataset_id": "golden_suite",
        "cases": [
            {
                "case_id": "case_regress",
                "run_id": "run_regress",
                "user_prompt": "Payments design",
                "expected_min_score": 0.70,
            }
        ],
    }

    evaluator = _DummyEvaluator(score_by_run_id={"run_regress": 0.50})
    output_dir = tmp_path / "evaluations"

    with pytest.raises(BenchRegressionError):
        _run_bench_dataset(
            dataset=dataset,
            checkpoint_dir=tmp_path / "outputs",
            output_dir=output_dir,
            evaluator=evaluator,
            fail_on_regression=True,
        )

    rollback_path = output_dir / "rollback_instructions.md"
    assert rollback_path.exists()
    rollback_text = rollback_path.read_text(encoding="utf-8")
    assert "Regression gate failed" in rollback_text
    assert "--fail-on-regression" in rollback_text


def test_run_bench_dataset_rejects_invalid_expected_threshold_when_loader_is_bypassed(tmp_path: Path) -> None:
    dataset = {
        "dataset_id": "golden_suite",
        "cases": [
            {
                "case_id": "case_bad",
                "run_id": "run_bad",
                "user_prompt": "Payments design",
                "expected_min_score": "invalid",
            }
        ],
    }

    evaluator = _DummyEvaluator(score_by_run_id={"run_bad": 0.50})

    with pytest.raises(ValueError, match="expected_min_score"):
        _run_bench_dataset(
            dataset=dataset,
            checkpoint_dir=tmp_path / "outputs",
            output_dir=tmp_path / "evaluations",
            evaluator=evaluator,
        )


def test_readme_documents_fail_on_regression_and_rollback() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "--fail-on-regression" in readme
    assert "rollback_instructions.md" in readme


def test_golden_scenarios_dataset_exists_and_includes_thresholds() -> None:
    dataset_path = Path("evals/golden/golden_scenarios.json")

    assert dataset_path.exists()
    payload = dataset_path.read_text(encoding="utf-8")
    assert "expected_min_score" in payload
