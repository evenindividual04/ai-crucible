"""
Chaos Engineer Agent for the AI Crucible.

Breaks the system through partial failures and cascade effects.
"""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from crucible.agents.base import BaseAgent


class ChaosVulnerabilityData(BaseModel):
    """Extended vulnerability data for chaos/reliability issues."""
    
    severity: str
    confidence: float
    title: str
    description: str
    attack_vector: str
    affected_components: List[int]
    failure_injection_point: str
    cascade_effect: str
    blast_radius: Literal["COMPONENT", "SERVICE", "SYSTEM"]


class ChaosEngineerOutput(BaseModel):
    """Output schema for the Chaos Engineer Agent."""
    
    vulnerabilities: List[dict] = Field(
        description="List of reliability vulnerabilities found"
    )


class ChaosEngineer(BaseAgent[ChaosEngineerOutput]):
    """
    Breaks the system through partial failures and cascade effects.
    
    Coverage:
    - Network partitions
    - Dependency failures
    - Clock skew / time-based bugs
    - Partial writes / incomplete state
    - Graceful degradation gaps
    """
    
    name = "Chaos Engineer"
    domain = "RELIABILITY"
    
    activation_keywords = [
        "distributed", "microservice", "api", "database", "queue", "cache",
        "timeout", "retry", "partition", "replica", "cluster", "failover",
        "async", "eventual", "consistency", "transaction"
    ]
    
    def get_default_prompt(self) -> str:
        return """You are the Chaos Engineer in an adversarial system design review.

Your SOLE PURPOSE is to find RELIABILITY failures through chaos injection.

## Failure Injection Points

1. **Network Failures**
   - Network partitions between services
   - DNS resolution failures
   - Load balancer failures
   - SSL/TLS certificate issues

2. **Dependency Failures**
   - Database unavailable
   - Cache down (Redis, Memcached)
   - External API timeouts
   - Message queue backpressure

3. **Time-Based Issues**
   - Clock skew between nodes
   - Timezone handling errors
   - DST transition bugs
   - Token expiration races

4. **Partial Failures**
   - Partial writes to database
   - Incomplete transaction rollbacks
   - Split brain scenarios
   - Retry-induced duplicates

5. **Resource Exhaustion**
   - Connection pool exhaustion
   - Memory pressure
   - Disk full scenarios
   - File descriptor limits

## Blast Radius Levels

- **COMPONENT**: Only one component affected
- **SERVICE**: Multiple components in one service affected
- **SYSTEM**: Cascading failure across the entire system

## Output Format

```json
{
  "vulnerabilities": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "confidence": 0.0-1.0,
      "title": "Brief failure scenario title",
      "description": "What fails and how it cascades",
      "attack_vector": "How to inject this failure",
      "affected_components": [1, 2, 3],
      "failure_injection_point": "Redis connection pool",
      "cascade_effect": "All user sessions become invalid",
      "blast_radius": "COMPONENT|SERVICE|SYSTEM"
    }
  ]
}
```

Think like a chaos monkey. What would Netflix break?"""
    
    def get_output_schema(self) -> type[ChaosEngineerOutput]:
        return ChaosEngineerOutput
    
    def build_user_message(
        self,
        design_markdown: str,
        components: List[Any],
        iteration: int,
        **kwargs: Any
    ) -> str:
        comp_list = [{"id": c.component_id, "name": c.name, "responsibility": c.responsibility}
                     for c in components]
        
        return f"""Analyze this system design for RELIABILITY and CHAOS issues.

--- DESIGN ---
{design_markdown}
--- END DESIGN ---

Components: {comp_list}

Inject failures at:
1. Network partitions between components
2. Database and cache unavailability
3. Partial writes and incomplete states
4. Resource exhaustion scenarios
5. Time-based edge cases

Respond with valid JSON containing found reliability vulnerabilities."""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.red_team_seconds
