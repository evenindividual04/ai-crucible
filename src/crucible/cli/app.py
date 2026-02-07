"""
Typer CLI application for the AI Crucible.

Entry point for the command-line interface.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional
import logging
import json
import warnings

# Suppress async event loop closure warnings
# These are harmless - they occur during cleanup after all work is complete
warnings.filterwarnings("ignore", message=".*Event loop is closed.*")
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*loop.*")

# Install stderr filter to suppress RuntimeError tracebacks
from crucible.stderr_filter import install_stderr_filter
install_stderr_filter()

# Load .env file for API keys
from dotenv import load_dotenv
load_dotenv()

import typer
from rich.console import Console

from crucible import __version__
from crucible.config import CrucibleConfig, set_config
from crucible.state import CrucibleState
from crucible.graph import run_crucible_async, build_crucible
from crucible.cli.display import CrucibleDisplay
from crucible.token_tracker import TokenBudget
from crucible.checkpoint import CheckpointManager

# Import display extensions for security metrics
try:
    from crucible.cli import display_security
except ImportError:
    pass  # Optional extension

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="crucible",
    help="The AI Crucible - Adversarial Reasoning Engine",
    add_completion=False,
)

console = Console(force_terminal=True)


@app.command()
def run(
    prompt: Optional[str] = typer.Argument(None, help="The system design prompt to analyze"),
    input_file: Optional[Path] = typer.Option(
        None, "--input-file", "-f",
        help="Read design from a file instead of prompt argument"
    ),
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to configuration file"
    ),
    max_iterations: int = typer.Option(
        3, "--max-iterations", "-n",
        help="Maximum number of adversarial iterations"
    ),
    similarity_threshold: float = typer.Option(
        0.85, "--similarity-threshold",
        help="Threshold for duplicate detection (0.0-1.0)"
    ),
    confidence_threshold: float = typer.Option(
        0.7, "--confidence-threshold",
        help="Minimum confidence for blocking vulnerabilities (0.0-1.0)"
    ),
    output_design: Optional[Path] = typer.Option(
        None, "--output-design", "-o",
        help="Save final design to a markdown file"
    ),
    output_diagrams: Optional[Path] = typer.Option(
        None, "--output-diagrams",
        help="Save Mermaid architecture diagrams to a markdown file"
    ),
    debug: bool = typer.Option(
        False, "--debug", "-d",
        help="Enable debug mode (plain text, full state dumps)"
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="Output in JSON format (for CI/CD)"
    ),
    provider: str = typer.Option(
        "groq", "--provider", "-p",
        help="LLM provider: groq (recommended), google, ollama, perplexity, openai, anthropic"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model to use (provider-specific, optional)"
    ),
    sequential: bool = typer.Option(
        True, "--sequential/--parallel",
        help="Run agents sequentially to avoid rate limits"
    ),
):
    """
    Run the AI Crucible on a system design prompt.
    
    The Crucible will:
    1. Generate an initial design (Architect)
    2. Attack it from multiple angles (Red Team)
    3. Apply patches (Defender)
    4. Evaluate and iterate until stable or unresolved
    """
    # Handle input: either prompt argument or input file
    if input_file:
        if not input_file.exists():
            console.print(f"[red]Error:[/red] Input file not found: {input_file}")
            raise typer.Exit(1)
        
        try:
            prompt = input_file.read_text(encoding='utf-8')
            console.print(f"[dim]Reading design from: {input_file}[/dim]")
        except Exception as e:
            console.print(f"[red]Error reading file:[/red] {e}")
            raise typer.Exit(1)
    elif not prompt:
        console.print("[red]Error:[/red] Either provide a prompt or use --input-file")
        console.print("\nUsage:")
        console.print("  crucible run \"Your design prompt here\"")
        console.print("  crucible run --input-file design.md")
        raise typer.Exit(1)
    
    # Determine display mode
    if json_output:
        mode = "json"
    elif debug:
        mode = "debug"
    else:
        mode = "war_room"
    
    # Suppress verbose logging in war_room mode
    if mode == "war_room":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        logging.getLogger("google_genai").setLevel(logging.WARNING)
        logging.getLogger("crucible.graph").setLevel(logging.WARNING)
        logging.getLogger("crucible.judge.novelty").setLevel(logging.WARNING)
        logging.getLogger("crucible.cache").setLevel(logging.WARNING)
        logging.getLogger("crucible.workers").setLevel(logging.WARNING)
        # Disable tqdm progress bars
        import os
        os.environ["TQDM_DISABLE"] = "1"
    
    # Pre-warm resources in background (embedding model, agent instances)
    try:
        from crucible.workers import prewarm_resources
        prewarm_resources()
    except Exception as e:
        logger.debug(f"Pre-warming skipped: {e}")
    
    # Initialize Redis cache if configured
    try:
        import os
        redis_enabled = os.environ.get("REDIS_ENABLED", "").lower() == "true"
        if redis_enabled:
            from crucible.cache import init_redis_cache
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", "6379"))
            redis_password = os.environ.get("REDIS_PASSWORD") or None
            init_redis_cache(host=redis_host, port=redis_port, password=redis_password)
            if mode != "json":
                console.print("[dim]Redis cache enabled[/dim]")
    except Exception as e:
        logger.debug(f"Redis initialization skipped: {e}")
    
    # Load and configure
    llm_overrides = {"provider": provider}
    if model:
        llm_overrides["model"] = model
    
    overrides = {
        "max_iterations": max_iterations,
        "sequential_mode": sequential,
        "similarity": {"threshold": similarity_threshold},
        "confidence": {"blocking_threshold": confidence_threshold},
        "output": {"mode": mode},
        "llm": llm_overrides,
    }
    
    try:
        config = CrucibleConfig.load(config_path=config_file, overrides=overrides)
        set_config(config)
    except ValueError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1)
    
    # Set up display
    display = CrucibleDisplay(mode=mode, console=console)
    
    # Run the crucible
    try:
        final_state = asyncio.run(_run_with_display(prompt, config, display))
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(1)
    except RuntimeError as e:
        if str(e) == "Event loop is closed":
            # Benign error during shutdown with httpx/asyncio
            pass
        else:
            raise
    except Exception as e:
        console.print(f"\n[red]Crucible failed[/red]")
        # Print full traceback in debug mode
        if debug:
            import traceback
            console.print(traceback.format_exc())
        else:
            console.print(f"Error: {e}")
        raise typer.Exit(1)
    
    # Print final output
    display.print_completion_celebration(final_state)
    display.print_termination(final_state)
    display.print_summary_table(final_state)
    
    # Save final design if requested
    if output_design:
        output_design.write_text(final_state.design_markdown)
        console.print(f"\n[green]Final design saved to:[/green] {output_design}")
    
    # Save diagrams if requested
    if output_diagrams:
        from crucible.diagrams import generate_all_diagrams
        diagrams_content = generate_all_diagrams(final_state)
        output_diagrams.write_text(diagrams_content)
        console.print(f"[green]Diagrams saved to:[/green] {output_diagrams}")
    
    # Exit with appropriate code
    exit_code = {
        "STABLE": 0,
        "UNRESOLVED": 1,
        "FAILED": 2,
    }.get(final_state.status, 2)
    
    raise typer.Exit(exit_code)


async def _run_with_display(
    prompt: str,
    config: CrucibleConfig,
    display: CrucibleDisplay
) -> CrucibleState:
    """Run the crucible with live display updates."""
    
    # Show welcome banner
    display.print_welcome_banner()
    
    # Initialize state
    state = CrucibleState(
        user_prompt=prompt,
        max_iterations=config.max_iterations,
    )
    
    # NEW: Initialize token budget
    if config.token_budget.daily_limit > 0:
        state.token_budget = TokenBudget(
            daily_limit=config.token_budget.daily_limit,
            warn_threshold=config.token_budget.warn_threshold,
            critical_threshold=config.token_budget.critical_threshold
        )
    
    # NEW: Initialize checkpoint manager
    checkpoint_mgr = None
    if config.checkpointing.enabled:
        output_dir = Path("outputs")
        checkpoint_mgr = CheckpointManager(run_id=state.run_id, output_dir=output_dir)
        display.print_event("System", "checkpoint", f"Checkpointing enabled (run ID: {state.run_id})")
    
    display.print_header(state)
    
    # Build and run the graph
    app = build_crucible()
    
    # Set display for streaming output
    from crucible.graph import set_display
    set_display(display)
    
    # Track state for display
    last_vuln_count = 0
    last_patch_count = 0
    last_status = state.status
    
    async for step in app.astream(state):
        for node_name, updates in step.items():
            if isinstance(updates, dict):
                for key, value in updates.items():
                    setattr(state, key, value)
        
        # Display updates based on state changes
        if state.status != last_status:
            # Print iteration separator when starting a new iteration
            if state.status == "ROUTING" and state.iteration_count > 0:
                display.print_iteration_separator(state.iteration_count, state.max_iterations)
            
            if state.status == "ARCHITECTING":
                display.print_event("Architect", "status", "Generating initial design...")
            elif state.status == "ROUTING":
                display.print_architect_proposal(state)
            elif state.status == "UNDER_ATTACK":
                display.print_event("Judge", "decision", f"Activated agents: {', '.join(state.active_agents)}")
            elif state.status == "PATCHING":
                display.print_event("Defender", "status", "Generating patches...")
            elif state.status == "EVALUATING":
                display.print_event("Judge", "status", f"Evaluating iteration {state.iteration_count}...")
            
            last_status = state.status
        
        # Show new vulnerabilities
        if len(state.vulnerabilities) > last_vuln_count:
            for vuln in state.vulnerabilities[last_vuln_count:]:
                display.print_vulnerability(vuln)
            last_vuln_count = len(state.vulnerabilities)
        
        # Show new patches
        if len(state.patches) > last_patch_count:
            for patch in state.patches[last_patch_count:]:
                vuln = state.get_vulnerability_by_id(patch.target_vulnerability_id)
                display.print_patch(patch, vuln)
            last_patch_count = len(state.patches)
        
        # Update header periodically
        if state.status in ("UNDER_ATTACK", "PATCHING", "EVALUATING"):
            display.print_header(state)
        
        # NEW: Save checkpoint after each iteration
        if checkpoint_mgr and state.status == "EVALUATING" and state.iteration_count > 0:
            try:
                checkpoint_mgr.save(state, state.iteration_count)
                display.print_event("System", "checkpoint", f"💾 Checkpoint saved (iteration {state.iteration_count})")
            except Exception as e:
                logger.warning(f"Failed to save checkpoint: {e}")
    
    # Async cleanup before event loop closes
    import gc
    gc.collect()
    await asyncio.sleep(0.1)
    gc.collect()
    
    return state


@app.command()
def version():
    """Show version information."""
    console.print(f"AI Crucible v{__version__}")


@app.command(name="list-runs")
def list_runs(
    output_dir: Path = typer.Option(
        Path("outputs"), "--output-dir", "-o",
        help="Directory containing run outputs"
    )
):
    """List all saved runs with checkpoint data."""
    from crucible.checkpoint import list_all_runs
    
    runs = list_all_runs(output_dir)
    
    if not runs:
        console.print("[yellow]No saved runs found[/yellow]")
        return
    
    console.print(f"\n[bold]Found {len(runs)} saved runs:[/bold]\n")
    
    for run in runs:
        console.print(f"[cyan]{run['run_id']}[/cyan]")
        console.print(f"  Status: {run['status']}")
        console.print(f"  Latest iteration: {run['latest_iteration']}")
        console.print(f"  Timestamp: {run['timestamp']}")
        summary = run.get('summary', {})
        console.print(f"  Vulnerabilities: {summary.get('total_vulnerabilities', 0)}")
        console.print(f"  Patches: {summary.get('total_patches', 0)}")
        console.print()


@app.command()
def resume(
    run_id: str = typer.Argument(..., help="Run ID to resume"),
    iteration: Optional[int] = typer.Option(
        None, "--iteration", "-i",
        help="Specific iteration to resume from (default: latest)"
    ),
    output_dir: Path = typer.Option(
        Path("outputs"), "--output-dir", "-o",
        help="Directory containing run outputs"
    )
):
    """Resume an interrupted run from a checkpoint."""
    from crucible.checkpoint import CheckpointManager
    
    # Load checkpoint
    checkpoint_mgr = CheckpointManager(run_id=run_id, output_dir=output_dir)
    
    try:
        state, checkpoint_data = checkpoint_mgr.load(iteration=iteration)
        console.print(f"[green]Loaded checkpoint from iteration {state.iteration_count}[/green]")
        console.print(f"Status: {state.status}")
        console.print(f"Vulnerabilities: {len(state.vulnerabilities)}")
        console.print(f"Patches: {len(state.patches)}")
        console.print()
        
        # TODO: Resume execution from loaded state
        # This would require refactoring _run_with_display to accept initial state
        console.print("[yellow]Note: Full resume execution not yet implemented[/yellow]")
        console.print("[dim]For now, this command loads and displays the checkpoint data[/dim]")
        
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"\nUse [cyan]crucible list-runs[/cyan] to see available runs")
        raise typer.Exit(1)


@app.command()
def init(
    path: Path = typer.Argument(
        Path("."),
        help="Directory to create config file in"
    ),
):
    """Initialize a crucible.yaml configuration file."""
    config_path = path / "crucible.yaml"
    
    if config_path.exists():
        console.print(f"[yellow]Config file already exists:[/yellow] {config_path}")
        raise typer.Exit(1)
    
    default_config = """# AI Crucible Configuration
