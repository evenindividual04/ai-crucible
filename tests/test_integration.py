"""
Integration tests for the AI Crucible.

Tests the full pipeline with mocked LLM responses.
"""

import pytest
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from pydantic import ValidationError

from crucible.state import CrucibleState, DesignComponent, Vulnerability, Patch
from crucible.config import CrucibleConfig
from crucible.agents.architect import ArchitectAgent, ArchitectOutput
from crucible.agents.red_team import SecurityHawk, VulnerabilityReport
from crucible.agents.defender import DefenderAgent, PatchOutput
from crucible.judge.controller import JudgeController
from crucible.judge.novelty import NoveltyChecker
from crucible.router.keyword_router import KeywordRouter, route_agents
from backend.src.models import WebSocketEvent
from backend.src.server import run_real_simulation


# Mock LLM responses
MOCK_ARCHITECT_RESPONSE = {
    "design_markdown": """# URL Shortener

## Overview
A simple URL shortening service.

## Components
1. API Gateway - Handles requests
2. URL Store - Stores mappings
3. Redirect Service - Handles redirects
""",
    "components": [
        {
            "component_id": 1,
            "name": "API Gateway",
            "responsibility": "Handle incoming HTTP requests",
            "assumptions": ["Traffic under 1000 RPS", "All requests are valid"],
            "dependencies": [],
        },
        {
            "component_id": 2,
            "name": "URL Store",
            "responsibility": "Store URL mappings in database",
            "assumptions": ["Database is always available", "Data fits in memory"],
            "dependencies": [1],
        },
        {
            "component_id": 3,
            "name": "Redirect Service",
            "responsibility": "Redirect short URLs to original",
            "assumptions": ["Lookup is O(1)", "No cache needed"],
            "dependencies": [2],
        },
    ],
}

MOCK_VULNERABILITY_RESPONSE = {
    "vulnerabilities": [
        {
            "severity": "CRITICAL",
            "confidence": 0.9,
            "title": "SQL Injection in URL validation",
            "description": "User input not sanitized before database query",
            "attack_vector": "Inject SQL via URL parameter",
            "affected_components": [1, 2],
        },
        {
            "severity": "HIGH",
            "confidence": 0.8,
            "title": "Missing rate limiting",
            "description": "No protection against API abuse",
            "attack_vector": "Flood API with requests",
            "affected_components": [1],
        },
    ],
}

MOCK_PATCH_RESPONSE = {
    "patches": [
        {
            "target_vulnerability_id": 1,
            "fix_description": "Add parameterized queries",
            "design_changes": ["Use prepared statements"],
            "introduces_new_assumptions": False,
        },
    ],
    "updated_design_markdown": """# URL Shortener (Patched)

## Overview
A simple URL shortening service with security fixes.

## Components
1. API Gateway - Handles requests with input validation
2. URL Store - Stores mappings using parameterized queries
3. Redirect Service - Handles redirects
""",
}


