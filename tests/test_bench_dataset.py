"""Tests for benchmark dataset execution in bench command (PR3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crucible.bench import (
    _aggregate_bench_results,
    _load_bench_dataset,
    _run_bench_dataset,
)
from crucible.eval.schemas import EvaluationMetadata, EvaluationReport


class _DummyEvaluator:
    def __init__(self, should_fail_run_ids: set[str] | None = None):
        self.should_fail_run_ids = should_fail_run_ids or set()
        self.saved_reports: list[tuple[Path, EvaluationReport, tuple[str, ...]]] = []

    def evaluate_checkpoint(self, checkpoint_path: Path, user_prompt: str, run_id: str) -> EvaluationReport:
        if run_id in self.should_fail_run_ids:
            raise RuntimeError(f"failed run: {run_id}")
        return EvaluationReport(
            trace_id=run_id,
            run_id=run_id,
            scores={},
            aggregate_score=0.8,
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
