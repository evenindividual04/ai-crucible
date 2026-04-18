"""
Attack chain synthesis module.

Composes discovered vulnerabilities into attack chains that show how multiple
vulnerabilities can be exploited in sequence to escalate impact.
"""

from typing import List, Optional
from datetime import datetime, timezone

from crucible.state import (
    AttackChain,
    AttackChainStep,
    Vulnerability,
    DesignComponent,
    CrucibleState,
)


def _build_chain_from_start_vuln(
    start_vuln: Vulnerability,
    domain_vulns: List[Vulnerability],
    vulnerabilities: List[Vulnerability],
    design_components: List[DesignComponent],
    max_chain_length: int = 5,
) -> Optional[AttackChain]:
    """
    Build a single chain starting from start_vuln within a domain.
    
    Returns None if chain has fewer than 2 steps.
    """
    chain_steps: List[AttackChainStep] = []
    used_ids = set()
    
    # First step
    first_narrative = _synthesize_narrative(start_vuln, None, design_components)
    chain_steps.append(
        AttackChainStep(
            vulnerability_id=start_vuln.vulnerability_id,
            step_number=1,
            description=first_narrative,
            attack_progression=start_vuln.attack_vector,
            confidence=start_vuln.confidence,
        )
    )
    used_ids.add(start_vuln.vulnerability_id)
    
    # Chain subsequent vulnerabilities
    current_affected = set(start_vuln.affected_components)
    last_vuln = start_vuln
    
    for next_vuln in domain_vulns:
        if next_vuln.vulnerability_id in used_ids or len(chain_steps) >= max_chain_length:
            continue
        
        # Check prerequisites: shared components AND temporal order
        next_affected = set(next_vuln.affected_components)
        shared_comps = len(current_affected & next_affected) > 0
        temporal_order = next_vuln.iteration_found >= last_vuln.iteration_found
        
        if shared_comps and temporal_order:
            # Add to chain
            next_narrative = _synthesize_narrative(next_vuln, last_vuln, design_components)
            chain_steps.append(
                AttackChainStep(
                    vulnerability_id=next_vuln.vulnerability_id,
                    step_number=len(chain_steps) + 1,
                    description=next_narrative,
                    attack_progression=next_vuln.attack_vector,
                    confidence=next_vuln.confidence,
                )
            )
            used_ids.add(next_vuln.vulnerability_id)
            current_affected.update(next_affected)
            last_vuln = next_vuln
    
    if len(chain_steps) < 2:
        return None  # Not a valid chain
    
    # Create chain
    confidence = _compute_mean_confidence(chain_steps, vulnerabilities)
    severity = _compute_max_severity(chain_steps, vulnerabilities)
    
    affected_comps = set()
    for step in chain_steps:
        vuln = next((v for v in vulnerabilities if v.vulnerability_id == step.vulnerability_id), None)
        if vuln:
            affected_comps.update(vuln.affected_components)
    
    chain_title = _synthesize_chain_title(chain_steps, vulnerabilities)
    chain_description = _synthesize_chain_description(chain_steps, vulnerabilities, design_components)
    
    return AttackChain(
        chain_id=0,  # Will be assigned by state integration
        steps=chain_steps,
        title=chain_title,
        description=chain_description,
        confidence=confidence,
        severity=severity,
        affected_components=list(affected_comps),
        created_at=datetime.now(timezone.utc),
    )


def _generate_chains_from_vulnerabilities(
    vulnerabilities: List[Vulnerability],
    design_components: List[DesignComponent],
    max_chain_length: int = 5,
) -> List[AttackChain]:
    """
    Generate attack chains from discovered vulnerabilities.
    
    Returns empty list if fewer than 2 vulnerabilities.
    Chains only form within the same domain (SECURITY, COST, etc.).
    
    Args:
        vulnerabilities: All discovered vulnerabilities
        design_components: System design structure
        max_chain_length: Maximum steps in a chain
    
    Returns:
        List of AttackChain objects (empty if no valid chains)
    """
    if len(vulnerabilities) < 2:
        return []
    
    # Group vulnerabilities by domain
    domain_groups = {}
    for vuln in vulnerabilities:
        domain_groups.setdefault(vuln.domain, []).append(vuln)
    
    chains = []
    chain_id = 1
    
    # Process each domain group separately
    for domain, domain_vulns in domain_groups.items():
        if len(domain_vulns) < 2:
            continue  # Can't chain without >= 2 vulns per domain
        
        # Try to build chains starting from each vulnerability
        for start_vuln in domain_vulns:
            chain = _build_chain_from_start_vuln(
                start_vuln,
                domain_vulns,
                vulnerabilities,
                design_components,
                max_chain_length,
            )
            if chain:
                chain.chain_id = chain_id
                chains.append(chain)
                chain_id += 1
    
    return chains


