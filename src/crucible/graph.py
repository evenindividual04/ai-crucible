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
from crucible.eval.schemas import AgentType
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
from crucible.token_tracker import TokenUsage, get_parallelism_recommendation
from crucible.deduplication import VulnerabilityDeduplicator
from crucible.validation import PatchValidator

logger = logging.getLogger(__name__)

# Global display object for streaming output
_display = None

# Global tracer for evaluation
_tracer = None

def set_display(display):
    """Set the global display object for streaming output."""
    global _display
    _display = display

def get_display():
    """Get the global display object."""
    return _display


def register_tracer(tracer):
    """Register a tracer for instrumentation."""
    global _tracer
    _tracer = tracer


def get_tracer():
    """Get the registered tracer, if any."""
    return _tracer


def _resolve_agent_type(agent_name: str) -> AgentType:
    """Map an agent name to a trace agent type."""
    return {
        "Architect": AgentType.ARCHITECT,
        "SecurityHawk": AgentType.SECURITY_HAWK,
        "ScaleMonster": AgentType.SCALE_MONSTER,
        "CostAnalyst": AgentType.COST_ANALYST,
        "LogicBreaker": AgentType.LOGIC_BREAKER,
        "ComplianceAgent": AgentType.COMPLIANCE,
        "UXAdversary": AgentType.UX_ADVERSARY,
        "ChaosEngineer": AgentType.CHAOS_ENGINEER,
        "Defender": AgentType.DEFENDER,
        "QuickFixer": AgentType.DEFENDER,
        "ArchitectRefactorer": AgentType.DEFENDER,
        "DefenseCoordinator": AgentType.DEFENDER,
    }.get(agent_name, AgentType.DEFENDER)


def _trace_iteration_start(state: CrucibleState) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.iteration_start(state)


def _trace_iteration_end(state: CrucibleState) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.iteration_end(state)


def _trace_agent_invoke(
    agent_type: AgentType | str,
    agent_name: str,
    input_prompt: str | None = None,
) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.agent_invoke(agent_type, agent_name, input_prompt=input_prompt)


def _trace_agent_complete(
    agent_type: AgentType | str,
    agent_name: str,
    *,
    success: bool = True,
    vulnerabilities_found: int = 0,
    tokens_used: int = 0,
    duration_ms: float | None = None,
    error_message: str | None = None,
) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.agent_complete(
            agent_type=agent_type,
            agent_name=agent_name,
            success=success,
            vulnerabilities_found=vulnerabilities_found,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            error_message=error_message,
        )


def _trace_design_validated(is_valid: bool, reason: str | None, components_count: int) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.design_validated(
            is_valid=is_valid,
            reason=reason,
            components_count=components_count,
        )


def _trace_vulnerability_found(vuln: Vulnerability) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.vulnerability_found(
            vulnerability_id=vuln.vulnerability_id,
            title=vuln.title,
            severity=vuln.severity,
            domain=vuln.domain,
            confidence=vuln.confidence,
            agent_type=_resolve_agent_type(vuln.agent_name or "Defender"),
        )


def _trace_vulnerability_duplicate(
    new_vuln: Vulnerability,
    original_vuln: Vulnerability,
    similarity_score: float,
) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.vulnerability_duplicate(
            vulnerability_id=new_vuln.vulnerability_id,
            original_id=original_vuln.vulnerability_id,
            similarity_score=similarity_score,
        )


def _trace_patch_applied(patch: Patch) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.patch_applied(
            patch_id=patch.patch_id,
            target_vulnerability_id=patch.target_vulnerability_id,
            validated=True,
            introduces_new_assumptions=patch.introduces_new_assumptions,
        )


def _trace_patch_rejected(patch: Patch, rejection_reason: str) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.patch_rejected(
            patch_id=patch.patch_id,
            target_vulnerability_id=patch.target_vulnerability_id,
            rejection_reason=rejection_reason,
        )


def _trace_judge_decision(decision, vulnerabilities_count: int, patches_count: int, security_score: float) -> None:
    tracer = get_tracer()
    if tracer:
        tracer.judge_decision(
            decision=decision,
            vulnerabilities_count=vulnerabilities_count,
            patches_count=patches_count,
            security_score=security_score,
        )


