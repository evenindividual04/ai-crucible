"""
Pydantic models for the AI Crucible state management.

This module defines the core data structures used throughout the system,
following the schema defined in state-schema.md.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from crucible.token_tracker import TokenBudget


class ScenarioPackRef(BaseModel):
    """Reference to a scenario pack and specific case within it."""
    
    pack_id: str
    case_id: str
    version: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class AttackChainStep(BaseModel):
    """Represents one step in an attack chain (prerequisite fulfilled)."""
    
    vulnerability_id: int
    step_number: int
    description: str
    attack_progression: str  # How this step enables the next
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)  # Vulnerability's confidence


class AttackChain(BaseModel):
    """Composed attack sequence from multiple vulnerabilities."""
    
    chain_id: int
    steps: List[AttackChainStep] = Field(default_factory=list)
    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    affected_components: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DesignComponent(BaseModel):
    """Represents a machine-readable unit of the proposed system."""
    
    component_id: int
    name: str
    responsibility: str
    assumptions: List[str] = Field(default_factory=list)
    dependencies: List[int] = Field(default_factory=list)  # Component IDs


class Vulnerability(BaseModel):
    """Generated exclusively by Red Team agents."""
    
    vulnerability_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    confidence: float = Field(ge=0.0, le=1.0)
    domain: Literal["SECURITY", "SCALABILITY", "COST", "LOGIC", "RELIABILITY", "REGULATORY", "USABILITY"]
    title: str
    description: str
    attack_vector: str
    affected_components: List[int] = Field(default_factory=list)
    iteration_found: int
    agent_name: Optional[str] = None  # Which red team agent found this

    @property
    def confidence_score(self) -> float:
        """Alias for confidence (backward compatibility)."""
        return self.confidence
    
    @property
    def is_patched(self) -> bool:
        """Check if this vulnerability has been patched. Set externally."""
        return getattr(self, '_is_patched', False)


from crucible.patches_v2 import PatchV2 as Patch


class IterationSummary(BaseModel):
    """Captures the outcome of a single adversarial round."""
    
    iteration_id: int
    vulnerabilities_reported: List[int] = Field(default_factory=list)
    patches_applied: List[int] = Field(default_factory=list)
    critical_remaining: int = 0
    notes: Optional[str] = None


class CrucibleState(BaseModel):
    """
    The single source of truth for all data flowing through the system.

    This is the main state object passed through the LangGraph nodes.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Schema Version (for future migrations)
    schema_version: int = 1
    
    # User Input
    user_prompt: str
    
    # Scenario Pack Reference (optional)
    scenario_pack_ref: Optional[ScenarioPackRef] = None
    
    # Design Representation
    design_markdown: str = ""  # Human-readable
    design_components: List[DesignComponent] = Field(default_factory=list)
    
    # Iteration Tracking
    iteration_count: int = 0
    max_iterations: int = 3
    
    # Active Defender Mode
    defender_mode: Literal["QUICK_FIX", "ARCHITECT", "COORDINATE"] = "QUICK_FIX"
    
    # ID Allocation (managed by orchestrator)
    next_component_id: int = 1
    next_vulnerability_id: int = 1
    next_patch_id: int = 1
    
    # Conflict History (Append-only)
    vulnerabilities: List[Vulnerability] = Field(default_factory=list)
    patches: List[Patch] = Field(default_factory=list)
    attack_chains: List[AttackChain] = Field(default_factory=list)  # Composed vulnerability chains
    iteration_summaries: List[IterationSummary] = Field(default_factory=list)
    
    # Active vulnerabilities for current iteration (working set)
    active_vulnerabilities: List[int] = Field(default_factory=list)
    
    # Agents activated for this run
    active_agents: List[str] = Field(default_factory=list)
    
    # Meta State
    status: Literal[
        "INIT",
        "ARCHITECTING",
        "ROUTING",
        "UNDER_ATTACK",
        "PATCHING",
        "EVALUATING",
        "STABLE",
        "UNRESOLVED",
        "FAILED"
    ] = "INIT"
    
    termination_reason: Optional[str] = None
    error_code: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # NEW: Token Budget Tracking
    token_budget: Optional[TokenBudget] = None
    
    # NEW: Checkpoint/Resume Metadata
    run_id: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    checkpoint_enabled: bool = True
    
    # NEW: Deduplication Tracking
    duplicate_count: int = 0
    merged_vulnerabilities: List[dict] = Field(default_factory=list)
    
    # NEW: Validation Tracking
    rejected_patch_count: int = 0
    validation_warnings: List[str] = Field(default_factory=list)
    
    # NEW: Security Metrics
    security_scores: List[dict] = Field(default_factory=list)  # List of SecurityScore.to_dict()
    current_security_score: Optional[dict] = None  # Latest SecurityScore.to_dict()

    # NEW: V2 Analytics
    attack_effectiveness: List[dict] = Field(default_factory=list)  # per-agent effectiveness metrics
    defense_quality: Optional[dict] = None
    convergence_metrics: Optional[dict] = None
    
    def allocate_component_id(self) -> int:
        """Allocate a new unique component ID."""
        cid = self.next_component_id
        self.next_component_id += 1
        return cid
    
    def allocate_vulnerability_id(self) -> int:
        """Allocate a new unique vulnerability ID."""
        vid = self.next_vulnerability_id
        self.next_vulnerability_id += 1
        return vid
    
    def allocate_patch_id(self) -> int:
        """Allocate a new unique patch ID."""
        pid = self.next_patch_id
        self.next_patch_id += 1
        return pid
    
    def get_vulnerability_by_id(self, vid: int) -> Optional[Vulnerability]:
        """Get a vulnerability by its ID."""
        for v in self.vulnerabilities:
            if v.vulnerability_id == vid:
                return v
        return None
    
    def get_active_vulnerabilities(self) -> List[Vulnerability]:
        """Get the list of currently active vulnerabilities."""
        return [v for v in self.vulnerabilities if v.vulnerability_id in self.active_vulnerabilities]
    
    def get_unpatched_critical_count(self) -> int:
        """Count CRITICAL vulnerabilities without a full (non-incremental) patch."""
        from crucible.patches_v2 import IncrementalPatch as IncPatch
        fully_patched_ids = {
            p.target_vulnerability_id for p in self.patches
            if not (isinstance(p, IncPatch) and not p.full_fix)
        }
        return sum(
            1 for v in self.vulnerabilities
            if v.severity == "CRITICAL" and v.vulnerability_id not in fully_patched_ids
        )
    
    def touch(self) -> None:
        """Update the last_modified_at timestamp."""
        self.last_modified_at = datetime.now(timezone.utc)


# Type aliases for clarity
Status = Literal[
    "INIT", "ARCHITECTING", "ROUTING", "UNDER_ATTACK", 
    "PATCHING", "EVALUATING", "STABLE", "UNRESOLVED", "FAILED"
]
Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
Domain = Literal["SECURITY", "SCALABILITY", "COST", "LOGIC", "RELIABILITY", "REGULATORY", "USABILITY"]
