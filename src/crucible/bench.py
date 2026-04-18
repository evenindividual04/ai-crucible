"""Benchmark dataset helpers for batch evaluation."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crucible.eval.schemas import EvaluationReport


_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_safe_identifier(identifier: str, field_name: str, dataset_path: Path | None = None, idx: int | None = None) -> None:
    """Validate that an identifier is safe for filesystem path composition."""
    location = ""
    if dataset_path is not None and idx is not None:
        location = f"Dataset {dataset_path} case[{idx}] "

    if ".." in identifier or "/" in identifier or "\\" in identifier:
        raise ValueError(f"{location}invalid {field_name}: path segments are not allowed")
    if not _SAFE_IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"{location}invalid {field_name}: only [A-Za-z0-9._-] allowed")


def _load_bench_dataset(dataset_path: Path) -> dict[str, Any]:
    """Load and validate a benchmark dataset JSON file."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Dataset {dataset_path} must be a JSON object")

    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"Dataset {dataset_path} must contain a non-empty 'cases' list")

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Dataset {dataset_path} case[{idx}] must be an object")
        for required in ("case_id", "run_id", "user_prompt"):
            value = case.get(required)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Dataset {dataset_path} case[{idx}] missing required field: {required}")

        for identifier_field in ("case_id", "run_id"):
            _validate_safe_identifier(
                identifier=case[identifier_field],
                field_name=identifier_field,
                dataset_path=dataset_path,
                idx=idx,
            )

    dataset_id = raw.get("dataset_id") or dataset_path.stem
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError(f"Dataset {dataset_path} field 'dataset_id' must be a non-empty string")

    return {
        "dataset_id": dataset_id,
        "cases": cases,
    }


def _compute_bench_config_hash(dataset: dict[str, Any], checkpoint_dir: Path) -> str:
    """Compute a reproducibility hash for benchmark execution inputs."""
    payload = {
        "dataset_id": dataset.get("dataset_id"),
        "cases": [
            {
                "case_id": c.get("case_id"),
                "run_id": c.get("run_id"),
                "repeat_index": c.get("repeat_index", 0),
                "seed": c.get("seed"),
            }
            for c in dataset.get("cases", [])
        ],
        "checkpoint_dir": str(checkpoint_dir),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _aggregate_bench_results(per_case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate case-level benchmark results into summary statistics."""
    scores = [r["aggregate_score"] for r in per_case_results if r.get("status") == "ok"]
    succeeded = len(scores)
    total = len(per_case_results)
    failed = total - succeeded

    if scores:
        mean_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
    else:
        mean_score = 0.0
        min_score = 0.0
        max_score = 0.0

    return {
        "cases_total": total,
        "cases_succeeded": succeeded,
        "cases_failed": failed,
        "aggregate_score_mean": mean_score,
        "aggregate_score_min": min_score,
        "aggregate_score_max": max_score,
    }


def _run_bench_dataset(
    dataset: dict[str, Any],
    checkpoint_dir: Path,
    output_dir: Path,
    evaluator: Any,
) -> dict[str, Any]:
    """Run benchmark evaluation over all dataset cases and persist outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = output_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    dataset_id = dataset["dataset_id"]
    config_hash = _compute_bench_config_hash(dataset, checkpoint_dir)

    per_case_results: list[dict[str, Any]] = []

    for case in dataset["cases"]:
        case_id = case["case_id"]
        run_id = case["run_id"]
        user_prompt = case["user_prompt"]
        repeat_index = int(case.get("repeat_index", 0))
        seed = case.get("seed")

        # Defense in depth: ensure identifiers are safe even if caller bypassed loader.
        _validate_safe_identifier(case_id, "case_id")
        _validate_safe_identifier(run_id, "run_id")

        try:
            report: EvaluationReport = evaluator.evaluate_checkpoint(
                checkpoint_path=checkpoint_dir / run_id / "checkpoints",
                user_prompt=user_prompt,
                run_id=run_id,
            )
            report.metadata.dataset_id = dataset_id
            report.metadata.config_hash = config_hash

            case_output = cases_dir / f"{case_id}__{run_id}__r{repeat_index}"
            evaluator.save_report(report, case_output, formats=["json", "md"])

            per_case_results.append(
                {
                    "case_id": case_id,
                    "run_id": run_id,
                    "status": "ok",
                    "aggregate_score": report.aggregate_score,
                    "seed": seed,
                    "repeat_index": repeat_index,
                }
            )
        except Exception as exc:
            per_case_results.append(
                {
                    "case_id": case_id,
                    "run_id": run_id,
                    "status": "error",
                    "error": str(exc),
                    "seed": seed,
                    "repeat_index": repeat_index,
                }
            )

    aggregate = _aggregate_bench_results(per_case_results)
    summary = {
        "dataset_id": dataset_id,
        "config_hash": config_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **aggregate,
        "cases": per_case_results,
    }

    summary_path = output_dir / "bench_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