def cleanup_agent_sync(agent):
    """
    Safely cleanup an agent in synchronous context.
    
    Creates a new event loop to avoid 'Event loop is closed' errors
    when cleaning up agents from synchronous node functions.
    """
    try:
        import asyncio
        # Create and use a new event loop for cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(agent.cleanup())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception:
        # Silently ignore any cleanup errors
        pass



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
    display = get_display()
    
    state.status = "ARCHITECTING"
    state.touch()
    
    if display:
        display.show_agent_activity("Architect", "Generating initial design")
    
    try:
        agent = ArchitectAgent()
        _trace_agent_invoke("Architect", "ArchitectAgent", input_prompt=state.user_prompt)
        output = agent.invoke(user_prompt=state.user_prompt)

        _trace_agent_complete(
            "Architect",
            "ArchitectAgent",
            success=True,
            vulnerabilities_found=0,
        )
        
        if display:
            display.clear_agent_activity()
        
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
        _trace_agent_complete(
            "Architect",
            "ArchitectAgent",
            success=False,
            error_message=str(e),
        )
        logger.error(f"Architect timeout: {e}")
        if display:
            display.clear_agent_activity()
        return {
            "status": "FAILED",
            "error_code": "FAILED_ARCHITECT_TIMEOUT",
            "termination_reason": str(e),
        }
    except AgentSchemaError as e:
        _trace_agent_complete(
            "Architect",
            "ArchitectAgent",
            success=False,
            error_message=str(e),
        )
        logger.error(f"Architect schema error: {e}")
        if display:
            display.clear_agent_activity()
        return {
            "status": "FAILED",
            "error_code": "FAILED_SCHEMA_VIOLATION",
            "termination_reason": str(e),
        }
    except Exception as e:
        _trace_agent_complete(
            "Architect",
            "ArchitectAgent",
            success=False,
            error_message=str(e),
        )
        logger.error(f"Architect error: {e}")
        if display:
            display.clear_agent_activity()
        return {
            "status": "FAILED",
            "error_code": "FAILED_ARCHITECT_ERROR",
            "termination_reason": str(e),
        }
    finally:
        # Cleanup agent to prevent async warnings
        if 'agent' in locals():
            cleanup_agent_sync(agent)


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
    _trace_design_validated(is_valid, reason, len(state.design_components))
    
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
    iteration: int,
    display=None,
) -> tuple[str, list, str | None]:
    """Run a single Red Team agent asynchronously."""
    agent_class = RED_TEAM_AGENTS.get(agent_name)
    if not agent_class:
        return agent_name, [], f"Unknown agent: {agent_name}"
    
    agent = None
    agent_type = _resolve_agent_type(agent_name)
    try:
        agent = agent_class()
        _trace_agent_invoke(agent_type, agent_name)
        
        # Show agent activity if display is provided
        if display:
            display.show_agent_activity(agent_name, "Analyzing design")
        
        output = await agent.invoke_async(
            design_markdown=design_markdown,
            components=components,
            iteration=iteration,
        )
        
        # Clear activity line
        if display:
            display.clear_agent_activity()

        _trace_agent_complete(
            agent_type,
            agent_name,
            success=True,
            vulnerabilities_found=len(output.vulnerabilities),
        )
        
        return agent_name, output.vulnerabilities, None
    except AgentTimeoutError as e:
        _trace_agent_complete(
            agent_type,
            agent_name,
            success=False,
            error_message=str(e),
        )
        if display:
            display.clear_agent_activity()
        return agent_name, [], f"Timeout: {e}"
    except AgentSchemaError as e:
        _trace_agent_complete(
            agent_type,
            agent_name,
            success=False,
            error_message=str(e),
        )
        if display:
            display.clear_agent_activity()
        return agent_name, [], f"Schema error: {e}"
    except Exception as e:
        _trace_agent_complete(
            agent_type,
            agent_name,
            success=False,
            error_message=str(e),
        )
        if display:
            display.clear_agent_activity()
        return agent_name, [], f"Error: {e}"
    finally:
        # Explicit cleanup to prevent async warnings
        if agent:
            try:
                await agent.cleanup()
            except Exception:
                pass


