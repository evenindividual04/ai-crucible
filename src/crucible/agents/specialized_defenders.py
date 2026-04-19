"""
Specialized Defender agents for the AI Crucible.

Provides Quick Fixer, Architect Refactorer, and Defense Coordinator.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Literal
from pydantic import BaseModel, Field

from crucible.agents.base import BaseAgent
from crucible.state import Vulnerability, CrucibleState


DefenderRoute = Literal["QUICK_FIX", "ARCHITECT"]


class DefenderStrategyPolicy(ABC):
  """Policy interface for selecting defender execution mode."""

  name: str

  @abstractmethod
  def select_mode(self, state: CrucibleState) -> DefenderRoute:
    """Select the defender mode for the given state."""


class TacticalFirstStrategy(DefenderStrategyPolicy):
  """Preserves legacy routing behavior (default strategy)."""

  name = "tactical-first"

  def select_mode(self, state: CrucibleState) -> DefenderRoute:
    active_vulns = state.get_active_vulnerabilities()
    has_critical_high = any(v.severity in ("CRITICAL", "HIGH") for v in active_vulns)
    use_architect = has_critical_high and state.iteration_count >= 2
    return "ARCHITECT" if use_architect else "QUICK_FIX"


class BalancedStrategy(DefenderStrategyPolicy):
  """Escalate sooner for persistent high-severity issues."""

  name = "balanced"

  def select_mode(self, state: CrucibleState) -> DefenderRoute:
    active_vulns = state.get_active_vulnerabilities()
    has_critical = any(v.severity == "CRITICAL" for v in active_vulns)
    has_high = any(v.severity == "HIGH" for v in active_vulns)

    if has_critical and state.iteration_count >= 1:
      return "ARCHITECT"
    if has_high and state.iteration_count >= 2:
      return "ARCHITECT"
    return "QUICK_FIX"


class ArchitectureFirstStrategy(DefenderStrategyPolicy):
  """Prefer structural remediation for high-severity vulnerabilities."""

  name = "architecture-first"

  def select_mode(self, state: CrucibleState) -> DefenderRoute:
    active_vulns = state.get_active_vulnerabilities()
    has_critical_high = any(v.severity in ("CRITICAL", "HIGH") for v in active_vulns)
    return "ARCHITECT" if has_critical_high else "QUICK_FIX"


DEFENDER_STRATEGIES: dict[str, DefenderStrategyPolicy] = {
  TacticalFirstStrategy.name: TacticalFirstStrategy(),
  BalancedStrategy.name: BalancedStrategy(),
  ArchitectureFirstStrategy.name: ArchitectureFirstStrategy(),
}


def select_defender_mode(state: CrucibleState) -> DefenderRoute:
  """Resolve configured strategy and select defender mode.

  Unknown strategy values safely fallback to tactical-first.
  """
  strategy = DEFENDER_STRATEGIES.get(
    state.defender_strategy,
    DEFENDER_STRATEGIES["tactical-first"],
  )
  return strategy.select_mode(state)


class QuickFixOutput(BaseModel):
    """Output schema for Quick Fixer - minimal tactical patches."""
    
    patches: List[dict] = Field(
        description="List of tactical patches (max 5 lines each)"
    )
    updated_design_markdown: str = Field(
        description="Design with fixes applied"
    )


class QuickFixer(BaseAgent[QuickFixOutput]):
    """
    Tactical defender for immediate, minimal patches.
    
    Constraints:
    - Max 5 lines of design change per patch
    - Cannot add new components
    - Cannot modify more than 2 existing components
    
    Best for: LOW and MEDIUM severity issues
    """
    
    name = "Quick Fixer"
    
    def get_default_prompt(self) -> str:
        return """You are the Quick Fixer in an adversarial system design review.

Your role is to apply MINIMAL tactical patches for immediate vulnerabilities.

## STRICT Constraints

1. **Max 5 lines of design change per patch**
2. **Cannot add new components** - only modify existing ones
3. **Cannot modify more than 2 existing components per patch**
4. **Focus on LOW and MEDIUM severity first** - leave CRITICAL for Architect

