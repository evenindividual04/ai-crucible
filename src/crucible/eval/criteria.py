"""
Evaluation criteria for AI Crucible.

This module defines the abstract base class for evaluation criteria
and concrete implementations for measuring different aspects of system
performance.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from crucible.eval.schemas import (
    AgentCompleteEvent,
    AgentInvokeEvent,
    CriterionScore,
    IterationEndEvent,
    Trace,
    TraceEventType,
    VulnerabilityFoundEvent,
)
from crucible.state import CrucibleState


class EvaluationCriterion(ABC):
    """
    Abstract base class for evaluation criteria.

    All evaluation criteria should inherit from this class and implement
    the evaluate() method. The evaluate() method returns a normalized
    score between 0 and 1.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this criterion."""
        pass

    @abstractmethod
    def evaluate(self, trace: Trace, state: CrucibleState | None = None) -> CriterionScore:
        """
        Evaluate the trace and return a score.

        Args:
            trace: Complete execution trace
            state: Final state (optional, can be derived from trace)

        Returns:
            CriterionScore with normalized value (0-1)
        """
        pass


class AttackEffectivenessCriterion(EvaluationCriterion):
    """
    Measures how effectively red team agents find vulnerabilities.

    This criterion evaluates:
    - Total vulnerabilities found
    - Breakdown by agent
    - Breakdown by domain
    - Breakdown by severity
    """

    @property
    def name(self) -> str:
        return "attack_effectiveness"

    def evaluate(self, trace: Trace, state: CrucibleState | None = None) -> CriterionScore:
        """Evaluate attack effectiveness."""
        # Count vulnerability found events
        vuln_found_events = trace.get_events_by_type(
            TraceEventType.VULNERABILITY_FOUND
        )

        total_found = len(vuln_found_events)

        # Use state if available, otherwise estimate from trace
        if state:
            # In a real implementation, we'd have ground truth
            # For now, use a simple heuristic
            max_expected = max(1, len(state.design_components) * 2)
        else:
            # Estimate based on design complexity
            max_expected = 5  # Conservative estimate

        # Normalize score (capped at 1.0)
        score = min(1.0, total_found / max_expected) if max_expected > 0 else 0.0

        # Breakdown by agent
        by_agent: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for event in vuln_found_events:
            if isinstance(event, VulnerabilityFoundEvent):
                agent = event.agent_type.value if hasattr(event, "agent_type") else "unknown"
                by_agent[agent] = by_agent.get(agent, 0) + 1
                by_domain[event.domain] = by_domain.get(event.domain, 0) + 1
                by_severity[event.severity] = by_severity.get(event.severity, 0) + 1

        return CriterionScore(
            name=self.name,
            value=score,
            details={
                "total_vulnerabilities_found": total_found,
                "max_expected": max_expected,
                "by_agent": by_agent,
                "by_domain": by_domain,
                "by_severity": by_severity,
            },
        )


class ConvergenceSpeedCriterion(EvaluationCriterion):
    """
    Measures how quickly the system reaches a stable state.

    This criterion evaluates:
    - Number of iterations to stability
    - Security score progression over time
    - Whether convergence was achieved
    """

    @property
    def name(self) -> str:
        return "convergence_speed"

    def evaluate(self, trace: Trace, state: CrucibleState | None = None) -> CriterionScore:
        """Evaluate convergence speed."""
        iterations = trace.iteration_count
        max_iterations = trace.max_iterations

        # Get final status
        status = trace.status or "UNKNOWN"

        # Get security score progression
        iteration_events = trace.get_events_by_type(TraceEventType.ITERATION_END)

        security_scores = []
        for event in iteration_events:
            if isinstance(event, IterationEndEvent) and event.security_score is not None:
                security_scores.append(event.security_score)

        # Normalize score based on iterations used
        if status == "STABLE":
            # Perfect convergence uses few iterations
            score = 1.0 if iterations <= 1 else (1.0 / iterations)
        elif status == "UNRESOLVED":
            # Partial convergence based on iterations
            score = (max_iterations - iterations) / max_iterations * 0.5
        else:
            # Failed convergence
            score = 0.0

        # Boost score if security score improved
        if len(security_scores) >= 2:
            improvement = security_scores[-1] - security_scores[0]
            score += min(0.2, improvement / 100.0)

        return CriterionScore(
            name=self.name,
            value=min(1.0, max(0.0, score)),
            details={
                "iterations": iterations,
                "max_iterations": max_iterations,
                "status": status,
                "security_scores": security_scores,
            },
        )


class RedundancyCriterion(EvaluationCriterion):
    """
    Detects circular reasoning and redundant patterns.

    This criterion identifies:
    - Repeated vulnerability discoveries
    - Circular reasoning patterns
    - Agent behavior repetition
    """

    @property
    def name(self) -> str:
        return "redundancy"

    def evaluate(self, trace: Trace, state: CrucibleState | None = None) -> CriterionScore:
        """Evaluate redundancy in reasoning."""
        # Count duplicate vulnerability events
        duplicate_events = trace.get_events_by_type(
            TraceEventType.VULNERABILITY_DUPLICATE
        )

        duplicates = len(duplicate_events)

        # Get total vulnerability events
        vuln_found_events = trace.get_events_by_type(
            TraceEventType.VULNERABILITY_FOUND
        )
        total_vulns = len(vuln_found_events)

        # Count repeated agent actions
        agent_events = trace.get_events_by_type(TraceEventType.AGENT_INVOKE)

        agent_actions: dict[str, list] = {}
        for event in agent_events:
            if isinstance(event, AgentInvokeEvent):
                key = f"{event.agent_type.value}"
                if key not in agent_actions:
                    agent_actions[key] = []
                agent_actions[key].append(event.timestamp)

        # Check for repeated agent invocations in same iteration
        repeated_in_iteration = 0
        by_iter: dict[int, list[AgentInvokeEvent]] = {}

        for event in agent_events:
            if isinstance(event, AgentInvokeEvent) and event.iteration:
                if event.iteration not in by_iter:
                    by_iter[event.iteration] = []
                by_iter[event.iteration].append(event)

        for iter_events in by_iter.values():
            agent_types = [e.agent_type.value for e in iter_events]
            # Count duplicates within iteration
            if len(agent_types) != len(set(agent_types)):
                repeated_in_iteration += len(agent_types) - len(set(agent_types))

        # Calculate redundancy score
        total_actions = len(agent_events)
        total_patterns = duplicates + repeated_in_iteration

        if total_actions > 0:
            score = 1.0 - (total_patterns / total_actions)
        else:
            score = 1.0

        return CriterionScore(
            name=self.name,
            value=min(1.0, max(0.0, score)),
            details={
                "duplicate_vulnerabilities": duplicates,
                "repeated_agent_actions_in_iteration": repeated_in_iteration,
                "total_actions": total_actions,
                "total_patterns": total_patterns,
            },
        )


class TokenEfficiencyCriterion(EvaluationCriterion):
    """
    Measures resource efficiency (tokens per vulnerability found).

    This criterion evaluates:
    - Tokens used per vulnerability
    - Token usage by agent
    - Cost effectiveness
    """

    @property
    def name(self) -> str:
        return "token_efficiency"

    def evaluate(self, trace: Trace, state: CrucibleState | None = None) -> CriterionScore:
        """Evaluate token efficiency."""
        # Get token usage from agent events
        agent_events = trace.get_events_by_type(TraceEventType.AGENT_COMPLETE)

        total_tokens = 0
        tokens_by_agent: dict[str, int] = {}

        for event in agent_events:
            if isinstance(event, AgentCompleteEvent):
                agent = event.agent_type.value if hasattr(event, "agent_type") else "unknown"
                tokens = event.tokens_used
                total_tokens += tokens
                tokens_by_agent[agent] = tokens_by_agent.get(agent, 0) + tokens

        # Get vulnerabilities found
        vuln_found_events = trace.get_events_by_type(
            TraceEventType.VULNERABILITY_FOUND
        )
        total_vulns = len(vuln_found_events)

        # Calculate efficiency
        if total_vulns == 0:
            score = 0.0
        elif total_tokens == 0:
            score = 1.0
        else:
            # Aim for < 1000 tokens per vulnerability
            tokens_per_vuln = total_tokens / total_vulns
            score = max(0.0, 1.0 - (tokens_per_vuln / 5000.0))

        return CriterionScore(
            name=self.name,
            value=min(1.0, max(0.0, score)),
            details={
                "total_tokens": total_tokens,
                "vulnerabilities_found": total_vulns,
                "tokens_per_vulnerability": total_tokens / total_vulns if total_vulns > 0 else 0,
                "tokens_by_agent": tokens_by_agent,
            },
        )