def _extract_step_confidences(
    chain_steps: List[AttackChainStep],
    vulnerabilities: List[Vulnerability],
) -> List[float]:
    """
    Extract confidence scores from vulnerabilities referenced by chain steps.
    
    Args:
        chain_steps: The chain steps
        vulnerabilities: All vulnerabilities (for lookup)
    
    Returns:
        List of confidence scores corresponding to each step
    """
    confidences = []
    for step in chain_steps:
        vuln = next(
            (v for v in vulnerabilities if v.vulnerability_id == step.vulnerability_id),
            None
        )
        if vuln:
            confidences.append(vuln.confidence)
    return confidences


def _compute_mean_confidence(
    chain_steps: List[AttackChainStep],
    vulnerabilities: List[Vulnerability],
) -> float:
    """Compute mean confidence across chain steps."""
    confidences = _extract_step_confidences(chain_steps, vulnerabilities)
    if not confidences:
        return 0.5
    
    mean = sum(confidences) / len(confidences)
    return min(1.0, max(0.0, mean))


def _compute_min_confidence(
    chain_steps: List[AttackChainStep],
    vulnerabilities: List[Vulnerability],
) -> float:
    """Compute minimum (worst-case) confidence across chain steps."""
    confidences = _extract_step_confidences(chain_steps, vulnerabilities)
    if not confidences:
        return 0.5
    
    return min(confidences)


def _compute_chain_confidence(
    chain: AttackChain,
    strategy: str = "mean",
) -> float:
    """
    Compute confidence score for an attack chain.
    
    Args:
        chain: The attack chain
        strategy: "mean" or "min" confidence computation
    
    Returns:
        Float in [0.0, 1.0] representing chain confidence
    """
    if not chain.steps:
        raise ValueError("Chain must have at least one step")
    
    # For a single-step chain, just return chain's confidence
    if len(chain.steps) == 1:
        return chain.confidence
    
    # Get confidence from steps, using chain's confidence as fallback if not set
    step_confidences = []
    for step in chain.steps:
        # If step confidence is still at default (0.5) and differs from chain's,
        # assume it wasn't explicitly set and use chain's confidence
        if step.confidence == 0.5 and chain.confidence != 0.5:
            step_confidences.append(chain.confidence)
        else:
            step_confidences.append(step.confidence)
    
    if strategy == "mean":
        # Average confidence of all steps
        mean = sum(step_confidences) / len(step_confidences)
        return min(1.0, max(0.0, mean))
    elif strategy == "min":
        # Minimum (worst-case) confidence of all steps
        return min(step_confidences) if step_confidences else 0.5
    else:
        # Default to mean
        mean = sum(step_confidences) / len(step_confidences)
        return min(1.0, max(0.0, mean))


def _compute_max_severity(
    chain_steps: List[AttackChainStep],
    vulnerabilities: List[Vulnerability],
) -> str:
    """Compute maximum severity across chain steps."""
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    
    max_severity = "LOW"
    max_level = 0
    
    for step in chain_steps:
        vuln = next(
            (v for v in vulnerabilities if v.vulnerability_id == step.vulnerability_id),
            None
        )
        if vuln and severity_order.get(vuln.severity, 0) > max_level:
            max_severity = vuln.severity
            max_level = severity_order.get(vuln.severity, 0)
    
    return max_severity


def _compute_escalation_severity(
    chain_steps: List[AttackChainStep],
    vulnerabilities: List[Vulnerability],
) -> str:
    """Compute escalation severity (multiple mitigations compound to CRITICAL)."""
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    
    total_score = 0
    for step in chain_steps:
        vuln = next(
            (v for v in vulnerabilities if v.vulnerability_id == step.vulnerability_id),
            None
        )
        if vuln:
            total_score += severity_order.get(vuln.severity, 0)
    
    # Escalation: if multiple vulnerabilities compound, severity rises
    if total_score >= 8:
        return "CRITICAL"
    elif total_score >= 6:
        return "HIGH"
    elif total_score >= 4:
        return "MEDIUM"
    else:
        return "LOW"


def _compute_chain_severity(
    chain: AttackChain,
    strategy: str = "max",
    vulnerabilities: List[Vulnerability] = None,
) -> str:
    """
    Compute severity for an attack chain.
    
    Args:
        chain: The attack chain
        strategy: "max" or "escalation" severity computation
        vulnerabilities: List of vulnerabilities (for strategy computation if needed)
    
    Returns:
        Severity string: CRITICAL, HIGH, MEDIUM, or LOW
    """
    if not chain.steps:
        raise ValueError("Chain must have at least one step")
    
    # If vulnerabilities provided, use them for dynamic computation
    if vulnerabilities and strategy != "max":
        if strategy == "escalation":
            return _compute_escalation_severity(chain.steps, vulnerabilities)
    
    # Default: return pre-computed severity (computed with max strategy)
    return chain.severity