def red_team_node(state: CrucibleState) -> Dict[str, Any]:
    """Red Team attacks the design (parallel or sequential based on config and token budget)."""
    config = get_config()
    display = get_display()
    logger.info(f"Red Team attacking with agents: {state.active_agents}")
    _trace_iteration_start(state)
    
    # NEW: Smart batching based on token budget
    sequential = config.sequential_mode
    max_concurrent = 6  # Default full parallelism
    
    if state.token_budget:
        use_parallel, recommended_concurrent = get_parallelism_recommendation(state.token_budget)
        
        # Check for budget threshold warnings
        warning = state.token_budget.check_threshold()
        if warning and display:
            display.print_event("System", "token_budget", warning)
        
        if not use_parallel:
            sequential = True
            if display:
                display.print_event("System", "smart_batch",
                    f"Switching to sequential mode (budget: {state.token_budget.percent_used:.1f}% used)")
        elif recommended_concurrent < 6:
            max_concurrent = recommended_concurrent
            if display:
                display.print_event("System", "smart_batch",
                    f"Limiting to {max_concurrent} concurrent agents (budget: {state.token_budget.percent_used:.1f}% used)")
    
    if sequential:
        # Run agents one-by-one
        async def run_agents_sequentially():
            results = []
            for agent_name in state.active_agents:
                result = await _run_single_red_team_agent(
                    agent_name,
                    state.design_markdown,
                    state.design_components,
                    state.iteration_count,
                    display,
                )
                results.append(result)
                await asyncio.sleep(3.0)
            return results
        
        results = asyncio.run(run_agents_sequentially())
    else:
        # Run with limited concurrency (batched parallelism)
        async def run_all_agents():
            agents = state.active_agents
            all_results = []
            
            for i in range(0, len(agents), max_concurrent):
                batch = agents[i:i+max_concurrent]
                tasks = [
                    _run_single_red_team_agent(
                        agent_name,
                        state.design_markdown,
                        state.design_components,
                        state.iteration_count,
                        display,
                    )
                    for agent_name in batch
                ]
                batch_results = await asyncio.gather(*tasks)
                all_results.extend(batch_results)
                
                if i + max_concurrent < len(agents):
                    await asyncio.sleep(1.0)
            
            return all_results
        
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
                agent_name=agent_name,
            )
            all_vulns.append(vuln)
            _trace_vulnerability_found(vuln)
    
    if not all_vulns:
        logger.warning("No vulnerabilities found by any agent")
    
    # NEW: Deduplicate vulnerabilities before judge
    if config.deduplication.enabled and all_vulns:
        deduplicator = VulnerabilityDeduplicator(
            similarity_threshold=config.deduplication.similarity_threshold
        )
        unique_vulns, duplicates = deduplicator.filter_duplicates(
            all_vulns,
            state.vulnerabilities
        )

        for duplicate_vuln, original_vuln, similarity_score in duplicates:
            _trace_vulnerability_duplicate(duplicate_vuln, original_vuln, similarity_score)
        
        if duplicates and display:
            display.print_event("System", "deduplication",
                f"🔍 Filtered {len(duplicates)} duplicate vulnerabilities")
        
        state.duplicate_count += len(duplicates)
        all_vulns = unique_vulns
    
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




def determine_defender_routing(state: CrucibleState) -> Literal["quick_fix", "architect"]:
    """Determine defender routing via explicit strategy policy."""
    from crucible.agents.specialized_defenders import select_defender_mode

    mode = select_defender_mode(state)
    if mode == "ARCHITECT":
        return "architect"
    return "quick_fix"


