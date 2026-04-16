"""
Report generation for AI Crucible evaluation.

This module provides reporters that generate evaluation reports in
different formats (JSON, Markdown, HTML).
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from crucible.eval.schemas import EvaluationReport

# Import failure categories from the schemas module
# (They're defined in schemas.py to avoid circular imports)
try:
    from crucible.eval.schemas import FailureCategories
except ImportError:
    # Define locally if schemas module has import issues
    class FailureCategories:
        """Categories for classifying evaluation failures."""

        CIRCULAR_REASONING = "circular_reasoning"
        INEFFECTIVE_ATTACK = "ineffective_attack"
        SLOW_CONVERGENCE = "slow_convergence"
        PATCH_REGRESSION = "patch_regression"
        JUDGE_ERROR = "judge_error"
        OTHER = "other"


class Reporter(ABC):
    """Abstract base class for reporters."""

    @abstractmethod
    def save_report(self, report: EvaluationReport, path: Path) -> None:
        """Save the report to a file."""
        pass


class JSONReporter(Reporter):
    """Reporter that saves reports in JSON format."""

    def save_report(self, report: EvaluationReport, path: Path) -> None:
        """Save report as JSON."""
        with open(path, "w") as f:
            json.dump(
                report.model_dump(exclude_none=True),
                f,
                indent=2,
                default=str,
            )


class MarkdownReporter(Reporter):
    """Reporter that saves reports in Markdown format."""

    def save_report(self, report: EvaluationReport, path: Path) -> None:
        """Save report as Markdown."""
        lines = self._generate_markdown(report)
        path.write_text("\n".join(lines))

    def _generate_markdown(self, report: EvaluationReport) -> list[str]:
        """Generate Markdown content for the report."""
        lines = [
            "# AI Crucible Evaluation Report",
            "",
            f"**Run ID:** {report.run_id}",
            f"**Timestamp:** {report.timestamp.isoformat()}",
            "",
            "---",
            "",
            "## Aggregate Score",
            "",
            f"**Score:** {report.aggregate_score:.3f} / 1.000",
            f"**Strategy:** {report.aggregation_strategy}",
            "",
            "## Individual Scores",
            "",
        ]

        # Score table
        lines.append("| Criterion | Score | Details |")
        lines.append("|-----------|-------|---------|")
        for name, score in sorted(report.scores.items()):
            if score:
                details = self._format_details(score.details)
                lines.append(f"| {name} | {score.value:.3f} | {details} |")
            else:
                lines.append(f"| {name} | **FAILED** | - |")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        for line in report.summary.split("\n"):
            lines.append(f"  {line}")
        lines.append("")

        # Failure categorization
        lines.extend(self._categorize_failures(report))
        lines.append("")

        # Metadata
        lines.extend(self._generate_metadata_section(report))

        return lines

    def _format_details(self, details: dict[str, Any]) -> str:
        """Format details for Markdown table."""
        items = []
        for key, value in details.items():
            if isinstance(value, (dict, list)):
                items.append(f"{key}: {len(value)} items")
            elif isinstance(value, float):
                items.append(f"{key}: {value:.2f}")
            else:
                items.append(f"{key}: {value}")
        return "; ".join(items) if items else "-"

    def _categorize_failures(self, report: EvaluationReport) -> list[str]:
        """Categorize and report any failures."""
        lines = ["## Failure Analysis", ""]
        failures_found = False

        for name, score in report.scores.items():
            if score is None:
                lines.append(f"  - {name}: Evaluation failed")
                failures_found = True
            elif score.value < 0.5:
                category = self._get_failure_category(name, score.value, score.details)
                lines.append(f"  - {name}: {category} ({score.value:.3f})")
                failures_found = True

        if not failures_found:
            lines.append("  ✓ No critical failures detected")

        lines.append("")
        return lines

    def _get_failure_category(
        self, name: str, value: float, details: dict[str, Any]
    ) -> str:
        """Determine failure category for a low score."""
        if name == "redundancy":
            return FailureCategories.CIRCULAR_REASONING
        elif name == "attack_effectiveness":
            return FailureCategories.INEFFECTIVE_ATTACK
        elif name == "convergence_speed":
            return FailureCategories.SLOW_CONVERGENCE
        elif "patch" in name:
            return FailureCategories.PATCH_REGRESSION
        elif "judge" in name:
            return FailureCategories.JUDGE_ERROR
        else:
            return FailureCategories.OTHER

    def _generate_metadata_section(self, report: EvaluationReport) -> list[str]:
        """Generate metadata section."""
        lines = ["## Metadata", ""]
        md = report.metadata

        lines.append(f"- **Crucible Version:** {md.crucible_version}")
        lines.append(f"- **LLM Provider:** {md.llm_provider}")
        lines.append(f"- **LLM Model:** {md.llm_model}")
        lines.append(f"- **Max Iterations:** {md.max_iterations}")

        if md.dataset_id:
            lines.append(f"- **Dataset:** {md.dataset_id}")

        if md.perturbations:
            lines.append(f"- **Perturbations:** {len(md.perturbations)} applied")

        lines.append("")

        return lines


class HTMLReporter(Reporter):
    """Reporter that saves reports in HTML format."""

    def save_report(self, report: EvaluationReport, path: Path) -> None:
        """Save report as HTML."""
        html = self._generate_html(report)
        path.write_text(html)

    def _generate_html(self, report: EvaluationReport) -> str:
        """Generate HTML content for the report."""
        lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "  <meta charset='utf-8'>",
            "  <title>AI Crucible Evaluation Report</title>",
            "  <style>",
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }",
            "    h1 { color: #333; }",
            "    h2 { color: #555; border-bottom: 1px solid #ddd; padding-bottom: 10px; }",
            "    table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }",
            "    th { background-color: #f5f5f5; }",
            "    .score-low { color: #c00; }",
            "    .score-med { color: #fa0; }",
            "    .score-high { color: #080; }",
            "    .summary { background-color: #f9f9f9; padding: 15px; border-radius: 5px; }",
            "  </style>",
            "</head>",
            "<body>",
            f"  <h1>AI Crucible Evaluation Report</h1>",
            "",
            f"  <p><strong>Run ID:</strong> {report.run_id}</p>",
            f"  <p><strong>Timestamp:</strong> {report.timestamp.isoformat()}</p>",
            "",
            "  <h2>Aggregate Score</h2>",
            f"  <p><strong>Score:</strong> {report.aggregate_score:.3f} / 1.000</p>",
            f"  <p><strong>Strategy:</strong> {report.aggregation_strategy}</p>",
            "",
            "  <h2>Individual Scores</h2>",
            "  <table>",
            "    <tr><th>Criterion</th><th>Score</th><th>Details</th></tr>",
        ]

        for name, score in sorted(report.scores.items()):
            if score:
                score_class = "score-high" if score.value >= 0.8 else "score-med" if score.value >= 0.5 else "score-low"
                details = self._format_details_html(score.details)
                lines.append(f"    <tr><td>{name}</td><td class='{score_class}'>{score.value:.3f}</td><td>{details}</td></tr>")
            else:
                lines.append(f"    <tr><td>{name}</td><td colspan='2'><strong>FAILED</strong></td></tr>")

        lines.extend([
            "  </table>",
            "",
            "  <h2>Summary</h2>",
            "  <div class='summary'>",
            "    <pre>",
        ])

        for line in report.summary.split("\n"):
            lines.append(f"      {line}")

        lines.extend([
            "    </pre>",
            "  </div>",
            "",
            "  <h2>Metadata</h2>",
            "  <ul>",
        ])

        md = report.metadata
        lines.append(f"    <li><strong>Crucible Version:</strong> {md.crucible_version}</li>")
        lines.append(f"    <li><strong>LLM Provider:</strong> {md.llm_provider}</li>")
        lines.append(f"    <li><strong>LLM Model:</strong> {md.llm_model}</li>")
        lines.append(f"    <li><strong>Max Iterations:</strong> {md.max_iterations}</li>")

        if md.dataset_id:
            lines.append(f"    <li><strong>Dataset:</strong> {md.dataset_id}</li>")

        lines.extend([
            "  </ul>",
            "</body>",
            "</html>",
        ])

        return "\n".join(lines)

    def _format_details_html(self, details: dict[str, Any]) -> str:
        """Format details for HTML."""
        items = []
        for key, value in details.items():
            if isinstance(value, (dict, list)):
                items.append(f"{key}: {len(value)} items")
            elif isinstance(value, float):
                items.append(f"{key}: {value:.2f}")
            else:
                items.append(f"{key}: {value}")
        return ", ".join(items) if items else "-"
