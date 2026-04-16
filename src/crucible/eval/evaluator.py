"""
Main evaluator orchestration for AI Crucible.

This module provides the CrucibleEvaluator class which coordinates
evaluation criteria, aggregates scores, and generates reports.
"""

from pathlib import Path
from typing import Any

from crucible.eval.aggregation import WeightedAverageStrategy, AggregationStrategy
from crucible.eval.criteria import (
    AttackEffectivenessCriterion,
    ConvergenceSpeedCriterion,
    RedundancyCriterion,
    TokenEfficiencyCriterion,
    EvaluationCriterion,
)
from crucible.eval.schemas import EvaluationReport, EvaluationMetadata, Trace
from crucible.eval.reporters import JSONReporter, MarkdownReporter


class CrucibleEvaluator:
    """
    Main evaluator for AI Crucible traces.

    The evaluator coordinates multiple evaluation criteria, aggregates their
    scores using a configurable strategy, and generates reports in
    multiple formats.
    """

    def __init__(
        self,
        criteria: list[EvaluationCriterion] | None = None,
        aggregation_strategy: AggregationStrategy | None = None,
    ):
        """
        Initialize the evaluator.

        Args:
            criteria: List of evaluation criteria to use. If None, uses defaults.
            aggregation_strategy: Strategy for combining scores. If None, uses weighted average.
        """
        self.criteria = criteria or [
            AttackEffectivenessCriterion(),
            ConvergenceSpeedCriterion(),
            RedundancyCriterion(),
            TokenEfficiencyCriterion(),
        ]
        self.aggregation_strategy = aggregation_strategy or WeightedAverageStrategy()

    def evaluate_trace(
        self,
        trace: Trace,
        state: Any = None,
        metadata: EvaluationMetadata | None = None,
    ) -> EvaluationReport:
        """
        Evaluate a single trace.

        Args:
            trace: Complete execution trace
            state: Optional final state (can be derived from trace)
            metadata: Optional evaluation metadata

        Returns:
            EvaluationReport with all scores and aggregate
        """
        scores: dict[str, Any] = {}

        # Evaluate each criterion
        for criterion in self.criteria:
            try:
                score = criterion.evaluate(trace, state)
                scores[criterion.name] = score
            except Exception as e:
                # Don't let one criterion failure break evaluation
                scores[criterion.name] = None

        # Convert to format expected by aggregation
        valid_scores = {
            name: score
            for name, score in scores.items()
            if score is not None
        }

        # Calculate aggregate score
        aggregate_score = self.aggregation_strategy.aggregate(valid_scores)

        # Build metadata
        if metadata is None:
            metadata = EvaluationMetadata(
                crucible_version=trace.crucible_version,
                llm_provider=trace.llm_provider,
                llm_model=trace.llm_model,
                max_iterations=trace.max_iterations,
            )

        # Generate summary
        summary_lines = [
            f"Evaluation for run {trace.run_id}",
            f"Aggregate Score: {aggregate_score:.3f} ({self.aggregation_strategy.name})",
        ]

        for name, score in scores.items():
            if score:
                summary_lines.append(f"  {score}")
            else:
                summary_lines.append(f"  {name}: FAILED")

        summary = "\n".join(summary_lines)

        return EvaluationReport(
            trace_id=trace.run_id,
            run_id=trace.run_id,
            scores=scores,
            aggregate_score=aggregate_score,
            aggregation_strategy=self.aggregation_strategy.name,
            metadata=metadata,
            summary=summary,
        )

    def evaluate_trace_file(
        self,
        trace_path: Path,
        state: Any = None,
    ) -> EvaluationReport:
        """
        Evaluate a trace from a file.

        Args:
            trace_path: Path to the trace JSON file
            state: Optional final state

        Returns:
            EvaluationReport with all scores and aggregate
        """
        from crucible.eval.schemas import Trace

        trace = Trace.model_validate_json(trace_path.read_text())
        return self.evaluate_trace(trace, state)

    def evaluate_checkpoint(
        self,
        checkpoint_path: Path,
        user_prompt: str,
        run_id: str,
    ) -> EvaluationReport:
        """
        Evaluate a run from checkpoint files.

        This enables evaluation of previously-run executions that didn't
        have explicit tracing enabled.

        Args:
            checkpoint_path: Path to the checkpoint directory
            user_prompt: The original user prompt
            run_id: Unique identifier for the run

        Returns:
            EvaluationReport with all scores and aggregate
        """
        from crucible.eval.tracer import CrucibleTracer

        # Reconstruct trace from checkpoint
        tracer = CrucibleTracer.from_checkpoint(
            run_id=run_id,
            checkpoint_path=checkpoint_path,
            user_prompt=user_prompt,
        )
        return self.evaluate_trace(tracer.trace)

    def save_report(
        self,
        report: EvaluationReport,
        output_path: Path,
        formats: list[str] | None = None,
    ) -> None:
        """
        Save an evaluation report to disk.

        Args:
            report: The evaluation report to save
            output_path: Base path for the report file
            formats: List of formats to save (json, md, html)
        """
        formats = formats or ["json", "md"]

        if "json" in formats:
            reporter = JSONReporter()
            json_path = output_path.with_suffix(".json")
            reporter.save_report(report, json_path)

        if "md" in formats:
            reporter = MarkdownReporter()
            md_path = output_path.with_suffix(".md")
            reporter.save_report(report, md_path)