def defender_node(state: CrucibleState) -> Dict[str, Any]:
    """
    Main defender entry point.
    
    Orchestrates specialized defenders:
    1. QuickFixer (Tactical)
    2. ArchitectRefactorer (Strategic)
    3. DefenseCoordinator (Validation)
    """
    from crucible.agents.specialized_defenders import (
        QuickFixer, ArchitectRefactorer, DefenseCoordinator
    )
    
    config = get_config()
    display = get_display()
    agents_to_cleanup = []
    
    logger.info(f"Defender node active. Mode: {state.defender_mode}")
    
    active_vulns = state.get_active_vulnerabilities()
    if not active_vulns:
        return {"status": "EVALUATING"}
        
    try:
        # 1. Select Strategy
        # If we haven't selected a mode yet (came from Red Team)
        if state.status == "PATCHING":
            mode = determine_defender_routing(state)
            state.defender_mode = "ARCHITECT" if mode == "architect" else "QUICK_FIX"
        
        # 2. Execute Strategy
        patches = []
        updated_design = state.design_markdown
        
        if state.defender_mode == "QUICK_FIX":
            logger.info("Running QuickFixer...")
            if display:
                display.show_agent_activity("Defender", "Generating tactical fixes")
            
            agent = QuickFixer()
            agents_to_cleanup.append(agent)
            _trace_agent_invoke("Defender", "QuickFixer")
            output = agent.invoke(
                design_markdown=state.design_markdown,
                components=state.design_components,
                vulnerabilities=active_vulns,
            )
            _trace_agent_complete(
                "Defender",
                "QuickFixer",
                success=True,
                vulnerabilities_found=0,
            )
            raw_patches = output.patches
            updated_design = output.updated_design_markdown
            
            if display:
                display.clear_agent_activity()
            
        elif state.defender_mode == "ARCHITECT":
            logger.info("Running ArchitectRefactorer...")
            if display:
                display.show_agent_activity("Defender", "Generating strategic refactoring")
            
            agent = ArchitectRefactorer()
            agents_to_cleanup.append(agent)
            _trace_agent_invoke("Defender", "ArchitectRefactorer")
            output = agent.invoke(
                design_markdown=state.design_markdown,
                components=state.design_components,
                vulnerabilities=active_vulns,
            )
            _trace_agent_complete(
                "Defender",
                "ArchitectRefactorer",
                success=True,
                vulnerabilities_found=0,
            )
            raw_patches = output.patches
            updated_design = output.updated_design_markdown
            
            if display:
                display.clear_agent_activity()
            
            # Architect can add components
            # Note: We'd need to properly parse and merge new components here
            # For now, we assume the design markdown reflects it
            
        else: # Coordinator (should usually be called after)
             # But here we treat it as a final validation step implicitly
             pass

        # 3. Convert patches using PatchV2 / IncrementalPatch
        from crucible.patches_v2 import IncrementalPatch, DefenseJustification
        for p_data in raw_patches:
            target_vid = p_data.get("target_vulnerability_id", 0)
            fix_category = p_data.get("fix_category", "TACTICAL")
            target_vuln = next((v for v in active_vulns if v.vulnerability_id == target_vid), None)
            is_partial = (
                target_vuln is not None
                and target_vuln.severity in ("CRITICAL", "HIGH")
                and fix_category == "TACTICAL"
            )

            base_kwargs = dict(
                patch_id=state.allocate_patch_id(),
                target_vulnerability_id=target_vid,
                fix_description=p_data.get("fix_description", ""),
                design_changes=p_data.get("design_changes", []),
                introduces_new_assumptions=p_data.get("introduces_new_assumptions", False),
                patch_confidence="HIGH",
                fix_category=fix_category,
                defender_strategy=state.defender_strategy,
                trade_offs=p_data.get("trade_offs"),
            )

            if is_partial:
                severity_after = "HIGH" if target_vuln.severity == "CRITICAL" else "MEDIUM"
                patch = IncrementalPatch(
                    **base_kwargs,
                    full_fix=False,
                    severity_before=target_vuln.severity,
                    severity_after=severity_after,
                    remaining_risk=(
                        f"Tactical fix reduces severity from {target_vuln.severity} to {severity_after}; "
                        "architectural fix still needed"
                    ),
                )
            else:
                patch = Patch(**base_kwargs)

            # Auto-generate DefenseJustification (Fix 6)
            patch.defense_justification = DefenseJustification(
                patch_id=patch.patch_id,
                attack_vector_addressed=target_vuln.attack_vector if target_vuln else "Unknown",
                mechanism=patch.fix_description,
                verification_method="CODE_REVIEW" if fix_category == "TACTICAL" else "INTEGRATION_TEST",
            )
            patches.append(patch)

        # 4. Coordinate (Always run if we have patches)
        if patches:
            logger.info("Running DefenseCoordinator...")
            if display:
                display.show_agent_activity("Defender", "Coordinating patch strategy")
            
            coord_agent = DefenseCoordinator()
            agents_to_cleanup.append(coord_agent)
            _trace_agent_invoke("Defender", "DefenseCoordinator")
            coord_out = coord_agent.invoke(
                design_markdown=state.design_markdown,
                patches=[p.model_dump() for p in patches],
                vulnerabilities=active_vulns
            )
            _trace_agent_complete(
                "Defender",
                "DefenseCoordinator",
                success=True,
                vulnerabilities_found=0,
            )
            
            if display:
                display.clear_agent_activity()
            
            # Log coordination results
            if coord_out.conflicts_detected:
                logger.warning(f"Conflicts detected: {coord_out.conflicts_detected}")
            
            # In a full impl, we'd apply unified patches here. 
            # For iteration 1, we just log and accept originals unless rejected.
        
        # NEW: Validate patches before Judge verification
        if config.validation.enabled and patches:
            validator = PatchValidator(strict_mode=config.validation.strict_mode)
            validation_results = validator.batch_validate(
                patches,
                state.design_components,
                state.vulnerabilities
            )
            
            # Filter out invalid patches
            valid_patches = []
            for patch in patches:
                result = validation_results[patch.patch_id]
                if result["valid"]:
                    valid_patches.append(patch)
                    _trace_patch_applied(patch)
                    # Log warnings if any
                    if result["warnings"] and display:
                        for warning in result["warnings"]:
                            display.print_event("Validator", "warning", f"⚠️  Patch #{patch.patch_id}: {warning}")
                else:
                    # Patch failed validation
                    state.rejected_patch_count += 1
                    _trace_patch_rejected(patch, "; ".join(result["errors"]))
                    if display:
                        for error in result["errors"]:
                            display.print_event("Validator", "error", f"❌ Patch #{patch.patch_id} rejected: {error}")
                    logger.warning(f"Patch #{patch.patch_id} failed validation: {result['errors']}")
            
            if len(valid_patches) < len(patches) and display:
                display.print_event("Validator", "summary",
                    f"Validation: {len(valid_patches)}/{len(patches)} patches accepted")
            
            patches = valid_patches

        # 5. Verify patches with Judge
        judge = JudgeController()
        is_valid, reason = judge.verify_patches(
            state,
            state.design_markdown,
            updated_design,
            patches,
        )
        
        if not is_valid:
            logger.error(f"Patch verification failed: {reason}")
            return {
                "status": "FAILED",
                "termination_reason": reason,
            }
            
        # Create summary
        summary = IterationSummary(
            iteration_id=state.iteration_count,
            vulnerabilities_reported=[v.vulnerability_id for v in active_vulns],
            patches_applied=[p.patch_id for p in patches],
            critical_remaining=state.get_unpatched_critical_count(),
        )
        
        return {
            "design_markdown": updated_design,
            "patches": state.patches + patches,
            "iteration_summaries": state.iteration_summaries + [summary],
            "iteration_count": state.iteration_count + 1,
            "status": "EVALUATING",
        }

    except Exception as e:
        logger.error(f"Defender error: {e}")
        return {"status": "EVALUATING"} # Fail open to allow retry/judge to decide
    finally:
        # Cleanup all defender agents
        if display:
            display.clear_agent_activity()
        for agent in agents_to_cleanup:
            cleanup_agent_sync(agent)