## Good Examples of Quick Fixes
- Add input validation to existing endpoint
- Enable TLS on existing connection
- Add retry logic with backoff
- Set reasonable timeout values
- Add logging for audit trail

## Bad Examples (DO NOT DO)
- "Add a new caching layer" (new component)
- "Rewrite the authentication system" (too big)
- "Add horizontal scaling" (architectural)

## Output Format

```json
{
  "patches": [
    {
      "target_vulnerability_id": 1,
      "fix_description": "Add input sanitization",
      "design_changes": ["Validate URL format before storing"],
      "lines_changed": 2,
      "components_modified": [1]
    }
  ],
  "updated_design_markdown": "..."
}
```

Remember: MINIMAL changes only. If you can't fix it in 5 lines, leave it for the Architect."""
    
    def get_output_schema(self) -> type[QuickFixOutput]:
        return QuickFixOutput
    
    def build_user_message(
        self,
        design_markdown: str,
        components: List[Any],
        vulnerabilities: List[Vulnerability],
        **kwargs: Any
    ) -> str:
        # Filter to LOW and MEDIUM only
        tactical_vulns = [v for v in vulnerabilities if v.severity in ("LOW", "MEDIUM")]
        
        vuln_list = [{"id": v.vulnerability_id, "severity": v.severity, 
                      "title": v.title, "components": v.affected_components}
                     for v in tactical_vulns[:3]]  # Max 3
        
        return f"""Apply TACTICAL fixes to LOW/MEDIUM vulnerabilities.

--- DESIGN ---
{design_markdown}
--- END ---

VULNERABILITIES (LOW/MEDIUM only):
{vuln_list}

Rules:
- Max 5 lines per fix
- No new components
- Max 2 components modified per patch

Respond with JSON."""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.defender_seconds


class ArchitectRefactorOutput(BaseModel):
    """Output schema for Architect Refactorer - structural changes."""
    
    justification: str = Field(
        description="Why tactical fix is impossible"
    )
    patches: List[dict] = Field(
        description="Structural patches with new components"
    )
    new_components: List[dict] = Field(
        description="New components being added"
    )
    updated_design_markdown: str = Field(
        description="Refactored design"
    )


class ArchitectRefactorer(BaseAgent[ArchitectRefactorOutput]):
    """
    Structural defender for fundamental changes when tactical fixes aren't enough.
    
    Constraints:
    - Limited to 1 use per run (expensive operation)
    - Can add new components
    - Can restructure data flow
    - Must justify why tactical fix is impossible
    
    Best for: CRITICAL issues that require fundamental changes
    """
    
    name = "Architect Refactorer"
    
    def get_default_prompt(self) -> str:
        return """You are the Architect Refactorer in an adversarial system design review.

Your role is to make STRUCTURAL changes when tactical fixes are impossible.

## When to Use (ALL must be true)
1. The vulnerability is CRITICAL or HIGH severity
2. A tactical fix (5 lines or less) is NOT possible
3. The issue is fundamental to the design, not just a missing feature

## You CAN
- Add new components (max 2)
- Restructure data flow between components
- Change component responsibilities
- Add new architectural patterns (circuit breaker, bulkhead, etc.)

## You MUST
- Justify why a tactical fix won't work
- Explain the trade-offs of your structural change
- Keep changes minimal even when structural

## Output Format

```json
{
  "justification": "Why tactical fix is impossible: ...",
  "patches": [
    {
      "target_vulnerability_id": 1,
      "fix_description": "Add dedicated auth service",
      "fix_category": "STRUCTURAL",
      "trade_offs": "Adds network hop but isolates auth failures"
    }
  ],
  "new_components": [
    {
      "name": "Auth Service",
      "responsibility": "Handle all authentication",
      "dependencies": [1]
    }
  ],
  "updated_design_markdown": "..."
}
```

Remember: This is expensive. Only use for truly structural issues."""
    
    def get_output_schema(self) -> type[ArchitectRefactorOutput]:
        return ArchitectRefactorOutput
    
    def build_user_message(
        self,
        design_markdown: str,
        components: List[Any],
        vulnerabilities: List[Vulnerability],
        **kwargs: Any
    ) -> str:
        # Filter to CRITICAL and HIGH only
        critical_vulns = [v for v in vulnerabilities 
                         if v.severity in ("CRITICAL", "HIGH")]
        
        vuln_list = [{"id": v.vulnerability_id, "severity": v.severity,
                      "title": v.title, "description": v.description,
                      "components": v.affected_components}
                     for v in critical_vulns[:2]]  # Max 2
        
        return f"""Apply STRUCTURAL fixes to CRITICAL/HIGH vulnerabilities.

--- DESIGN ---
{design_markdown}
--- END ---

CRITICAL VULNERABILITIES:
{vuln_list}

Requirements:
1. Explain why tactical fix is impossible
2. Propose structural change
3. Document trade-offs

Respond with JSON."""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.defender_seconds * 2  # Longer for structural


