"""
Mermaid diagram generation for the AI Crucible.

Generates architecture diagrams from system designs.
"""

from typing import List, Optional
from crucible.state import CrucibleState, DesignComponent, Vulnerability


def generate_architecture_diagram(state: CrucibleState) -> str:
    """
    Generate a Mermaid architecture diagram from the current design.
    
    Returns a Mermaid diagram string.
    """
    lines = [
        "```mermaid",
        "graph TB",
        "    %% AI Crucible Architecture Diagram",
        "",
    ]
    
    # Add components as nodes
    for comp in state.design_components:
        node_id = f"C{comp.component_id}"
        # Escape quotes in names
        name = comp.name.replace('"', "'")
        lines.append(f'    {node_id}["{name}"]')
    
    lines.append("")
    
    # Add dependencies as edges
    for comp in state.design_components:
        node_id = f"C{comp.component_id}"
        for dep_id in comp.dependencies:
            dep_node_id = f"C{dep_id}"
            lines.append(f"    {dep_node_id} --> {node_id}")
    
    # Style vulnerable components
    patched_ids = {p.target_vulnerability_id for p in state.patches}
    vulnerable_component_ids = set()
    
    for vuln in state.vulnerabilities:
        if vuln.vulnerability_id not in patched_ids:
            vulnerable_component_ids.update(vuln.affected_components)
    
    if vulnerable_component_ids:
        lines.append("")
        lines.append("    %% Styling for vulnerable components")
        for comp_id in vulnerable_component_ids:
            lines.append(f"    style C{comp_id} fill:#ff6b6b,stroke:#c92a2a")
    
    lines.append("```")
    
    return "\n".join(lines)


def generate_vulnerability_flow(state: CrucibleState) -> str:
    """
    Generate a Mermaid flowchart showing vulnerability lifecycle.
    
    Shows which vulnerabilities were found, patched, and remain.
    """
    lines = [
        "```mermaid",
        "flowchart LR",
        "    %% Vulnerability Lifecycle",
        "",
    ]
    
    patched_ids = {p.target_vulnerability_id for p in state.patches}
    
    # Group by iteration
    iterations = {}
    for vuln in state.vulnerabilities:
        iter_num = vuln.iteration_found
        if iter_num not in iterations:
            iterations[iter_num] = []
        iterations[iter_num].append(vuln)
    
    for iter_num, vulns in sorted(iterations.items()):
        lines.append(f"    subgraph Iteration_{iter_num}[\"Iteration {iter_num}\"]")
        
        for vuln in vulns:
            vid = f"V{vuln.vulnerability_id}"
            title = vuln.title[:30].replace('"', "'")
            status = "patched" if vuln.vulnerability_id in patched_ids else "unresolved"
            
            if status == "patched":
                lines.append(f'        {vid}["{title}..."]:::patched')
            else:
                lines.append(f'        {vid}["{title}..."]:::unresolved')
        
        lines.append("    end")
        lines.append("")
    
    # Add styling
    lines.append("    classDef patched fill:#51cf66,stroke:#2f9e44")
    lines.append("    classDef unresolved fill:#ff6b6b,stroke:#c92a2a")
    
    lines.append("```")
    
    return "\n".join(lines)


def generate_iteration_timeline(state: CrucibleState) -> str:
    """
    Generate a Mermaid timeline showing the adversarial iterations.
    """
    lines = [
        "```mermaid",
        "timeline",
        f"    title AI Crucible Run ({state.status})",
        "",
    ]
    
    # Initial design
    comp_count = len(state.design_components)
    lines.append(f"    section Design")
    lines.append(f"        Architect : {comp_count} components")
    
    # Each iteration
    for summary in state.iteration_summaries:
        vuln_count = len(summary.vulnerabilities_reported)
        patch_count = len(summary.patches_applied)
        lines.append(f"    section Iteration {summary.iteration_id}")
        lines.append(f"        Attack : {vuln_count} vulnerabilities")
        lines.append(f"        Defend : {patch_count} patches")
    
    # Final status
    lines.append(f"    section Result")
    lines.append(f"        {state.status} : {state.termination_reason or 'Complete'}")
    
    lines.append("```")
    
    return "\n".join(lines)


def generate_all_diagrams(state: CrucibleState) -> str:
    """Generate all diagrams as a markdown document."""
    sections = [
        "## Architecture Diagram",
        "",
        generate_architecture_diagram(state),
        "",
        "## Vulnerability Lifecycle",
        "",
        generate_vulnerability_flow(state),
        "",
        "## Iteration Timeline", 
        "",
        generate_iteration_timeline(state),
    ]
    
    return "\n".join(sections)
