"""
Evaluation schemas for trace instrumentation and reporting.

This module defines Pydantic schemas for capturing execution traces,
evaluation results, and reports. All schemas are designed for
JSON serialization and type safety.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class TraceEventType(str, Enum):
    """Types of trace events captured during execution."""

    # Lifecycle events
    ITERATION_START = "iteration_start"
    ITERATION_END = "iteration_end"
    RUN_START = "run_start"
    RUN_END = "run_end"

    # Agent events
    AGENT_INVOKE = "agent_invoke"
    AGENT_COMPLETE = "agent_complete"

    # Vulnerability events
    VULNERABILITY_FOUND = "vulnerability_found"
    VULNERABILITY_DUPLICATE = "vulnerability_duplicate"

    # Patch events
    PATCH_APPLIED = "patch_applied"
    PATCH_REJECTED = "patch_rejected"

    # Judge events
    JUDGE_DECISION = "judge_decision"
    DESIGN_VALIDATED = "design_validated"

    # System events
    ERROR = "error"
    TIMEOUT = "timeout"


class AgentType(str, Enum):
    """Types of agents in the system."""

    ARCHITECT = "Architect"
    SECURITY_HAWK = "SecurityHawk"
    SCALE_MONSTER = "ScaleMonster"
    COST_ANALYST = "CostAnalyst"
    LOGIC_BREAKER = "LogicBreaker"
    COMPLIANCE = "ComplianceAgent"
    UX_ADVERSARY = "UXAdversary"
    CHAOS_ENGINEER = "ChaosEngineer"
    DEFENDER = "Defender"


class PerturbationType(str, Enum):
    """Types of input perturbations for robustness testing."""

    PARAPHRASE = "paraphrase"
    ADD_NOISE = "add_noise"
    CHANGE_TONE = "change_tone"
    RESTRUCTURE = "restructure"


class JudgeDecisionType(str, Enum):
    """Types of judge decisions."""

    CONTINUE_TO_DEFEND = "continue_to_defend"
    CONTINUE_TO_ATTACK = "continue_to_attack"
    TERMINATE_STABLE = "terminate_stable"
    TERMINATE_UNRESOLVED = "terminate_unresolved"
    TERMINATE_FAILED = "terminate_failed"


# ============================================================================
# Trace Event Schemas
# ============================================================================


class TraceEvent(BaseModel):
    """Base class for all trace events."""

    event_type: TraceEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    iteration: int | None = None
    run_id: str | None = None


class IterationStartEvent(TraceEvent):
    """Event marking the start of an iteration."""

    event_type: Literal[TraceEventType.ITERATION_START] = TraceEventType.ITERATION_START
    state_snapshot: dict[str, Any] | None = None


class IterationEndEvent(TraceEvent):
    """Event marking the end of an iteration."""

    event_type: Literal[TraceEventType.ITERATION_END] = TraceEventType.ITERATION_END
    state_snapshot: dict[str, Any] | None = None
    vulnerabilities_count: int = 0
    patches_count: int = 0
    security_score: float | None = None


class AgentInvokeEvent(TraceEvent):
    """Event marking the start of an agent invocation."""

    event_type: Literal[TraceEventType.AGENT_INVOKE] = TraceEventType.AGENT_INVOKE
    agent_type: AgentType
    agent_name: str
    input_prompt: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class AgentCompleteEvent(TraceEvent):
    """Event marking the completion of an agent invocation."""

    event_type: Literal[TraceEventType.AGENT_COMPLETE] = TraceEventType.AGENT_COMPLETE
    agent_type: AgentType
    agent_name: str
    success: bool
    vulnerabilities_found: int = 0
    tokens_used: int = 0
    duration_ms: float | None = None
    error_message: str | None = None


class VulnerabilityFoundEvent(TraceEvent):
    """Event marking a vulnerability discovery."""

    event_type: Literal[TraceEventType.VULNERABILITY_FOUND] = TraceEventType.VULNERABILITY_FOUND
    vulnerability_id: int
    title: str
    severity: str
    domain: str
    confidence: float
    agent_type: AgentType


class VulnerabilityDuplicateEvent(TraceEvent):
    """Event marking a duplicate vulnerability detection."""

    event_type: Literal[TraceEventType.VULNERABILITY_DUPLICATE] = TraceEventType.VULNERABILITY_DUPLICATE
    vulnerability_id: int
    original_id: int
    similarity_score: float | None = None


class PatchAppliedEvent(TraceEvent):
    """Event marking a patch application."""

    event_type: Literal[TraceEventType.PATCH_APPLIED] = TraceEventType.PATCH_APPLIED
    patch_id: int
    target_vulnerability_id: int
    validated: bool
    introduces_new_assumptions: bool


class PatchRejectedEvent(TraceEvent):
    """Event marking a patch rejection."""

    event_type: Literal[TraceEventType.PATCH_REJECTED] = TraceEventType.PATCH_REJECTED
    patch_id: int
    target_vulnerability_id: int
    rejection_reason: str


class JudgeDecisionEvent(TraceEvent):
    """Event marking a judge decision."""

    event_type: Literal[TraceEventType.JUDGE_DECISION] = TraceEventType.JUDGE_DECISION
    decision: JudgeDecisionType
    vulnerabilities_count: int
    patches_count: int
    security_score: float


class DesignValidatedEvent(TraceEvent):
    """Event marking design validation."""

    event_type: Literal[TraceEventType.DESIGN_VALIDATED] = TraceEventType.DESIGN_VALIDATED
    is_valid: bool
    reason: str | None = None
    components_count: int


class ErrorEvent(TraceEvent):
    """Event marking an error."""

    event_type: Literal[TraceEventType.ERROR] = TraceEventType.ERROR
    error_type: str
    error_message: str
    node: str | None = None


class TimeoutEvent(TraceEvent):
    """Event marking a timeout."""

    event_type: Literal[TraceEventType.TIMEOUT] = TraceEventType.TIMEOUT
    node: str | None = None
    duration_seconds: float


# ============================================================================
# Trace and Report Schemas
# ============================================================================


class Trace(BaseModel):
    """Complete execution trace for a single run."""

    run_id: str
    user_prompt: str
    start_time: datetime
    end_time: datetime | None = None
    events: list[TraceEvent] = Field(default_factory=list)
    status: str | None = None  # STABLE, UNRESOLVED, FAILED

    # Config snapshot
    crucible_version: str = "unknown"
    llm_provider: str = "unknown"
    llm_model: str = "unknown"
    max_iterations: int = 3

    @property
    def duration_seconds(self) -> float | None:
        """Calculate duration of the run."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    @property
    def iteration_count(self) -> int:
        """Get the number of iterations completed."""
        iter_ends = [
            e for e in self.events if e.event_type == TraceEventType.ITERATION_END
        ]
        return len(iter_ends)

    def get_events_by_type(
        self, event_type: TraceEventType
    ) -> list[TraceEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_agent_events(self, agent_type: AgentType) -> list[TraceEvent]:
        """Get all events for a specific agent."""
        return [
            e for e in self.events
            if e.event_type in (TraceEventType.AGENT_INVOKE, TraceEventType.AGENT_COMPLETE)
            and getattr(e, "agent_type", None) == agent_type
        ]


class CriterionScore(BaseModel):
    """Score for a single evaluation criterion."""

    name: str
    value: float = Field(ge=0.0, le=1.0)  # Normalized 0-1
    details: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name}: {self.value:.3f}"