def _validate_chain_no_circular_deps(chain: AttackChain) -> bool:
    """
    Validate that attack chain has no circular dependencies.
    
    Returns True if acyclic (valid), False if cyclic.
    Single-step chains are always valid.
    Empty chains raise ValueError.
    
    Args:
        chain: The attack chain to validate
    
    Returns:
        True if acyclic, False if cyclic
        
    Raises:
        ValueError: If chain has no steps
    """
    if len(chain.steps) == 0:
        raise ValueError("Chain must have at least one step")
    
    if len(chain.steps) == 1:
        return True
    
    # Check for cycles in step ordering (step_number should be sequential)
    step_numbers = [s.step_number for s in chain.steps]
    expected = list(range(1, len(chain.steps) + 1))
    
    if step_numbers == expected:
        return True
    
    # Check that vulnerability IDs don't repeat (which would indicate a cycle)
    vuln_ids = [s.vulnerability_id for s in chain.steps]
    if len(vuln_ids) != len(set(vuln_ids)):
        return False  # Cycle detected (repeated vulnerability)
    
    return True


def _synthesize_narrative(
    vulnerability: Vulnerability,
    prior_vulnerability: Optional[Vulnerability],
    design_components: List[DesignComponent],
) -> str:
    """
    Generate narrative text for a chain step.
    
    If prior_vulnerability is None, explains how attack gains foothold.
    If prior_vulnerability is set, explains how prior vuln enables this one.
    
    Args:
        vulnerability: The current vulnerability in the chain
        prior_vulnerability: The prerequisite vulnerability (if any)
        design_components: Design structure for context
    
    Returns:
        Non-empty string narrative for this chain step
    """
    comp_names = {c.component_id: c.name for c in design_components}
    
    affected_names = [
        comp_names.get(cid, f"Component {cid}")
        for cid in vulnerability.affected_components
    ]
    
    if prior_vulnerability is None:
        # Initial foothold
        narrative = (
            f"Attacker exploits {vulnerability.title} in "
            f"{', '.join(affected_names) if affected_names else 'system'}. "
            f"Attack vector: {vulnerability.attack_vector}"
        )
    else:
        # Chained exploitation
        prior_names = [
            comp_names.get(cid, f"Component {cid}")
            for cid in prior_vulnerability.affected_components
        ]
        narrative = (
            f"Using access gained from {prior_vulnerability.title}, "
            f"attacker now exploits {vulnerability.title} in "
            f"{', '.join(affected_names) if affected_names else 'system'}. "
            f"This enables: {vulnerability.attack_vector}"
        )
    
    return narrative


def _synthesize_chain_title(
    chain_steps: List[AttackChainStep],
    vulnerabilities: List[Vulnerability],
) -> str:
    """Generate a descriptive title for the attack chain."""
    if len(chain_steps) < 2:
        return "Single-step attack"
    
    first_vuln = next(
        (v for v in vulnerabilities if v.vulnerability_id == chain_steps[0].vulnerability_id),
        None
    )
    last_vuln = next(
        (v for v in vulnerabilities if v.vulnerability_id == chain_steps[-1].vulnerability_id),
        None
    )
    
    if first_vuln and last_vuln:
        return f"{len(chain_steps)}-step escalation: {first_vuln.title} → {last_vuln.title}"
    
    return f"{len(chain_steps)}-step attack chain"


def _synthesize_chain_description(
    chain_steps: List[AttackChainStep],
    vulnerabilities: List[Vulnerability],
    design_components: List[DesignComponent],
) -> str:
    """Generate a detailed description of the attack chain."""
    descriptions = []
    
    for i, step in enumerate(chain_steps):
        vuln = next(
            (v for v in vulnerabilities if v.vulnerability_id == step.vulnerability_id),
            None
        )
        if vuln:
            prior = None
            if i > 0:
                prior_step = chain_steps[i - 1]
                prior = next(
                    (v for v in vulnerabilities if v.vulnerability_id == prior_step.vulnerability_id),
                    None
                )
            
            narrative = _synthesize_narrative(vuln, prior, design_components)
            descriptions.append(f"Step {i + 1}: {narrative}")
    
    return "\n".join(descriptions)


def _insert_chains_into_state(
    state: CrucibleState,
    chains: List[AttackChain],
) -> CrucibleState:
    """
    Insert generated chains into CrucibleState immutably.
    
    Creates a new state object with chains added rather than mutating input.
    Allocates unique chain_ids if needed.
    
    Args:
        state: The current CrucibleState
        chains: List of AttackChain objects to insert
    
    Returns:
        New CrucibleState with chains added
    """
    # Allocate unique chain IDs
    next_chain_id = max(
        (c.chain_id for c in state.attack_chains),
        default=0
    ) + 1
    
    updated_chains = list(state.attack_chains)
    
    for chain in chains:
        if chain.chain_id == 0 or chain.chain_id is None:
            chain.chain_id = next_chain_id
            next_chain_id += 1
        
        updated_chains.append(chain)
    
    # Immutable update using model_copy()
    return state.model_copy(update={
        "attack_chains": updated_chains,
        "last_modified_at": datetime.now(timezone.utc),
    })
