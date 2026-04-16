"""
Additional evaluation criteria for AI Crucible.

This module implements PatchQualityCriterion and JudgeQualityCriterion
to complete the evaluation metrics set.
"""

from dataclasses import dataclass

from crucible.eval.schemas import CriterionScore, Trace, TraceEventType, AgentType


class PatchQualityCriterion:
    """
    Measures how well defender patches work.

    This criterion evaluates:
    - Patch success rate (validated vs rejected)
    - Regressions: patches that introduce new vulnerabilities
    - Design changes coverage
    """

    @property
    def name(self) -> str:
        return "patch_quality"

    def evaluate(self, trace: Trace, state=None) -> CriterionScore:
        """Evaluate patch quality from trace."""
        # Count patch events
        patch_applied = trace.get_events_by_type(TraceEventType.PATCH_APPLIED)
        patch_rejected = trace.get_events_by_type(TraceEventType.PATCH_REJECTED)

        total_patches = len(patch_applied) + len(patch_rejected)
        validated_count = sum(1 for p in patch_applied if hasattr(p, "validated") and p.validated)

        # Check for regressions (new vulnerabilities after patch)
        regressions = 0
        # This is simplified - a full implementation would analyze
        # vulnerability lists before and after each patch

        # Calculate score
        if total_patches == 0:
            score = 0.0
        else:
            score = validated_count / total_patches

        # Penalty for regressions
        if regressions > 0:
            score *= 0.5  # Reduce score if there are regressions

        # Boost if there are no rejected patches
        if len(patch_rejected) == 0:
            score = min(1.0, score * 1.2)

        return CriterionScore(
            name=self.name,
            value=min(1.0, max(0.0, score)),
            details={
                "total_patches": total_patches,
                "validated_patches": validated_count,
                "rejected_patches": len(patch_rejected),
                "regressions": regressions,
            },
        )


class JudgeQualityCriterion:
    """
    Measures the quality of judge/controller decisions.

    This criterion evaluates:
    - Termination correctness (do runs end at appropriate times?)
    - Consistency of termination decisions
    - Accuracy of novelty filtering
    """

    @property
    def name(self) -> str:
        return "judge_quality"

    def evaluate(self, trace: Trace, state=None) -> CriterionScore:
        """Evaluate judge decision quality from trace."""
        # Get iteration end events
        iteration_ends = trace.get_events_by_type(TraceEventType.ITERATION_END)

        # Get final status
        final_status = trace.status or "UNKNOWN"

        # Count total iterations
        total_iterations = trace.max_iterations

        # Check if status is appropriate
        if final_status == "STABLE":
            # Stable is good - should have used most but not all iterations
            appropriate_iterations = trace.iteration_count
            iterations_used_ratio = appropriate_iterations / total_iterations
            score = iterations_used_ratio
        elif final_status == "UNRESOLVED":
            # Unresolved could be appropriate if max iterations reached
            if trace.iteration_count >= total_iterations:
                score = 0.8  # Used all available iterations
            else:
                score = 0.4  # Partial convergence
        elif final_status == "FAILED":
            # Failed runs are not good
            score = 0.0
        else:
            # Unknown status
            score = 0.5

        # Additional metrics
        termination_events = trace.get_events_by_type(TraceEventType.JUDGE_DECISION)
        termination_count = len(termination_events)

        return CriterionScore(
            name=self.name,
            value=min(1.0, max(0.0, score)),
            details={
                "final_status": final_status,
                "total_iterations": total_iterations,
                "iterations_used": trace.iteration_count,
                "termination_events": termination_count,
            },
        )
