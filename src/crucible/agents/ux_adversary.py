"""
UX Adversary Agent for the AI Crucible.

Finds usability failures under edge conditions.
"""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from crucible.agents.base import BaseAgent


class UXVulnerabilityData(BaseModel):
    """Extended vulnerability data for UX issues."""
    
    severity: str
    confidence: float
    title: str
    description: str
    attack_vector: str
    affected_components: List[int]
    user_impact: Literal["FRUSTRATION", "ABANDONMENT", "DATA_LOSS", "CONFUSION"]
    affected_user_segment: str


class UXAdversaryOutput(BaseModel):
    """Output schema for the UX Adversary Agent."""
    
    vulnerabilities: List[dict] = Field(
        description="List of UX vulnerabilities found"
    )


class UXAdversary(BaseAgent[UXAdversaryOutput]):
    """
    Finds usability failures under edge conditions.
    
    Coverage:
    - Slow network / high latency scenarios
    - Mobile-first failures
    - Accessibility violations
    - Error message clarity
    - Timeout and retry UX
    """
    
    name = "UX Adversary"
    domain = "USABILITY"
    
    activation_keywords = [
        "ui", "frontend", "mobile", "user", "form", "input", "display",
        "button", "page", "screen", "interface", "web", "app", "view"
    ]
    
    def get_default_prompt(self) -> str:
        return """You are the UX Adversary in an adversarial system design review.

Your SOLE PURPOSE is to find USABILITY failures and USER EXPERIENCE issues.

## Attack Surfaces

1. **Network Conditions**
   - Slow 3G connections
   - Intermittent connectivity
   - High latency (>500ms)
   - Offline scenarios

2. **Device Diversity**
   - Mobile-first failures
   - Small screen sizes
   - Touch vs. mouse interactions
   - Varying browser capabilities

3. **Accessibility (WCAG)**
   - Screen reader compatibility
   - Keyboard navigation
   - Color contrast issues
   - Focus management

4. **Error Handling UX**
   - Unclear error messages
   - Lost form data on errors
   - Retry mechanisms
   - Loading state clarity

5. **Edge Cases**
   - Empty states
   - Maximum content length
   - Unicode/emoji handling
   - Right-to-left languages

## User Impact Levels

- **FRUSTRATION**: User can complete task but experience is poor
- **ABANDONMENT**: User leaves without completing task
- **DATA_LOSS**: User loses entered data or work
- **CONFUSION**: User doesn't understand what to do

## Output Format

```json
{
  "vulnerabilities": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "confidence": 0.0-1.0,
      "title": "Brief UX issue title",
      "description": "How the UX fails and impact on users",
      "attack_vector": "Specific scenario that triggers the issue",
      "affected_components": [1, 2],
      "user_impact": "FRUSTRATION|ABANDONMENT|DATA_LOSS|CONFUSION",
      "affected_user_segment": "Mobile users on 3G"
    }
  ]
}
```

Think like a frustrated user, not a developer."""
    
    def get_output_schema(self) -> type[UXAdversaryOutput]:
        return UXAdversaryOutput
    
    def build_user_message(
        self,
        design_markdown: str,
        components: List[Any],
        iteration: int,
        **kwargs: Any
    ) -> str:
        comp_list = [{"id": c.component_id, "name": c.name, "responsibility": c.responsibility}
                     for c in components]
        
        return f"""Analyze this system design for USABILITY and UX issues.

--- DESIGN ---
{design_markdown}
--- END DESIGN ---

Components: {comp_list}

Find issues related to:
1. Poor mobile experience
2. Inaccessibility (WCAG violations)
3. Confusing error handling
4. Lost data on failures
5. Slow or unclear loading states

Respond with valid JSON containing found UX vulnerabilities."""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.red_team_seconds
