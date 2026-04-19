"""
Trace instrumentation layer for AI Crucible.

This module provides the CrucibleTracer class which instruments LangGraph
execution to capture trace events including state transitions, agent invocations,
vulnerability discoveries, and judge decisions.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from crucible.eval.schemas import (
    AgentCompleteEvent,
    AgentInvokeEvent,
    AgentType,
    BenchmarkCaseEndEvent,
    BenchmarkCaseStartEvent,
    ChainDiscoveredEvent,
    ChainMitigatedEvent,
    DesignValidatedEvent,
    IterationEndEvent,
    IterationStartEvent,
    JudgeDecisionEvent,
    JudgeDecisionType,
    PatchAppliedEvent,
    PatchRejectedEvent,
    Trace,
    TraceEvent,
    TraceEventType,
    VulnerabilityDuplicateEvent,
    VulnerabilityFoundEvent,
)
from crucible.state import CrucibleState


class CrucibleTracer:
    """
    Instrumentation tracer for AI Crucible execution.

    The tracer captures events during LangGraph execution and stores them
    for later evaluation. Events are appended to an in-memory trace
    and optionally written to disk in JSONL format.
    """

    def __init__(
        self,
        run_id: str,
        user_prompt: str,
        llm_provider: str = "unknown",
        llm_model: str = "unknown",
        max_iterations: int = 3,
        output_path: Path | None = None,
        enabled: bool = True,
    ):
        """
        Initialize the tracer.

        Args:
            run_id: Unique identifier for this run
            user_prompt: The original user prompt/design request
            llm_provider: LLM provider being used
            llm_model: LLM model being used
            max_iterations: Maximum iterations for this run
            output_path: Path to write trace JSONL file (optional)
            enabled: Whether tracing is enabled
        """
        self.run_id = run_id
        self.user_prompt = user_prompt
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.max_iterations = max_iterations
        self.output_path = output_path
        self.enabled = enabled

        self._trace = Trace(
            run_id=run_id,
            user_prompt=user_prompt,
            start_time=datetime.now(timezone.utc),
            crucible_version="unknown",  # Will be set from package
            llm_provider=llm_provider,
            llm_model=llm_model,
            max_iterations=max_iterations,
        )

        self._lock = threading.Lock()
        self._iteration: int = 0

    @property
    def trace(self) -> Trace:
        """Get the current trace."""
        return self._trace

    def add_event(self, event: TraceEvent) -> None:
        """Add an event to the trace."""
        if not self.enabled:
            return

        with self._lock:
            event.run_id = self.run_id
            event.iteration = self._iteration if event.iteration is None else event.iteration
            self._trace.events.append(event)

        # Write to file immediately if path is set
        if self.output_path:
            self._append_event_to_file(event)

    def _snapshot_state(self, state: CrucibleState | dict[str, Any] | None) -> dict[str, Any] | None:
        """Convert a state object into a serializable snapshot."""
        if state is None:
            return None

        if hasattr(state, "model_dump"):
            return state.model_dump(exclude_none=True)

        if isinstance(state, dict):
            return dict(state)

        return {"value": str(state)}

    def _append_event_to_file(self, event: TraceEvent) -> None:
        """Append an event to the JSONL file."""
        if not self.output_path:
            return

        try:
            with open(self.output_path, "a") as f:
                f.write(event.model_dump_json(exclude_none=True) + "\n")
        except Exception:
            # Don't let tracing errors break the main execution
            pass

    def iteration_start(self, state: CrucibleState) -> None:
        """Mark the start of an iteration."""
        self._iteration += 1
        event = IterationStartEvent(
            iteration=self._iteration,
            state_snapshot=self._snapshot_state(state),
        )
        self.add_event(event)

    def iteration_end(self, state: CrucibleState) -> None:
        """Mark the end of an iteration."""
        security_score = None
        if state and hasattr(state, "current_security_score"):
            security_score = state.current_security_score

        if hasattr(state, "vulnerabilities"):
            vulnerabilities_count = len(state.vulnerabilities)
        elif isinstance(state, dict):
            vulnerabilities_count = len(state.get("vulnerabilities", []))
        else:
            vulnerabilities_count = 0

        if hasattr(state, "patches"):
            patches_count = len(state.patches)
        elif isinstance(state, dict):
            patches_count = len(state.get("patches", []))
        else:
            patches_count = 0

        event = IterationEndEvent(
            iteration=self._iteration,
            state_snapshot=self._snapshot_state(state),
            vulnerabilities_count=vulnerabilities_count,
            patches_count=patches_count,
            security_score=security_score,
        )
        self.add_event(event)

    def agent_invoke(
        self,
        agent_type: str | AgentType,
        agent_name: str,
        input_prompt: str | None = None,
    ) -> None:
        """Mark the start of an agent invocation."""
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError:
                # Unknown agent type, use string representation
                pass

        event = AgentInvokeEvent(
            agent_type=agent_type if isinstance(agent_type, AgentType) else AgentType.DEFENDER,
            agent_name=agent_name,
            input_prompt=input_prompt,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
        )
        self.add_event(event)

    def agent_complete(
        self,
        agent_type: str | AgentType,
        agent_name: str | None = None,
        success: bool = True,
        vulnerabilities_found: int = 0,
        tokens_used: int = 0,
        duration_ms: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Mark the completion of an agent invocation."""
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError:
                pass

        if agent_name is None:
            agent_name = agent_type.value if isinstance(agent_type, AgentType) else str(agent_type)

        event = AgentCompleteEvent(
            agent_type=agent_type if isinstance(agent_type, AgentType) else AgentType.DEFENDER,
            agent_name=agent_name,
            success=success,
            vulnerabilities_found=vulnerabilities_found,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        self.add_event(event)

    def vulnerability_found(
        self,
        vulnerability_id: int,
        title: str,
        severity: str,
        domain: str,
        confidence: float,
        agent_type: str | AgentType,
    ) -> None:
        """Mark a vulnerability discovery."""
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError:
                pass

        event = VulnerabilityFoundEvent(
            vulnerability_id=vulnerability_id,
            title=title,
            severity=severity,
            domain=domain,
            confidence=confidence,
            agent_type=agent_type if isinstance(agent_type, AgentType) else AgentType.SECURITY_HAWK,
        )
        self.add_event(event)

    def vulnerability_duplicate(
        self,
        vulnerability_id: int,
        original_id: int,
        similarity_score: float | None = None,
    ) -> None:
        """Mark a duplicate vulnerability detection."""
        event = VulnerabilityDuplicateEvent(
            vulnerability_id=vulnerability_id,
            original_id=original_id,
            similarity_score=similarity_score,
        )
        self.add_event(event)

    def patch_applied(
        self,
        patch_id: int,
        target_vulnerability_id: int,
        validated: bool = True,
        introduces_new_assumptions: bool = False,
    ) -> None:
        """Mark a patch application."""
        event = PatchAppliedEvent(
            patch_id=patch_id,
            target_vulnerability_id=target_vulnerability_id,
            validated=validated,
            introduces_new_assumptions=introduces_new_assumptions,
        )
        self.add_event(event)

    def patch_rejected(
        self,
        patch_id: int,
        target_vulnerability_id: int,
        rejection_reason: str,
    ) -> None:
        """Mark a patch rejection."""
        event = PatchRejectedEvent(
            patch_id=patch_id,
            target_vulnerability_id=target_vulnerability_id,
            rejection_reason=rejection_reason,
        )
        self.add_event(event)

    def chain_discovered(
        self,
        chain_id: int,
        vulnerability_ids: list[int],
        attack_path: list[str] | None = None,
        severity: str | None = None,
    ) -> None:
        """Mark discovery of an attack chain."""
        event = ChainDiscoveredEvent(
            chain_id=chain_id,
            vulnerability_ids=vulnerability_ids,
            attack_path=attack_path,
            severity=severity,
        )
        self.add_event(event)

    def chain_mitigated(
        self,
        chain_id: int,
        patch_ids: list[int],
        mitigated: bool,
        residual_risk: float | None = None,
    ) -> None:
        """Mark mitigation status of an attack chain."""
        event = ChainMitigatedEvent(
            chain_id=chain_id,
            patch_ids=patch_ids,
            mitigated=mitigated,
            residual_risk=residual_risk,
        )
        self.add_event(event)

    def benchmark_case_start(
        self,
        benchmark_id: str,
        case_id: str,
        input_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mark the start of a benchmark case."""
        event = BenchmarkCaseStartEvent(
            benchmark_id=benchmark_id,
            case_id=case_id,
            input_hash=input_hash,
            metadata=metadata,
        )
        self.add_event(event)

    def benchmark_case_end(
        self,
        benchmark_id: str,
        case_id: str,
        success: bool,
        score: float | None = None,
        duration_ms: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Mark completion of a benchmark case."""
        event = BenchmarkCaseEndEvent(
            benchmark_id=benchmark_id,
            case_id=case_id,
            success=success,
            score=score,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        self.add_event(event)

    def judge_decision(
        self,
        decision: str | JudgeDecisionType,
        vulnerabilities_count: int = 0,
        patches_count: int = 0,
        security_score: float = 0.0,
    ) -> None:
        """Mark a judge decision."""
        if isinstance(decision, str):
            try:
                decision = JudgeDecisionType(decision.lower())
            except ValueError:
                # Unknown decision, use CONTINUE_TO_ATTACK as fallback
                decision = JudgeDecisionType.CONTINUE_TO_ATTACK

        event = JudgeDecisionEvent(
            decision=decision,
            vulnerabilities_count=vulnerabilities_count,
            patches_count=patches_count,
            security_score=security_score,
        )
        self.add_event(event)

    def design_validated(
        self,
        is_valid: bool,
        reason: str | None = None,
        components_count: int = 0,
    ) -> None:
        """Mark a design validation."""
        event = DesignValidatedEvent(
            is_valid=is_valid,
            reason=reason,
            components_count=components_count,
        )
        self.add_event(event)

    def finalize(self, status: str) -> Trace:
        """Finalize the trace and return it."""
        self._trace.end_time = datetime.now(timezone.utc)
        self._trace.status = status

        # Write final trace to file if path is set
        if self.output_path:
            self._write_final_trace()

        return self._trace

    def _write_final_trace(self) -> None:
        """Write the complete trace to a JSON file."""
        if not self.output_path:
            return

        # Write to same directory as JSONL, but with .json extension
        json_path = self.output_path.with_suffix(".json")
        try:
            with open(json_path, "w") as f:
                json.dump(
                    self._trace.model_dump(exclude_none=True),
                    f,
                    indent=2,
                    default=str,
                )
        except Exception:
            # Don't let tracing errors break the main execution
            pass

    @classmethod
    def from_checkpoint(
        cls,
        run_id: str,
        checkpoint_path: Path,
        user_prompt: str,
    ) -> "CrucibleTracer":
        """
        Create a tracer from an existing checkpoint.

        This enables evaluation of previously-run executions that didn't
        have explicit tracing enabled. The trace is reconstructed
        from checkpoint data.

        Args:
            run_id: Unique identifier for the run
            checkpoint_path: Path to the checkpoint directory
            user_prompt: The original user prompt

        Returns:
            A CrucibleTracer instance with reconstructed trace
        """
        tracer = cls(
            run_id=run_id,
            user_prompt=user_prompt,
            enabled=False,  # Reconstruction mode
        )

        # TODO: Implement checkpoint reconstruction
        # This would:
        # 1. Load all iter_{N}.json files
        # 2. Reconstruct event sequence
        # 3. Estimate missing data (timing, etc.)

        return tracer


def trace_decorator(tracer: CrucibleTracer):
    """
    Decorator to wrap a function with tracing instrumentation.

    Usage:
        @trace_decorator(tracer)
        def some_function(state):
            # Function execution is traced
            pass
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            # Before function execution
            start_time = datetime.now(timezone.utc)

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # After function execution (even on error)
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                # Log completion event
                # This is a simplified version - actual implementation
                # would be more specific based on the function being wrapped

        return wrapper

    return decorator
