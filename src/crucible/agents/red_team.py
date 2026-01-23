"""
Red Team Agents for the AI Crucible.

Four specialized agents that attack system designs from different angles:
- SecurityHawk: Authentication, authorization, data protection
- ScaleMonster: Concurrency, resource limits, bottlenecks
- CostAnalyst: API usage, storage, compute costs
- LogicBreaker: State transitions, invariants, deadlocks
"""

from abc import abstractmethod
from typing import Any, List, Literal

from pydantic import BaseModel, Field

from crucible.agents.base import BaseAgent
from crucible.state import Vulnerability, DesignComponent


class VulnerabilityReport(BaseModel):
    """Output schema for Red Team agents."""
    
    vulnerabilities: List[dict] = Field(
        description="List of vulnerabilities found in the design"
    )


class RedTeamAgent(BaseAgent[VulnerabilityReport]):
    """Base class for all Red Team agents."""
    
    domain: Literal["SECURITY", "SCALABILITY", "COST", "LOGIC"]
    
    def get_output_schema(self) -> type[VulnerabilityReport]:
        return VulnerabilityReport
    
    def get_timeout(self) -> int:
        return self.config.timeouts.red_team_seconds
    
    @abstractmethod
    def get_attack_surface(self) -> str:
        """Return the attack surface description for this agent."""
        pass
    
    def build_user_message(
        self,
        design_markdown: str,
        components: List[DesignComponent],
        iteration: int,
        **kwargs: Any
    ) -> str:
        components_json = [c.model_dump() for c in components]
        return f"""Analyze this system design and find vulnerabilities in the {self.domain} domain.

--- SYSTEM DESIGN ---
{design_markdown}
--- END DESIGN ---

--- COMPONENTS (for reference) ---
{components_json}
--- END COMPONENTS ---

Current iteration: {iteration}

Attack surface to focus on:
{self.get_attack_surface()}

Find 1-3 vulnerabilities. For each vulnerability, provide:
- severity: CRITICAL, HIGH, MEDIUM, or LOW
- confidence: 0.0 to 1.0 (how certain you are this is a real issue)
- title: Brief title
- description: Detailed explanation
- attack_vector: How an attacker would exploit this
- affected_components: List of component IDs affected

Respond with valid JSON:
```json
{{
  "vulnerabilities": [
    {{
      "severity": "CRITICAL",
      "confidence": 0.85,
      "title": "...",
      "description": "...",
      "attack_vector": "...",
      "affected_components": [1, 2]
    }}
  ]
}}
```"""


class SecurityHawk(RedTeamAgent):
    """Attacks from the SECURITY domain."""
    
    name = "Security Hawk"
    domain = "SECURITY"
    
    def get_default_prompt(self) -> str:
        return """You are the Security Hawk, a Red Team agent focused on SECURITY vulnerabilities.

Your mission: Find exploitable security weaknesses in system designs.

## Attack Surface
- Authentication flows (login, session management, tokens)
- Authorization boundaries (access control, privilege escalation)
- Data storage & transmission (encryption, PII exposure)
- Input validation (injection, XSS, path traversal)
- API security (rate limiting, authentication bypass)

## Rules
1. Each vulnerability MUST reference specific component IDs
2. Provide realistic attack vectors, not generic OWASP lists
3. Confidence should reflect how likely this is a real issue
4. Focus on HIGH and CRITICAL severity issues

You are adversarial. Your job is to BREAK the design."""
    
    def get_attack_surface(self) -> str:
        return """- Authentication flows (login, session, tokens, OAuth)
- Authorization boundaries (access control, privilege escalation)
- Data storage & transmission (encryption at rest/transit, PII)
- Input validation (SQL injection, XSS, SSRF, path traversal)
- API security (authentication bypass, rate limiting gaps)"""


class ScaleMonster(RedTeamAgent):
    """Attacks from the SCALABILITY domain."""
    
    name = "Scale Monster"
    domain = "SCALABILITY"
    
    def get_default_prompt(self) -> str:
        return """You are the Scale Monster, a Red Team agent focused on SCALABILITY vulnerabilities.

Your mission: Break the system under load.

## Attack Surface
- Concurrency issues (race conditions, deadlocks)
- State contention (hot keys, lock contention)
- Resource exhaustion (memory leaks, connection pools)
- Bottlenecks (single points of failure, N+1 queries)
- Cascade failures (thundering herd, retry storms)

## Assumption
Assume 100× expected traffic at peak load.

## Rules
1. Each vulnerability MUST reference specific component IDs
2. Describe the exact failure scenario
3. Confidence should reflect how likely this fails at scale
4. Focus on issues that cause outages, not just slowdowns

You are adversarial. Your job is to BREAK the design."""
    
    def get_attack_surface(self) -> str:
        return """- Concurrency (race conditions, deadlocks, TOCTOU)
- State contention (hot keys, lock contention, leader bottlenecks)
- Resource exhaustion (memory leaks, connection pool starvation, OOM)
- Bottlenecks (single instance, N+1 queries, synchronous calls)
- Cascade failures (thundering herd, retry storms, circuit breaker gaps)

Assume 100× expected traffic."""


class CostAnalyst(RedTeamAgent):
    """Attacks from the COST domain."""
    
    name = "Cost Analyst"
    domain = "COST"
    
    def get_default_prompt(self) -> str:
        return """You are the Cost Analyst, a Red Team agent focused on COST vulnerabilities.

Your mission: Find unsustainable cost growth patterns.

## Attack Surface
- API usage patterns (unbounded calls, no caching)
- Storage amplification (no TTL, data duplication)
- Compute hotspots (expensive operations in hot paths)
- Third-party dependencies (metered services, egress costs)

## Rules
1. Each vulnerability MUST reference specific component IDs
2. Quantify cost direction: ↑ (10-50%), ↑↑ (50-200%), ↑↑↑ (>200%)
3. Don't provide exact dollar amounts, just direction
4. Focus on costs that grow faster than revenue

You are adversarial. Your job is to find cost bombs."""
    
    def get_attack_surface(self) -> str:
        return """- API usage (unbounded calls, missing caching, chatty interfaces)
- Storage (no TTL, data duplication, unbounded growth)
- Compute (expensive operations in hot paths, no pagination)
- Third-party (metered APIs, egress costs, premium feature abuse)

Use ↑ (10-50%), ↑↑ (50-200%), ↑↑↑ (>200%) for cost impact."""


class LogicBreaker(RedTeamAgent):
    """Attacks from the LOGIC domain."""
    
    name = "Logic Breaker"
    domain = "LOGIC"
    
    def get_default_prompt(self) -> str:
        return """You are the Logic Breaker, a Red Team agent focused on LOGIC vulnerabilities.

Your mission: Find invariant violations and state bugs.

## Attack Surface
- State transitions (invalid states, missing transitions)
- Ordering assumptions (out-of-order events, duplicate delivery)
- Partial failure scenarios (half-complete operations)
- Business logic flaws (edge cases, boundary conditions)

## Rules
1. Each vulnerability MUST reference specific component IDs
2. Describe the exact state corruption or logic flaw
3. These are bugs that are NOT security or scale related
4. Focus on issues that cause incorrect behavior

You are adversarial. Your job is to find logic bombs."""
    
    def get_attack_surface(self) -> str:
        return """- State transitions (invalid states, missing error handling)
- Ordering assumptions (out-of-order delivery, idempotency gaps)
- Partial failures (half-complete transactions, orphan data)
- Business logic (edge cases, boundary conditions, off-by-one)
- Invariant violations (constraints not enforced, data corruption)"""