class PerturbationRecord(BaseModel):
    """Record of a perturbation applied to an input."""

    type: PerturbationType
    input: str
    original_input: str
    similarity_score: float | None = None  # Calculated after evaluation


class EvaluationMetadata(BaseModel):
    """Metadata for an evaluation run."""

    crucible_version: str = "unknown"
    llm_provider: str = "unknown"
    llm_model: str = "unknown"
    max_iterations: int = 3
    dataset_id: str | None = None
    config_hash: str | None = None
    perturbations: list[PerturbationRecord] = Field(default_factory=list)
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvaluationReport(BaseModel):
    """Complete evaluation report for a single run."""

    trace_id: str
    run_id: str
    scores: dict[str, CriterionScore] = Field(default_factory=dict)
    aggregate_score: float = Field(ge=0.0, le=1.0)
    aggregation_strategy: str = "weighted_average"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: EvaluationMetadata = Field(default_factory=EvaluationMetadata)
    summary: str = ""

    def add_score(self, score: CriterionScore) -> None:
        """Add a score to the report."""
        self.scores[score.name] = score

    def get_score(self, name: str) -> CriterionScore | None:
        """Get a score by name."""
        return self.scores.get(name)

    def __str__(self) -> str:
        """Human-readable string representation."""
        lines = [
            f"Evaluation Report: {self.trace_id}",
            f"Aggregate Score: {self.aggregate_score:.3f} ({self.aggregation_strategy})",
            f"Scores:"
        ]
        for name, score in self.scores.items():
            lines.append(f"  {score}")
        return "\n".join(lines)


# ============================================================================
# Batch Evaluation Schemas
# ============================================================================


class BatchEvaluationResult(BaseModel):
    """Result of evaluating multiple traces."""

    trace_ids: list[str] = Field(default_factory=list)
    scores: dict[str, list[CriterionScore]] = Field(default_factory=dict)
    aggregate_statistics: dict[str, dict[str, float]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: EvaluationMetadata = Field(default_factory=EvaluationMetadata)


class ComparisonResult(BaseModel):
    """Result of comparing two evaluations."""

    base_trace_id: str
    base_scores: dict[str, CriterionScore]
    compare_trace_id: str
    compare_scores: dict[str, CriterionScore]
    differences: dict[str, float] = Field(default_factory=dict)
    winner: str | None = None  # Which trace performed better overall
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
