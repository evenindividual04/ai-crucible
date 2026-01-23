"""
Defender Agent for the AI Crucible.

Applies minimal, targeted patches to address specific vulnerabilities.
"""

from typing import Any, List

from pydantic import BaseModel, Field

from crucible.agents.base import BaseAgent
from crucible.state import Vulnerability, DesignComponent, Patch


class PatchOutput(BaseModel):
    """Output schema for the Defender agent."""
    
    patches: List[dict] = Field(
        description="List of patches to apply"
    )
    updated_design_markdown: str = Field(
        description="Updated design with patches applied"
    )


class DefenderAgent(BaseAgent[PatchOutput]):
    """
    Applies minimal fixes to address specific vulnerabilities.
    
    Constraints:
    - Max 3 patches per iteration
    - One patch per vulnerability
    - No architectural rewrites
    """
    
    name = "Defender"
    prompt_file = "defender.md"
    
    def get_default_prompt(self) -> str:
        return """You are the Defender agent in an adversarial system design review.

Your role is to apply MINIMAL patches to address specific vulnerabilities.

## Critical Rules

1. Maximum 3 patches per iteration
2. One patch targets ONE vulnerability
3. NO architectural rewrites - only targeted fixes
4. Each patch must reference the vulnerability ID it addresses
5. Patches should be the MINIMUM change needed

## Forbidden Actions
- Adding entirely new major components
- Rewriting the core architecture
- Blanket fixes like "add caching everywhere"
- Over-engineering solutions

## Output Format

```json
{
  "patches": [
    {
      "target_vulnerability_id": 1,
      "fix_description": "Brief description of the fix",
      "design_changes": ["Specific change 1", "Specific change 2"],
      "introduces_new_assumptions": false
    }
  ],
  "updated_design_markdown": "# Updated Design\\n..."
}
```

Remember: Apply the MINIMUM fix needed. Don't over-engineer."""
    
    def get_output_schema(self) -> type[PatchOutput]:
        return PatchOutput
    
    def build_user_message(
        self,
        design_markdown: str,
        components: List[DesignComponent],
        vulnerabilities: List[Vulnerability],
        **kwargs: Any
    ) -> str:
        # Prioritize vulnerabilities: CRITICAL > HIGH > MEDIUM > LOW
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_vulns = sorted(
            vulnerabilities,
            key=lambda v: (severity_order.get(v.severity, 4), -v.confidence)
        )
        
        vuln_list = []
        for v in sorted_vulns:
            vuln_list.append({
                "vulnerability_id": v.vulnerability_id,
                "severity": v.severity,
                "domain": v.domain,
                "title": v.title,
                "description": v.description,
                "attack_vector": v.attack_vector,
                "affected_components": v.affected_components,
            })
        
        max_patches = self.config.agents.defender.max_patches_per_iteration
        
        # Build priority guidance
        critical_count = sum(1 for v in sorted_vulns if v.severity == "CRITICAL")
        high_count = sum(1 for v in sorted_vulns if v.severity == "HIGH")
        
        priority_note = ""
        if critical_count > 0:
            priority_note = f"\n⚠️ PRIORITY: Address {critical_count} CRITICAL vulnerabilities first!"
        elif high_count > 0:
            priority_note = f"\n⚠️ PRIORITY: Address {high_count} HIGH severity vulnerabilities!"
        
        return f"""Apply patches to address the following vulnerabilities.

--- CURRENT DESIGN ---
{design_markdown}
--- END DESIGN ---

--- VULNERABILITIES TO ADDRESS (sorted by priority) ---
{vuln_list}
--- END VULNERABILITIES ---
{priority_note}

Rules:
1. Maximum {max_patches} patches allowed
2. Address vulnerabilities IN ORDER (CRITICAL first, then HIGH, etc.)
3. Each patch must target exactly one vulnerability
4. Apply MINIMAL fixes - no over-engineering

Respond with valid JSON containing:
1. A list of patches (max {max_patches})
2. The updated design markdown with fixes applied"""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.defender_seconds