# See config-schema.md for full documentation

max_iterations: 3

similarity:
  threshold: 0.85
  model: "all-MiniLM-L6-v2"

confidence:
  blocking_threshold: 0.7
  degradation_rate: 0.8

llm:
  provider: "google"
  model: "gemini-2.5-flash"
  temperature: 0.3

output:
  mode: "war_room"
  state_dump_on_failure: true
"""
    
    config_path.write_text(default_config)
    console.print(f"[green]Created config file:[/green] {config_path}")


@app.command()
def resume(
    checkpoint: Path = typer.Argument(..., help="Path to checkpoint file to resume from"),
    output_design: Optional[Path] = typer.Option(
        None, "--output-design", "-o",
        help="Save final design to a markdown file"
    ),
    debug: bool = typer.Option(
        False, "--debug", "-d",
        help="Enable debug mode"
    ),
):
    """Resume a run from a checkpoint file."""
    from crucible.checkpoint import load_checkpoint
    
    if not checkpoint.exists():
        console.print(f"[red]Checkpoint file not found:[/red] {checkpoint}")
        raise typer.Exit(1)
    
    try:
        state = load_checkpoint(checkpoint)
    except Exception as e:
        console.print(f"[red]Failed to load checkpoint:[/red] {e}")
        raise typer.Exit(1)
    
    console.print(f"[green]Resuming from checkpoint:[/green] {checkpoint}")
    console.print(f"  Iteration: {state.iteration_count}/{state.max_iterations}")
    console.print(f"  Status: {state.status}")
    console.print(f"  Vulnerabilities: {len(state.vulnerabilities)}")
    console.print(f"  Patches: {len(state.patches)}")
    
    # Set up display
    mode = "debug" if debug else "war_room"
    display = CrucibleDisplay(mode=mode, console=console)
    
    # Load config and continue
    config = CrucibleConfig.load()
    set_config(config)
    
    try:
        final_state = asyncio.run(_resume_with_display(state, config, display))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        logger.exception("Crucible resume failed")
        display.print_error("FAILED_UNEXPECTED", str(e))
        raise typer.Exit(2)
    
    # Print final output
    display.print_termination(final_state)
    display.print_summary_table(final_state)
    
    if output_design:
        output_design.write_text(final_state.design_markdown)
        console.print(f"\n[green]Final design saved to:[/green] {output_design}")
    
    exit_code = {"STABLE": 0, "UNRESOLVED": 1, "FAILED": 2}.get(final_state.status, 2)
    raise typer.Exit(exit_code)


async def _resume_with_display(
    state: CrucibleState,
    config: CrucibleConfig,
    display: CrucibleDisplay
) -> CrucibleState:
    """Resume a run from a saved state."""
    display.print_header(state)
    
    # Build and run the graph
    app = build_crucible()
    
    # Set display for streaming output
    from crucible.graph import set_display
    set_display(display)
    
    last_vuln_count = len(state.vulnerabilities)
    last_patch_count = len(state.patches)
    last_status = state.status
    
    async for step in app.astream(state):
        for node_name, updates in step.items():
            if isinstance(updates, dict):
                for key, value in updates.items():
                    setattr(state, key, value)
        
        if state.status != last_status:
            last_status = state.status
        
        if len(state.vulnerabilities) > last_vuln_count:
            for vuln in state.vulnerabilities[last_vuln_count:]:
                display.print_vulnerability(vuln)
            last_vuln_count = len(state.vulnerabilities)
        
        if len(state.patches) > last_patch_count:
            for patch in state.patches[last_patch_count:]:
                vuln = state.get_vulnerability_by_id(patch.target_vulnerability_id)
                display.print_patch(patch, vuln)
            last_patch_count = len(state.patches)
        
        if state.status in ("UNDER_ATTACK", "PATCHING", "EVALUATING"):
            display.print_header(state)
    
    return state


if __name__ == "__main__":
    app()