def _calculate_terminal_metrics(state: CrucibleState) -> None:
    """Calculate v2 analytics at the end of a run (mutates state in place)."""
    from crucible.patches_v2 import (
        calculate_attack_effectiveness,
        calculate_convergence_metrics,
        DefenseQuality,
        IncrementalPatch,
    )
    display = get_display()

    # Per-agent attack effectiveness
    patched_ids = {p.target_vulnerability_id for p in state.patches}
    vulns_as_dicts = [
        {"agent": v.agent_name, "vulnerability_id": v.vulnerability_id}
        for v in state.vulnerabilities
    ]
    effectiveness_rows = []
    for agent_name in state.active_agents:
        eff = calculate_attack_effectiveness(agent_name, vulns_as_dicts, list(patched_ids))
        row = {
            "agent": eff.agent,
            "total_attacks": eff.total_attacks,
            "accepted_attacks": eff.accepted_attacks,
            "patched_attacks": eff.patched_attacks,
            "effectiveness_ratio": eff.effectiveness_ratio,
            "impact_ratio": eff.impact_ratio,
        }
        effectiveness_rows.append(row)
    state.attack_effectiveness = effectiveness_rows

    # Defense quality
    partial = sum(1 for p in state.patches if isinstance(p, IncrementalPatch) and not p.full_fix)
    full = len(state.patches) - partial
    dq = DefenseQuality(
        total_patches=len(state.patches),
        regression_count=0,
        full_fix_count=full,
        partial_fix_count=partial,
    )
    state.defense_quality = {
        "total_patches": dq.total_patches,
        "regression_count": dq.regression_count,
        "full_fix_count": dq.full_fix_count,
        "partial_fix_count": dq.partial_fix_count,
        "regression_rate": dq.regression_rate,
        "first_time_fix_rate": dq.first_time_fix_rate,
    }

    # Convergence metrics
    initial_critical = (
        state.iteration_summaries[0].critical_remaining if state.iteration_summaries else 0
    )
    cm = calculate_convergence_metrics(
        state.iteration_count, initial_critical, state.get_unpatched_critical_count()
    )
    state.convergence_metrics = {
        "iterations_completed": cm.iterations_completed,
        "critical_at_start": cm.critical_at_start,
        "critical_at_end": cm.critical_at_end,
        "vulnerability_reduction_rate": cm.vulnerability_reduction_rate,
    }

    # Display summary table
    if display and effectiveness_rows:
        display.print_event("Analytics", "metrics", "=== Run Analytics ===")
        for row in effectiveness_rows:
            if row["total_attacks"] > 0:
                display.print_event(
                    "Analytics", "agent",
                    f"{row['agent']}: {row['total_attacks']} attacks, "
                    f"{row['patched_attacks']} patched "
                    f"({row['impact_ratio']:.0%} impact)",
                )
        display.print_event(
            "Analytics", "defense",
            f"Defense: {full} full fixes, {partial} partial fixes",
        )
        display.print_event(
            "Analytics", "convergence",
            f"Convergence: {cm.iterations_completed} iterations, "
            f"{cm.critical_at_start}→{cm.critical_at_end} criticals "
            f"({cm.vulnerability_reduction_rate:.0%} reduced)",
        )