class TestArchitectAgent:
    """Tests for the Architect agent."""
    
    @pytest.mark.asyncio
    async def test_architect_builds_design(self):
        """Test that Architect generates a valid design."""
        agent = ArchitectAgent()
        
        # Mock the LLM response
        with patch.object(agent, '_invoke_llm', new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = ArchitectOutput(**MOCK_ARCHITECT_RESPONSE)
            
            result = await agent.invoke_async(user_prompt="Design a URL shortener")
            
            assert result.design_markdown is not None
            assert len(result.components) == 3
            assert result.components[0].name == "API Gateway"
    
    def test_architect_prompt_contains_rules(self):
        """Test that Architect prompt includes key rules."""
        agent = ArchitectAgent()
        prompt = agent.get_default_prompt()
        
        assert "UNOPTIMIZED" in prompt or "not optimize" in prompt.lower()
        assert "assumptions" in prompt.lower()


class TestRedTeamAgents:
    """Tests for Red Team agents."""
    
    def test_security_hawk_has_correct_domain(self):
        """Test SecurityHawk has SECURITY domain."""
        agent = SecurityHawk()
        assert agent.domain == "SECURITY"
        assert "Security" in agent.name
    
    def test_attack_surface_contains_key_vectors(self):
        """Test attack surface includes important vectors."""
        agent = SecurityHawk()
        surface = agent.get_attack_surface()
        
        assert "authentication" in surface.lower() or "auth" in surface.lower()
        assert "injection" in surface.lower()


class TestDefenderAgent:
    """Tests for the Defender agent."""
    
    def test_defender_prioritizes_vulnerabilities(self):
        """Test that Defender sorts vulnerabilities by severity."""
        agent = DefenderAgent()
        
        # Create mixed-severity vulnerabilities
        vulns = [
            Vulnerability(
                vulnerability_id=1, severity="LOW", confidence=0.5,
                domain="SECURITY", title="Low issue", description="",
                attack_vector="", affected_components=[], iteration_found=0,
            ),
            Vulnerability(
                vulnerability_id=2, severity="CRITICAL", confidence=0.9,
                domain="SECURITY", title="Critical issue", description="",
                attack_vector="", affected_components=[], iteration_found=0,
            ),
            Vulnerability(
                vulnerability_id=3, severity="HIGH", confidence=0.7,
                domain="SECURITY", title="High issue", description="",
                attack_vector="", affected_components=[], iteration_found=0,
            ),
        ]
        
        message = agent.build_user_message(
            design_markdown="# Test",
            components=[],
            vulnerabilities=vulns,
        )
        
        # CRITICAL should appear before HIGH, which should appear before LOW
        critical_pos = message.find("Critical issue")
        high_pos = message.find("High issue")
        low_pos = message.find("Low issue")
        
        assert critical_pos < high_pos < low_pos


class TestJudgeController:
    """Tests for the Judge controller."""
    
    def test_validate_design_rejects_empty(self):
        """Test that Judge rejects designs with no components."""
        judge = JudgeController()
        state = CrucibleState(user_prompt="Test")
        
        is_valid, reason = judge.validate_design(state)
        
        assert not is_valid
        assert "No components" in reason
    
    def test_validate_design_accepts_valid(self, sample_state_with_design):
        """Test that Judge accepts valid designs."""
        judge = JudgeController()
        
        is_valid, reason = judge.validate_design(sample_state_with_design)
        
        assert is_valid
    
    def test_decide_termination_at_max_iterations(self):
        """Test termination at iteration cap."""
        judge = JudgeController()
        state = CrucibleState(user_prompt="Test", max_iterations=3)
        state.iteration_count = 3
        
        decision = judge.decide_termination(state)
        
        assert decision.decision in ("TERMINATE_STABLE", "TERMINATE_UNRESOLVED")


class TestNoveltyChecker:
    """Tests for duplicate detection."""
    
    def test_exact_duplicate_detection(self):
        """Test that exact duplicates are detected."""
        checker = NoveltyChecker()
        
        vuln1 = Vulnerability(
            vulnerability_id=1, severity="HIGH", confidence=0.8,
            domain="SECURITY", title="SQL Injection",
            description="Input not sanitized",
            attack_vector="Inject via parameter",
            affected_components=[1], iteration_found=0,
        )
        
        vuln2 = Vulnerability(
            vulnerability_id=2, severity="HIGH", confidence=0.8,
            domain="SECURITY", title="SQL Injection",
            description="Input not sanitized",
            attack_vector="Inject via parameter",
            affected_components=[1], iteration_found=0,
        )
        
        # Force fallback to exact match
        checker._load_attempted = True
        checker._model_loaded = False
        
        is_dup = checker.is_duplicate(vuln2, [vuln1])
        assert is_dup
    
    def test_filter_novel_removes_duplicates(self):
        """Test that filter_novel removes duplicates."""
        checker = NoveltyChecker()
        checker._load_attempted = True
        checker._model_loaded = False
        
        existing = [
            Vulnerability(
                vulnerability_id=1, severity="HIGH", confidence=0.8,
                domain="SECURITY", title="Issue A", description="",
                attack_vector="Attack A", affected_components=[], iteration_found=0,
            ),
        ]
        
        candidates = [
            Vulnerability(
                vulnerability_id=2, severity="HIGH", confidence=0.8,
                domain="SECURITY", title="Issue A", description="",
                attack_vector="Attack A", affected_components=[], iteration_found=0,
            ),
            Vulnerability(
                vulnerability_id=3, severity="MEDIUM", confidence=0.7,
                domain="LOGIC", title="Issue B", description="",
                attack_vector="Attack B", affected_components=[], iteration_found=0,
            ),
        ]
        
        novel = checker.filter_novel(candidates, existing)
        
        assert len(novel) == 1
        assert novel[0].title == "Issue B"


class TestKeywordRouter:
    """Tests for keyword-based routing."""
    
    def test_security_keywords_activate_security_hawk(self):
        """Test that auth keywords activate SecurityHawk."""
        state = CrucibleState(
            user_prompt="Design a system with user authentication",
            design_markdown="# System with login and password",
        )
        
        agents = route_agents(state)
        
        assert "SecurityHawk" in agents
    
    def test_database_keywords_activate_scale_monster(self):
        """Test that database keywords activate ScaleMonster."""
        state = CrucibleState(
            user_prompt="Design a system",
            design_markdown="# System with database and caching",
        )
        
        agents = route_agents(state)
        
        assert "ScaleMonster" in agents
    
    def test_no_keywords_activates_all(self):
        """Test that no matching keywords activates all agents."""
        state = CrucibleState(
            user_prompt="Hello",
            design_markdown="# Empty",
        )
        
        agents = route_agents(state)
        
        # Should activate all agents as fallback (4 original + 3 v2 agents)
        assert len(agents) == 7


class TestEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_iteration_flow(self, sample_state_with_design):
        """Test a complete iteration flow."""
        state = sample_state_with_design
        judge = JudgeController()
        
        # Validate design
        is_valid, _ = judge.validate_design(state)
        assert is_valid
        
        # Route agents
        agents = route_agents(state)
        assert len(agents) > 0
        
        # Simulate attacks (mock vulnerabilities)
        mock_vulns = [
            Vulnerability(
                vulnerability_id=1, severity="CRITICAL", confidence=0.9,
                domain="SECURITY", title="Test Vuln", description="",
                attack_vector="Test attack", affected_components=[1], iteration_found=0,
            ),
        ]
        
        # Evaluate attacks
        novel, decision = judge.evaluate_attacks(state, mock_vulns)
        
        assert len(novel) == 1
        assert decision.decision == "CONTINUE_TO_DEFEND"


class TestDashboardTelemetryEvents:
    """Contract tests for optional dashboard telemetry event types."""

    @pytest.mark.parametrize(
        ("event_type", "payload"),
        [
            ("ATTACK_EFFECTIVENESS_UPDATE", [{"agent": "SecurityHawk", "effectiveness_ratio": 0.8}]),
            ("DEFENSE_QUALITY_UPDATE", {"first_time_fix_rate": 0.7}),
            ("CONVERGENCE_UPDATE", {"iterations_to_stable": 2}),
        ],
    )
    def test_websocket_event_accepts_optional_telemetry_types(self, event_type, payload):
        evt = WebSocketEvent(type=event_type, data=payload)
        assert evt.type == event_type

    def test_websocket_event_rejects_unknown_type(self):
        with pytest.raises(ValidationError):
            WebSocketEvent(type="UNKNOWN_TELEMETRY", data={})

    def test_websocket_event_accepts_attack_effectiveness_series_payload(self):
        evt = WebSocketEvent(
            type="ATTACK_EFFECTIVENESS_UPDATE",
            data=[
                {"agent": "SecurityHawk", "effectiveness_ratio": 0.8},
                {"agent": "ScaleMonster", "effectiveness_ratio": 0.6},
            ],
        )
        assert isinstance(evt.data, list)
        assert evt.data[0]["agent"] == "SecurityHawk"

    def test_websocket_event_rejects_attack_effectiveness_dict_payload(self):
        with pytest.raises(ValidationError):
            WebSocketEvent(
                type="ATTACK_EFFECTIVENESS_UPDATE",
                data={"agent": "SecurityHawk", "effectiveness_ratio": 0.8},
            )

    def test_websocket_event_rejects_defense_quality_list_payload(self):
        with pytest.raises(ValidationError):
            WebSocketEvent(
                type="DEFENSE_QUALITY_UPDATE",
                data=[{"first_time_fix_rate": 0.5}],
            )


class TestRealtimeTelemetryStreaming:
    """Contract tests for websocket telemetry streaming sequence."""

    @pytest.mark.asyncio
    async def test_run_real_simulation_emits_telemetry_before_simulation_end(self, monkeypatch):
        class FakeWebSocket:
            def __init__(self):
                self.events = []

            async def send_json(self, payload):
                self.events.append(payload)

        fake_state = SimpleNamespace(
            design_components=[],
            iteration_summaries=[],
            max_iterations=1,
            active_agents=[],
            vulnerabilities=[],
            patches=[],
            security_scores=[],
            status="STABLE",
            termination_reason="done",
            iteration_count=1,
            current_security_score=95,
            attack_effectiveness=[],
            defense_quality={"regression_rate": 0.0},
            convergence_metrics={"iterations_to_stable": 1},
        )

        monkeypatch.setattr("crucible.graph.run_crucible", lambda _prompt: fake_state)

        ws = FakeWebSocket()
        await run_real_simulation(ws, "Design a system", {})

        event_types = [evt["type"] for evt in ws.events]
        assert "ATTACK_EFFECTIVENESS_UPDATE" in event_types
        assert "DEFENSE_QUALITY_UPDATE" in event_types
        assert "CONVERGENCE_UPDATE" in event_types
        assert "SIMULATION_END" in event_types

        attack_idx = event_types.index("ATTACK_EFFECTIVENESS_UPDATE")
        defense_idx = event_types.index("DEFENSE_QUALITY_UPDATE")
        convergence_idx = event_types.index("CONVERGENCE_UPDATE")
        end_idx = event_types.index("SIMULATION_END")

        assert attack_idx < end_idx
        assert defense_idx < end_idx
        assert convergence_idx < end_idx
