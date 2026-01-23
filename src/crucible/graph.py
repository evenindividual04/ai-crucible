"""
LangGraph orchestration for the AI Crucible.

Implements the state machine defined in graph-logic.md.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Literal
import logging

from langgraph.graph import StateGraph, END
from pydantic import BaseModel

from crucible.config import get_config, CrucibleConfig
from crucible.state import (
    CrucibleState,
    DesignComponent,
    Vulnerability,
    Patch,
    IterationSummary,
)
from crucible.agents import (
    ArchitectAgent,
    SecurityHawk,
    ScaleMonster,
    CostAnalyst,
    LogicBreaker,
    DefenderAgent,
    ComplianceAgent,
    UXAdversary,
    ChaosEngineer,
)
from crucible.agents.base import AgentError, AgentTimeoutError, AgentSchemaError
from crucible.router import route_agents
from crucible.judge import JudgeController

logger = logging.getLogger(__name__)


# Agent registry
RED_TEAM_AGENTS = {
    "SecurityHawk": SecurityHawk,
    "ScaleMonster": ScaleMonster,
    "CostAnalyst": CostAnalyst,
    "LogicBreaker": LogicBreaker,
    "ComplianceAgent": ComplianceAgent,
    "UXAdversary": UXAdversary,
    "ChaosEngineer": ChaosEngineer,
}


def architect_node(state: CrucibleState) -> Dict[str, Any]:
    """Generate initial design from user prompt."""
    logger.info("Architect generating design...")
    
    state.status = "ARCHITECTING"
    state.touch()
    
    try:
        agent = ArchitectAgent()
        output = agent.invoke(user_prompt=state.user_prompt)
        
        # Assign component IDs
        components = []
        for comp_data in output.components:
            comp = DesignComponent(
                component_id=state.allocate_component_id(),
                name=comp_data.name,
                responsibility=comp_data.responsibility,
                assumptions=comp_data.assumptions,
                dependencies=comp_data.dependencies,
            )
            components.append(comp)
        
        return {
            "design_markdown": output.design_markdown,
            "design_components": components,
            "status": "ROUTING",
        }
        
    except AgentTimeoutError as e:
        logger.error(f"Architect timeout: {e}")
        return {
            "status": "FAILED",
            "error_code": "FAILED_ARCHITECT_TIMEOUT",
            "termination_reason": str(e),
        }
    except AgentSchemaError as e:
        logger.error(f"Architect schema error: {e}")
        return {
            "status": "FAILED",
            "error_code": "FAILED_SCHEMA_VIOLATION",
            "termination_reason": str(e),
        }
    except Exception as e:
        logger.error(f"Architect error: {e}")
        return {
            "status": "FAILED",
            "error_code": "FAILED_ARCHITECT_ERROR",
            "termination_reason": str(e),
        }


def router_node(state: CrucibleState) -> Dict[str, Any]:
    """Route to appropriate Red Team agents."""
    logger.info("Routing to Red Team agents...")
    
    agents = route_agents(state)
    logger.info(f"Activated agents: {agents}")
    
    return {
        "active_agents": agents,
        "status": "UNDER_ATTACK",
    }


def validate_design_node(state: CrucibleState) -> Dict[str, Any]:
    """Judge validates the design."""
    logger.info("Judge validating design...")
    
    judge = JudgeController()
    is_valid, reason = judge.validate_design(state)
    
    if not is_valid:
        logger.error(f"Design validation failed: {reason}")
        return {
            "status": "FAILED",
            "error_code": reason.split(":")[0] if ":" in reason else "FAILED_INVALID_DESIGN",
            "termination_reason": reason,
        }
    
    return {}


async def _run_single_red_team_agent(
    agent_name: str,
    design_markdown: str,
    components: list,
    iteration: int
) -> tuple[str, list, str | None]:
    """Run a single Red Team agent asynchronously."""
    agent_class = RED_TEAM_AGENTS.get(agent_name)
    if not agent_class:
        return agent_name, [], f"Unknown agent: {agent_name}"
    
    try:
        agent = agent_class()
        output = await agent.invoke_async(
            design_markdown=design_markdown,
            components=components,
            iteration=iteration,
        )
        return agent_name, output.vulnerabilities, None
    except AgentTimeoutError as e:
        return agent_name, [], f"Timeout: {e}"
    except AgentSchemaError as e:
        return agent_name, [], f"Schema error: {e}"
    except Exception as e:
        return agent_name, [], f"Error: {e}"


def red_team_node(state: CrucibleState) -> Dict[str, Any]:
    """Red Team attacks the design (parallel or sequential based on config)."""
    config = get_config()
    logger.info(f"Red Team attacking with agents: {state.active_agents}")
    
    # Check if sequential mode is enabled
    sequential = config.sequential_mode
    
    if sequential:
        # Run agents one-by-one with delay to avoid rate limits
        async def run_agents_sequentially():
            results = []
            for agent_name in state.active_agents:
                result = await _run_single_red_team_agent(
                    agent_name,
                    state.design_markdown,
                    state.design_components,
                    state.iteration_count,
                )
                results.append(result)
                # Small delay between agents to avoid rate limits
                await asyncio.sleep(1.0)
            return results
        
        results = asyncio.run(run_agents_sequentially())
    else:
        # Run all agents in parallel (default)
        async def run_all_agents():
            tasks = [
                _run_single_red_team_agent(
                    agent_name,
                    state.design_markdown,
                    state.design_components,
                    state.iteration_count,
                )
                for agent_name in state.active_agents
            ]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(run_all_agents())
    
    all_vulns: List[Vulnerability] = []
    
    for agent_name, vuln_list, error in results:
        if error:
            logger.warning(f"{agent_name}: {error}")
            continue
        
        # Get agent domain
        agent_class = RED_TEAM_AGENTS.get(agent_name)
        domain = agent_class.domain if agent_class else "LOGIC"
        
        # Convert to Vulnerability objects
        for vuln_data in vuln_list:
            vuln = Vulnerability(
                vulnerability_id=state.allocate_vulnerability_id(),
                severity=vuln_data.get("severity", "MEDIUM"),
                confidence=vuln_data.get("confidence", 0.5),
                domain=domain,
                title=vuln_data.get("title", "Unknown"),
                description=vuln_data.get("description", ""),
                attack_vector=vuln_data.get("attack_vector", ""),
                affected_components=vuln_data.get("affected_components", []),
                iteration_found=state.iteration_count,
            )
            all_vulns.append(vuln)
    
    if not all_vulns:
        logger.warning("No vulnerabilities found by any agent")
    
    # Filter and evaluate with Judge
    judge = JudgeController()
    novel_vulns, decision = judge.evaluate_attacks(state, all_vulns)
    
    # Update state with novel vulnerabilities
    active_vuln_ids = [v.vulnerability_id for v in novel_vulns]
    
    return {
        "vulnerabilities": state.vulnerabilities + novel_vulns,
        "active_vulnerabilities": active_vuln_ids,
        "status": "PATCHING" if decision.decision == "CONTINUE_TO_DEFEND" else "EVALUATING",
    }



def defender_node(state: CrucibleState) -> Dict[str, Any]:
    """Defender patches vulnerabilities."""
    logger.info("Defender generating patches...")
    
    active_vulns = state.get_active_vulnerabilities()
    
    if not active_vulns:
        logger.warning("No active vulnerabilities to patch")
        return {"status": "EVALUATING"}
    
    try:
        agent = DefenderAgent()
        output = agent.invoke(
            design_markdown=state.design_markdown,
            components=state.design_components,
            vulnerabilities=active_vulns,
        )
        
        # Convert to Patch objects
        patches: List[Patch] = []
        max_patches = agent.config.agents.defender.max_patches_per_iteration
        
        for i, patch_data in enumerate(output.patches[:max_patches]):
            patch = Patch(
                patch_id=state.allocate_patch_id(),
                target_vulnerability_id=patch_data.get("target_vulnerability_id", 0),
                fix_description=patch_data.get("fix_description", ""),
                design_changes=patch_data.get("design_changes", []),
                introduces_new_assumptions=patch_data.get("introduces_new_assumptions", False),
            )
            patches.append(patch)
        
        # Verify patches
        judge = JudgeController()
        is_valid, reason = judge.verify_patches(
            state,
            state.design_markdown,
            output.updated_design_markdown,
            patches,
        )
        
        if not is_valid:
            logger.error(f"Patch verification failed: {reason}")
            return {
                "status": "FAILED",
                "error_code": reason.split(":")[0] if ":" in reason else "FAILED_REGRESSION",
                "termination_reason": reason,
            }
        
        # Create iteration summary
        summary = IterationSummary(
            iteration_id=state.iteration_count,
            vulnerabilities_reported=[v.vulnerability_id for v in active_vulns],
            patches_applied=[p.patch_id for p in patches],
            critical_remaining=state.get_unpatched_critical_count(),
        )
        
        return {
            "design_markdown": output.updated_design_markdown,
            "patches": state.patches + patches,
            "iteration_summaries": state.iteration_summaries + [summary],
            "iteration_count": state.iteration_count + 1,
            "status": "EVALUATING",
        }
        
    except AgentTimeoutError as e:
        logger.warning(f"Defender timed out: {e}")
        return {"status": "EVALUATING"}
    except AgentSchemaError as e:
        logger.warning(f"Defender schema error: {e}")
        return {"status": "EVALUATING"}
    except Exception as e:
        logger.error(f"Defender error: {e}")
        return {"status": "EVALUATING"}


def evaluate_node(state: CrucibleState) -> Dict[str, Any]:
    """Judge evaluates and decides termination."""
    logger.info("Judge evaluating iteration...")
    
    judge = JudgeController()
    decision = judge.decide_termination(state)
    
    if decision.decision == "TERMINATE_STABLE":
        return {
            "status": "STABLE",
            "termination_reason": decision.reason,
        }
    elif decision.decision == "TERMINATE_UNRESOLVED":
        return {
            "status": "UNRESOLVED",
            "termination_reason": decision.reason,
        }
    elif decision.decision == "TERMINATE_FAILED":
        return {
            "status": "FAILED",
            "termination_reason": decision.reason,
        }
    else:
        # Continue to next iteration
        return {"status": "ROUTING"}


def should_continue(state: CrucibleState) -> Literal["continue", "end"]:
    """Determine if the loop should continue."""
    if state.status in ("STABLE", "UNRESOLVED", "FAILED"):
        return "end"
    return "continue"


def route_after_validate(state: CrucibleState) -> Literal["router", "end"]:
    """Route after design validation."""
    if state.status == "FAILED":
        return "end"
    return "router"


def route_after_attack(state: CrucibleState) -> Literal["defender", "evaluate"]:
    """Route after Red Team attack."""
    if state.status == "PATCHING":
        return "defender"
    return "evaluate"


def route_after_evaluate(state: CrucibleState) -> Literal["router", "end"]:
    """Route after evaluation."""
    if state.status in ("STABLE", "UNRESOLVED", "FAILED"):
        return "end"
    return "router"


def create_crucible_graph() -> StateGraph:
    """Create the LangGraph state machine for the Crucible."""
    
    # Create the graph with CrucibleState as the state type
    graph = StateGraph(CrucibleState)
    
    # Add nodes
    graph.add_node("architect", architect_node)
    graph.add_node("validate_design", validate_design_node)
    graph.add_node("router", router_node)
    graph.add_node("red_team", red_team_node)
    graph.add_node("defender", defender_node)
    graph.add_node("evaluate", evaluate_node)
    
    # Set entry point
    graph.set_entry_point("architect")
    
    # Add edges with explicit path mapping
    graph.add_edge("architect", "validate_design")
    
    # After validate_design: go to router if valid, END if failed
    graph.add_conditional_edges(
        "validate_design",
        route_after_validate,
        {"router": "router", "end": END}
    )
    
    graph.add_edge("router", "red_team")
    
    # After red_team: go to defender or evaluate
    graph.add_conditional_edges(
        "red_team",
        route_after_attack,
        {"defender": "defender", "evaluate": "evaluate"}
    )
    
    graph.add_edge("defender", "evaluate")
    
    # After evaluate: continue to router or END
    graph.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {"router": "router", "end": END}
    )
    
    return graph


def build_crucible():
    """Build and compile the Crucible graph."""
    graph = create_crucible_graph()
    return graph.compile()


async def run_crucible_async(user_prompt: str, config: CrucibleConfig | None = None) -> CrucibleState:
    """Run the Crucible asynchronously."""
    config = config or get_config()
    
    # Initialize state
    initial_state = CrucibleState(
        user_prompt=user_prompt,
        max_iterations=config.max_iterations,
    )
    
    # Build and run the graph
    app = build_crucible()
    
    # Run the graph
    final_state = None
    async for state in app.astream(initial_state):
        # Get the latest state from the stream
        for node_name, node_state in state.items():
            if isinstance(node_state, dict):
                # Merge updates into state
                for key, value in node_state.items():
                    setattr(initial_state, key, value)
            final_state = initial_state
    
    return final_state or initial_state


def run_crucible(user_prompt: str, config: CrucibleConfig | None = None) -> CrucibleState:
    """Run the Crucible synchronously."""
    return asyncio.run(run_crucible_async(user_prompt, config))