class BatchEvaluator:
    """
    Batch evaluator for comparing multiple runs.

    The batch evaluator evaluates multiple traces and generates
    comparison reports and statistics.
    """

    def __init__(
        self,
        evaluator: CrucibleEvaluator | None = None,
    ):
        """
        Initialize the batch evaluator.

        Args:
            evaluator: The underlying evaluator to use for each trace
        """
        self.evaluator = evaluator or CrucibleEvaluator()

    def evaluate_traces(
        self,
        traces: list[Trace],
    ) -> dict[str, EvaluationReport]:
        """
        Evaluate multiple traces.

        Args:
            traces: List of traces to evaluate

        Returns:
            Mapping of trace IDs to evaluation reports
        """
        results = {}

        for trace in traces:
            try:
                report = self.evaluator.evaluate_trace(trace)
                results[trace.run_id] = report
            except Exception:
                # Don't let one failure stop batch evaluation
                results[trace.run_id] = None

        return results

    def evaluate_trace_directory(
        self,
        trace_dir: Path,
    ) -> dict[str, EvaluationReport]:
        """
        Evaluate all traces in a directory.

        Args:
            trace_dir: Directory containing trace JSON files

        Returns:
            Mapping of trace IDs to evaluation reports
        """
        from crucible.eval.schemas import Trace

        traces = []
        for json_file in trace_dir.glob("*.json"):
            try:
                trace = Trace.model_validate_json(json_file.read_text())
                traces.append(trace)
            except Exception:
                # Skip invalid trace files
                continue

        return self.evaluate_traces(traces)

    def compare_runs(
        self,
        base_run_id: str,
        compare_run_id: str,
        reports: dict[str, EvaluationReport],
    ) -> dict[str, Any]:
        """
        Compare two evaluation runs.

        Args:
            base_run_id: ID of the base (reference) run
            compare_run_id: ID of the run to compare against
            reports: Mapping of run IDs to evaluation reports

        Returns:
            Comparison result with differences and winner
        """
        base_report = reports.get(base_run_id)
        compare_report = reports.get(compare_run_id)

        if not base_report or not compare_report:
            return {
                "error": "One or both runs not found in reports",
            }

        differences = {}

        # Compare aggregate scores
        diff = compare_report.aggregate_score - base_report.aggregate_score
        differences["aggregate"] = diff

        # Compare individual criteria
        for name in base_report.scores:
            if name in compare_report.scores:
                base_score = base_report.scores[name].value
                compare_score = compare_report.scores[name].value
                differences[name] = compare_score - base_score

        # Determine winner (higher aggregate score wins)
        winner = None
        if diff > 0:
            winner = compare_run_id
        elif diff < 0:
            winner = base_run_id

        return {
            "base_run_id": base_run_id,
            "base_score": base_report.aggregate_score,
            "compare_run_id": compare_run_id,
            "compare_score": compare_report.aggregate_score,
            "differences": differences,
            "winner": winner,
        }
