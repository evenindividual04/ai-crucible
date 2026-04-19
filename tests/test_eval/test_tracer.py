"""
Tests for trace instrumentation.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path

from crucible.eval.tracer import CrucibleTracer
from crucible.eval.schemas import (
    AgentInvokeEvent,
    AgentCompleteEvent,
    IterationStartEvent,
    IterationEndEvent,
    TraceEvent,
    TraceEventType,
    AgentType,
)


class TestCrucibleTracer:
    """Tests for CrucibleTracer."""

    def test_init(self):
        """Test tracer initialization."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test prompt",
            llm_provider="test_provider",
            llm_model="test_model",
        )

        assert tracer.run_id == "test_run"
        assert tracer.user_prompt == "Test prompt"
        assert tracer.enabled == True

    def test_iteration_start(self):
        """Test iteration start event."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.iteration_start({"test": "state"})
        events = tracer.trace.get_events_by_type(TraceEventType.ITERATION_START)

        assert len(events) == 1
        assert events[0].iteration == 1

    def test_iteration_end(self):
        """Test iteration end event."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.iteration_start({"test": "state"})
        tracer.iteration_end({"test": "end_state"})
        events = tracer.trace.get_events_by_type(TraceEventType.ITERATION_END)

        assert len(events) == 1
        assert events[0].iteration == 1

    def test_agent_invoke(self):
        """Test agent invoke event."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.agent_invoke("SecurityHawk", "test_input")
        events = tracer.trace.get_events_by_type(TraceEventType.AGENT_INVOKE)

        assert len(events) == 1
        assert events[0].agent_name == "test_input"

    def test_agent_complete(self):
        """Test agent complete event."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.agent_complete("SecurityHawk", vulnerabilities_found=3, tokens_used=500)
        events = tracer.trace.get_events_by_type(TraceEventType.AGENT_COMPLETE)

        assert len(events) == 1
        assert events[0].vulnerabilities_found == 3
        assert events[0].tokens_used == 500

    def test_finalize(self):
        """Test trace finalization."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        trace = tracer.finalize("STABLE")

        assert trace.status == "STABLE"
        assert trace.end_time is not None
        assert trace.duration_seconds is not None

    def test_get_agent_events(self):
        """Test getting events by agent."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.agent_invoke("SecurityHawk", "input1")
        tracer.agent_complete("SecurityHawk")
        tracer.agent_invoke("ScaleMonster", "input2")

        events = tracer.trace.get_agent_events(AgentType.SECURITY_HAWK)

        assert len(events) == 2
        assert events[0].event_type == TraceEventType.AGENT_INVOKE
        assert events[1].event_type == TraceEventType.AGENT_COMPLETE

    def test_disabled_tracer(self):
        """Test that disabled tracer doesn't record events."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=False,
        )

        tracer.iteration_start({"test": "state"})
        assert len(tracer.trace.events) == 0

    def test_trace_event_type_includes_pr6_event_members(self):
        """PR6 event enum members should be present with stable values."""
        assert TraceEventType.CHAIN_DISCOVERED.value == "chain_discovered"
        assert TraceEventType.CHAIN_MITIGATED.value == "chain_mitigated"
        assert TraceEventType.BENCHMARK_CASE_START.value == "benchmark_case_start"
        assert TraceEventType.BENCHMARK_CASE_END.value == "benchmark_case_end"

    def test_chain_discovered_emits_event_with_expected_payload(self):
        """Tracer should emit chain_discovered with provided payload."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.chain_discovered(
            chain_id=1,
            vulnerability_ids=[3, 9],
            attack_path=["A->B", "B->C"],
            severity="HIGH",
        )
        events = tracer.trace.get_events_by_type(TraceEventType.CHAIN_DISCOVERED)

        assert len(events) == 1
        event = events[0]
        assert event.event_type == TraceEventType.CHAIN_DISCOVERED
        assert event.chain_id == 1
        assert event.vulnerability_ids == [3, 9]
        assert event.attack_path == ["A->B", "B->C"]
        assert event.severity == "HIGH"
        assert event.iteration == 0
        assert event.run_id == "test_run"

    def test_chain_discovered_defaults_optional_fields(self):
        """Optional chain_discovered fields should default to None."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.chain_discovered(chain_id=2, vulnerability_ids=[1])
        events = tracer.trace.get_events_by_type(TraceEventType.CHAIN_DISCOVERED)

        assert len(events) == 1
        event = events[0]
        assert event.chain_id == 2
        assert event.vulnerability_ids == [1]
        assert event.attack_path is None
        assert event.severity is None

    def test_chain_mitigated_emits_event_with_expected_payload(self):
        """Tracer should emit chain_mitigated with provided payload."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.chain_mitigated(
            chain_id=1,
            patch_ids=[7, 8],
            mitigated=True,
            residual_risk=0.1,
        )
        events = tracer.trace.get_events_by_type(TraceEventType.CHAIN_MITIGATED)

        assert len(events) == 1
        event = events[0]
        assert event.event_type == TraceEventType.CHAIN_MITIGATED
        assert event.chain_id == 1
        assert event.patch_ids == [7, 8]
        assert event.mitigated is True
        assert event.residual_risk == pytest.approx(0.1)

    def test_chain_mitigated_defaults_optional_fields(self):
        """Optional chain_mitigated fields should default to None."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.chain_mitigated(chain_id=3, patch_ids=[11], mitigated=False)
        events = tracer.trace.get_events_by_type(TraceEventType.CHAIN_MITIGATED)

        assert len(events) == 1
        event = events[0]
        assert event.patch_ids == [11]
        assert event.mitigated is False
        assert event.residual_risk is None

    def test_benchmark_case_start_emits_event_with_expected_payload(self):
        """Tracer should emit benchmark_case_start with provided payload."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.benchmark_case_start(
            benchmark_id="owasp-mini",
            case_id="case-001",
            input_hash="abc123",
            metadata={"tier": "smoke"},
        )
        events = tracer.trace.get_events_by_type(TraceEventType.BENCHMARK_CASE_START)

        assert len(events) == 1
        event = events[0]
        assert event.event_type == TraceEventType.BENCHMARK_CASE_START
        assert event.benchmark_id == "owasp-mini"
        assert event.case_id == "case-001"
        assert event.input_hash == "abc123"
        assert event.metadata == {"tier": "smoke"}

    def test_benchmark_case_end_emits_event_with_expected_payload(self):
        """Tracer should emit benchmark_case_end with provided payload."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.benchmark_case_end(
            benchmark_id="owasp-mini",
            case_id="case-001",
            success=True,
            score=0.84,
            duration_ms=123.4,
            error_message=None,
        )
        events = tracer.trace.get_events_by_type(TraceEventType.BENCHMARK_CASE_END)

        assert len(events) == 1
        event = events[0]
        assert event.event_type == TraceEventType.BENCHMARK_CASE_END
        assert event.benchmark_id == "owasp-mini"
        assert event.case_id == "case-001"
        assert event.success is True
        assert event.score == pytest.approx(0.84)
        assert event.duration_ms == pytest.approx(123.4)
        assert event.error_message is None

    def test_benchmark_case_end_defaults_optional_fields(self):
        """Optional benchmark_case_end fields should default to None."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.benchmark_case_end(
            benchmark_id="owasp-mini",
            case_id="case-002",
            success=False,
        )
        events = tracer.trace.get_events_by_type(TraceEventType.BENCHMARK_CASE_END)

        assert len(events) == 1
        event = events[0]
        assert event.success is False
        assert event.score is None
        assert event.duration_ms is None
        assert event.error_message is None

    def test_pr6_events_do_not_break_existing_tracer_behavior(self):
        """New PR6 events should coexist with existing event behavior."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=True,
        )

        tracer.iteration_start({"k": "v"})
        tracer.agent_invoke("SecurityHawk", "input")
        tracer.chain_discovered(chain_id=4, vulnerability_ids=[2, 4])
        tracer.benchmark_case_start(benchmark_id="suite", case_id="c1")

        assert len(tracer.trace.get_events_by_type(TraceEventType.ITERATION_START)) == 1
        assert len(tracer.trace.get_events_by_type(TraceEventType.AGENT_INVOKE)) == 1
        assert tracer.trace.get_events_by_type(TraceEventType.AGENT_INVOKE)[0].agent_name == "input"
        assert len(tracer.trace.get_events_by_type(TraceEventType.CHAIN_DISCOVERED)) == 1
        assert len(tracer.trace.get_events_by_type(TraceEventType.BENCHMARK_CASE_START)) == 1

    def test_pr6_methods_respect_disabled_tracer(self):
        """Disabled tracer should not record PR6 events."""
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            enabled=False,
        )

        tracer.chain_discovered(chain_id=1, vulnerability_ids=[1])
        tracer.chain_mitigated(chain_id=1, patch_ids=[1], mitigated=True)
        tracer.benchmark_case_start(benchmark_id="suite", case_id="a")
        tracer.benchmark_case_end(benchmark_id="suite", case_id="a", success=True)

        assert len(tracer.trace.events) == 0

    def test_pr6_events_persist_to_jsonl(self, tmp_path):
        """PR6 events should be written to JSONL when output_path is configured."""
        output_path = tmp_path / "trace.jsonl"
        tracer = CrucibleTracer(
            run_id="test_run",
            user_prompt="Test",
            output_path=output_path,
            enabled=True,
        )

        tracer.chain_discovered(chain_id=10, vulnerability_ids=[1, 2], severity="HIGH")
        tracer.chain_mitigated(chain_id=10, patch_ids=[9], mitigated=True, residual_risk=0.05)
        tracer.benchmark_case_start(benchmark_id="suite", case_id="case-1", input_hash="h1")
        tracer.benchmark_case_end(benchmark_id="suite", case_id="case-1", success=True, score=0.9)

        lines = output_path.read_text().strip().splitlines()
        payloads = [json.loads(line) for line in lines]

        assert len(payloads) == 4
        assert payloads[0]["event_type"] == "chain_discovered"
        assert payloads[0]["chain_id"] == 10
        assert payloads[1]["event_type"] == "chain_mitigated"
        assert payloads[1]["patch_ids"] == [9]
        assert payloads[2]["event_type"] == "benchmark_case_start"
        assert payloads[2]["case_id"] == "case-1"
        assert payloads[3]["event_type"] == "benchmark_case_end"
        assert payloads[3]["success"] is True
