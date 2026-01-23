"""
Architect Agent for the AI Crucible.

Generates the initial system design from the user's prompt.
Intentionally does not optimize for security, scale, or cost.
"""

from typing import Any, List

from pydantic import BaseModel, Field

from crucible.agents.base import BaseAgent
from crucible.state import DesignComponent


class ArchitectOutput(BaseModel):
    """Output schema for the Architect agent."""
    
    design_markdown: str = Field(
        description="Human-readable system design in Markdown format"
    )
    components: List[DesignComponent] = Field(
        description="List of system components with their responsibilities and assumptions"
    )


class ArchitectAgent(BaseAgent[ArchitectOutput]):
    """
    Generates initial system design without defensive optimization.
    
    The Architect intentionally creates "naive" designs that are
    attackable by the Red Team, surfacing stronger adversarial signals.
    """
    
    name = "Architect"
    prompt_file = "architect.md"
    
    def get_default_prompt(self) -> str:
        return """You are the Architect agent in an adversarial system design review.

Your role is to generate an INITIAL system design based on the user's prompt.

## Critical Rules

1. Generate a realistic but UNOPTIMIZED design
2. Do NOT include:
   - Security hardening (no auth, encryption optimizations)
   - Scale optimizations (no caching, sharding, replicas)
   - Cost optimizations (no resource limits, quotas)
3. You MUST explicitly list assumptions for each component
4. Keep the design simple enough to be attacked

## Output Format

You must respond with a JSON object containing:

```json
{
  "design_markdown": "# System Design\\n\\n## Overview\\n...",
  "components": [
    {
      "component_id": 1,
      "name": "Component Name",
      "responsibility": "What this component does",
      "assumptions": ["Assumption 1", "Assumption 2"],
      "dependencies": []
    }
  ]
}
```

## Component Guidelines

- Each component must have at least 2 assumptions
- Use clear, specific names
- Define responsibilities precisely
- List dependencies as component IDs

Remember: Your job is to create a design that CAN be attacked, not a perfect design."""
    
    def get_output_schema(self) -> type[ArchitectOutput]:
        return ArchitectOutput
    
    def build_user_message(self, user_prompt: str, **kwargs: Any) -> str:
        return f"""Please design a system for the following requirement:

--- USER REQUIREMENT ---
{user_prompt}
--- END REQUIREMENT ---

Generate an initial system design with 3-6 components. Remember to:
1. List explicit assumptions for each component
2. Do NOT optimize for security, scale, or cost
3. Create a design that can be meaningfully attacked

Respond with valid JSON only."""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.architect_seconds