class DefenseCoordinatorOutput(BaseModel):
    """Output schema for Defense Coordinator."""
    
    conflicts_detected: List[dict] = Field(
        default_factory=list,
        description="Patches that conflict with each other"
    )
    unified_patches: List[dict] = Field(
        description="Patches unified to avoid conflicts"
    )
    new_attack_surfaces: List[str] = Field(
        default_factory=list,
        description="New attack surfaces introduced by patches"
    )
    recommendation: str = Field(
        description="Overall recommendation"
    )


class DefenseCoordinator(BaseAgent[DefenseCoordinatorOutput]):
    """
    Orchestrates multiple fixes to avoid conflicts.
    
    Responsibilities:
    - Detects when patches contradict each other
    - Proposes unified fix for related vulnerabilities
    - Ensures patches don't introduce new attack surfaces
    """
    
    name = "Defense Coordinator"
    
    def get_default_prompt(self) -> str:
        return """You are the Defense Coordinator in an adversarial system design review.

Your role is to ORCHESTRATE multiple patches and detect conflicts.

## Your Responsibilities

1. **Detect Conflicts**
   - Patches that modify the same component in incompatible ways
   - Fixes that undo each other
   - Changes that create deadlocks or race conditions

2. **Propose Unified Fixes**
   - When multiple vulns affect the same component, propose ONE fix
   - Reduce total number of changes

3. **Identify New Attack Surfaces**
   - Does adding auth create a new DoS vector?
   - Does adding caching introduce stale data risks?
   - Does adding logging leak sensitive data?

## Output Format

```json
{
  "conflicts_detected": [
    {
      "patch_ids": [1, 3],
      "conflict_type": "INCOMPATIBLE_CHANGES",
      "description": "Both patches modify Component 2 differently"
    }
  ],
  "unified_patches": [
    {
      "replaces_patch_ids": [1, 3],
      "fix_description": "Combined fix for both issues",
      "design_changes": ["..."]
    }
  ],
  "new_attack_surfaces": [
    "Rate limiting cache could be exhausted by distributed attack"
  ],
  "recommendation": "Apply unified patches. Monitor new attack surface."
}
```

Be thorough but concise."""
    
    def get_output_schema(self) -> type[DefenseCoordinatorOutput]:
        return DefenseCoordinatorOutput
    
    def build_user_message(
        self,
        design_markdown: str,
        patches: List[dict],
        vulnerabilities: List[Vulnerability],
        **kwargs: Any
    ) -> str:
        vuln_summary = [{"id": v.vulnerability_id, "title": v.title, 
                         "components": v.affected_components}
                        for v in vulnerabilities]
        
        return f"""Coordinate these patches and detect conflicts.

--- DESIGN ---
{design_markdown}
--- END ---

PROPOSED PATCHES:
{patches}

VULNERABILITIES ADDRESSED:
{vuln_summary}

Tasks:
1. Detect any conflicts between patches
2. Propose unified fixes where possible
3. Identify any new attack surfaces

Respond with JSON."""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.defender_seconds