def evaluate_node(state: CrucibleState) -> Dict[str, Any]:
    """Judge evaluates and decides termination."""
    logger.info("Judge evaluating iteration...")
    
    judge = JudgeController()
    decision = judge.decide_termination(state)
    from crucible.security_metrics import SecurityScorer

    scorer = SecurityScorer()
    security_score = scorer.calculate_overall_score(state)

    state.security_scores.append(security_score.to_dict())
    state.current_security_score = security_score.to_dict()

    display = get_display()
    if display:
        improvement = None
        if len(state.security_scores) > 1:
            prev_score = state.security_scores[-2]["overall_score"]
            improvement = security_score.overall_score - prev_score

        display.print_security_score(security_score, improvement)

    _trace_judge_decision(
        decision.decision,
        vulnerabilities_count=len(state.vulnerabilities),
        patches_count=len(state.patches),
        security_score=security_score.overall_score,
    )
    _trace_iteration_end(state)
    
    if decision.decision in ("TERMINATE_STABLE", "TERMINATE_UNRESOLVED", "TERMINATE_FAILED"):
        _calculate_terminal_metrics(state)
        status = decision.decision.replace("TERMINATE_", "")
        return {
            "status": status,
            "termination_reason": decision.reason,
            "attack_effectiveness": state.attack_effectiveness,
            "defense_quality": state.defense_quality,
            "convergence_metrics": state.convergence_metrics,
        }
    else:
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
        defender_strategy=config.defender_strategy_sim.default_strategy,
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
