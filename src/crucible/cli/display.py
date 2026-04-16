"""
Rich-based display for the AI Crucible CLI.

Implements the visual specification from cli-spec.md.
"""

from datetime import datetime, timezone
from typing import List, Optional
import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.spinner import Spinner
from rich.columns import Columns
from rich import box

from crucible.state import CrucibleState, Vulnerability, Patch, IterationSummary


# Color scheme from cli-spec.md
AGENT_COLORS = {
    "Architect": "cyan",
    "Security Hawk": "red",
    "Scale Monster": "dark_orange",
    "Cost Analyst": "yellow",
    "Logic Breaker": "purple",
    "Defender": "green",
    "Judge": "white",
}

AGENT_ICONS = {
    "Architect": "🏗️",
    "Security Hawk": "⚠️",
    "Scale Monster": "📈",
    "Cost Analyst": "💰",
    "Logic Breaker": "🧩",
    "Defender": "🛡️",
    "Judge": "⚖️",
}

SEVERITY_COLORS = {
    "CRITICAL": "bold red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "dim",
}

STATUS_COLORS = {
    "INIT": "dim",
    "ARCHITECTING": "cyan",
    "ROUTING": "blue",
    "UNDER_ATTACK": "red",
    "PATCHING": "green",
    "EVALUATING": "yellow",
    "STABLE": "bold green",
    "UNRESOLVED": "bold yellow",
    "FAILED": "bold red",
}


class CrucibleDisplay:
    """Rich-based display for the Crucible CLI."""
    
    def __init__(
        self,
        mode: str = "war_room",  # war_room, debug, json
        console: Optional[Console] = None
    ):
        self.mode = mode
        self.console = console or Console()
        self.start_time = datetime.now(timezone.utc)
        self.events: List[dict] = []
        self.progress = None
        self.current_spinner = None
        self.metrics = {
            "vulns": 0,
            "patches": 0,
            "iteration": 0,
        }
    
    def _get_relative_time(self) -> str:
        """Get time relative to start."""
        delta = datetime.now(timezone.utc) - self.start_time
        return f"+{delta.total_seconds():.1f}s"
    
    def print_header(self, state: CrucibleState) -> None:
        """Print the header bar."""
        if self.mode == "json":
            return
        
        if self.mode == "debug":
            self.console.print(f"\n=== THE CRUCIBLE ===")
            self.console.print(f"Iteration: {state.iteration_count}/{state.max_iterations}")
            self.console.print(f"Status: {state.status}")
            self.console.print("=" * 40)
            return
        
        # War room mode with live metrics
        title = Text()
        title.append("⚔️  THE CRUCIBLE", style="bold cyan")
        title.append(" // ", style="dim")
        title.append("ADVERSARIAL ENGINE", style="cyan")
        
        status_style = STATUS_COLORS.get(state.status, "white")
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        # Create info with metrics
        info = Text()
        info.append(f"Iteration: {state.iteration_count}/{state.max_iterations}", style="bold")
        info.append(" │ ", style="dim")
        info.append(f"Status: ", style="dim")
        info.append(state.status, style=status_style)
        info.append(" │ ", style="dim")
        info.append(f"⚠️  {len(state.vulnerabilities)} vulns", style="red")
        info.append(" │ ", style="dim")
        info.append(f"🛡️  {len(state.patches)} patches", style="green")
        info.append(" │ ", style="dim")
        info.append(f"⏱️  {elapsed:.0f}s", style="cyan")
        
        self.console.print(Panel(
            info,
            title=title,
            border_style="cyan",
            box=box.DOUBLE,
        ))
    
    def print_event(
        self,
        agent: str,
        event_type: str,
        content: str,
        severity: Optional[str] = None
    ) -> None:
        """Print an event to the console."""
        timestamp = self._get_relative_time()
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "event_type": event_type,
            "content": content,
            "severity": severity,
        }
        self.events.append(event)
        
        if self.mode == "json":
            self.console.print(json.dumps(event))
            return
        
        if self.mode == "debug":
            self.console.print(f"[{timestamp}] [{agent}] {event_type}: {content}")
            return
        
        # War room mode
        icon = AGENT_ICONS.get(agent, "•")
        color = AGENT_COLORS.get(agent, "white")
        
        header = Text()
        header.append(f"{icon} ", style=color)
        header.append(f"[{agent}]", style=f"bold {color}")
        header.append(f" {timestamp}", style="dim")
        
        if severity:
            sev_style = SEVERITY_COLORS.get(severity, "white")
            header.append(f" [{severity}]", style=sev_style)
        
        self.console.print(header)
        self.console.print(f"   {content}")
        self.console.print()
    
    def print_architect_proposal(self, state: CrucibleState) -> None:
        """Print the Architect's proposal."""
        content = f"Proposed design with {len(state.design_components)} components"
        
        if self.mode == "war_room":
            # Show component summary
            comp_names = [c.name for c in state.design_components]
            content += f": {', '.join(comp_names)}"
        
        self.print_event("Architect", "proposal", content)
        
        if self.mode == "debug":
            self.console.print("\n--- DESIGN ---")
            self.console.print(state.design_markdown[:1000])
            self.console.print("--- END DESIGN ---\n")
    
    def print_vulnerability(self, vuln: Vulnerability) -> None:
        """Print a vulnerability found by Red Team."""
        agent_name = {
            "SECURITY": "Security Hawk",
            "SCALABILITY": "Scale Monster",
            "COST": "Cost Analyst",
            "LOGIC": "Logic Breaker",
        }.get(vuln.domain, "Red Team")
        
        # Enhanced confidence display with colors
        confidence_style = "green" if vuln.confidence >= 0.8 else "yellow" if vuln.confidence >= 0.6 else "red"
        
        content = f"{vuln.title}"
        if self.mode == "war_room":
            conf_text = Text()
            conf_text.append(" (", style="dim")
            conf_text.append(f"{vuln.confidence:.0%}", style=confidence_style)
            conf_text.append(" confidence)", style="dim")
            
            # Print with enhanced formatting
            timestamp = self._get_relative_time()
            icon = AGENT_ICONS.get(agent_name, "•")
            color = AGENT_COLORS.get(agent_name, "white")
            sev_style = SEVERITY_COLORS.get(vuln.severity, "white")
            
            header = Text()
            header.append(f"{icon} ", style=color)
            header.append(f"[{agent_name}]", style=f"bold {color}")
            header.append(f" {timestamp}", style="dim")
            header.append(f" [{vuln.severity}]", style=sev_style)
            header.append(conf_text)
            
            self.console.print(header)
            self.console.print(f"   {content}")
            self.console.print()
        else:
            content += f" (confidence: {vuln.confidence:.0%})"
            self.print_event(
                agent_name,
                "vulnerability",
                content,
                severity=vuln.severity
            )
        
        if self.mode == "debug":
            self.console.print(f"   Description: {vuln.description}")
            self.console.print(f"   Attack Vector: {vuln.attack_vector}")
    
    def print_patch(self, patch: Patch, vuln: Optional[Vulnerability] = None) -> None:
        """Print a patch from Defender."""
        content = patch.fix_description
        if vuln:
            content = f"Patched: {vuln.title}"
        
        self.print_event("Defender", "patch", content)
    
    def print_judge_decision(self, decision: str, reason: str) -> None:
        """Print a Judge decision."""
        self.print_event("Judge", "decision", f"{decision}: {reason}")
    
    def print_termination(self, state: CrucibleState) -> None:
        """Print the final termination status."""
        if self.mode == "json":
            event = {
                "event": "termination",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "state": state.status,
                "reason": state.termination_reason,
            }
            self.console.print(json.dumps(event))
            return
        
        status_style = STATUS_COLORS.get(state.status, "white")
        
        self.console.print()
        self.console.print(Panel(
            Text(f"Status: {state.status}\n{state.termination_reason or ''}", style=status_style),
            title="⚖️ FINAL VERDICT",
            border_style=status_style.replace("bold ", ""),
            box=box.HEAVY,
        ))
    
    def print_iteration_separator(self, iteration: int, max_iterations: int) -> None:
        """Print a visual separator between iterations."""
        if self.mode != "war_room":
            return
        
        progress_pct = (iteration / max_iterations) * 100 if max_iterations > 0 else 0
        bar_width = 30
        filled = int(bar_width * iteration / max_iterations) if max_iterations > 0 else 0
        bar = "━" * filled + "─" * (bar_width - filled)
        
        separator = Text()
        separator.append("\n" + "═" * 60 + "\n", style="dim cyan")
        separator.append(f"  ITERATION {iteration}/{max_iterations}  ", style="bold cyan")
        separator.append(f"[{bar}] {progress_pct:.0f}%", style="cyan")
        separator.append("\n" + "═" * 60 + "\n", style="dim cyan")
        
        self.console.print(separator)
    
    def print_summary_table(self, state: CrucibleState) -> None:
        """Print the summary table at end of run."""
        if self.mode == "json":
            return
        
        if not state.vulnerabilities:
            return
        
        table = Table(
            title="📋 Vulnerability Summary",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        
        table.add_column("Iter", style="dim", justify="center")
        table.add_column("ID", style="dim", justify="center")
        table.add_column("Domain", justify="center")
        table.add_column("Severity", justify="center")
        table.add_column("Title")
        table.add_column("Confidence", justify="center")
        table.add_column("Outcome", justify="center")
        
        patched_ids = {p.target_vulnerability_id for p in state.patches}
        
        # Statistics
        total = len(state.vulnerabilities)
        patched = len(patched_ids)
        critical = sum(1 for v in state.vulnerabilities if v.severity == "CRITICAL")
        high = sum(1 for v in state.vulnerabilities if v.severity == "HIGH")
        
        for vuln in state.vulnerabilities:
            sev_style = SEVERITY_COLORS.get(vuln.severity, "white")
            outcome = "✅ PATCHED" if vuln.vulnerability_id in patched_ids else "⚠️  OPEN"
            outcome_style = "green" if outcome.startswith("✅") else "yellow"
            
            # Confidence color
            conf_style = "green" if vuln.confidence >= 0.8 else "yellow" if vuln.confidence >= 0.6 else "red"
            
            table.add_row(
                str(vuln.iteration_found),
                str(vuln.vulnerability_id),
                vuln.domain,
                Text(vuln.severity, style=sev_style),
                vuln.title[:45] + ("..." if len(vuln.title) > 45 else ""),
                Text(f"{vuln.confidence:.0%}", style=conf_style),
                Text(outcome, style=outcome_style),
            )
        
        # Add statistics row
        table.add_row(
            "",
            "",
            Text("TOTALS", style="bold"),
            Text(f"{critical}C / {high}H", style="bold"),
            Text(f"{total} total issues", style="bold"),
            "",
            Text(f"{patched}/{total} fixed", style="bold green" if patched == total else "bold yellow"),
        )
        
        self.console.print()
        self.console.print(table)
    
    def print_error(self, error_code: str, message: str) -> None:
        """Print an error message."""
        if self.mode == "json":
            event = {
                "event": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_code": error_code,
                "message": message,
            }
            self.console.print(json.dumps(event))
            return
        
        self.console.print(Panel(
            Text(f"{error_code}\n{message}", style="red"),
            title="❌ ERROR",
            border_style="red",
            box=box.HEAVY,
        ))
    
    def print_metrics(self, metrics_summary: str) -> None:
        """Print run metrics summary."""
        if self.mode == "json":
            return
        
        self.console.print()
        self.console.print(Panel(
            Text(metrics_summary, style="dim"),
            title="📊 Run Statistics",
            border_style="dim",
            box=box.ROUNDED,
        ))
    
    def print_design_diff(self, old_design: str, new_design: str, iteration: int) -> None:
        """Print a diff between two designs."""
        if self.mode == "json":
            return
        
        if self.mode != "debug":
            # Only show in debug mode
            return
        
        import difflib
        
        old_lines = old_design.splitlines(keepends=True)
        new_lines = new_design.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"design_v{iteration}",
            tofile=f"design_v{iteration + 1}",
            lineterm=""
        )
        
        diff_text = "".join(diff)
        if diff_text:
            self.console.print(f"\n--- Design Changes (Iteration {iteration}) ---")
            for line in diff_text.split("\n")[:30]:  # Limit to 30 lines
                if line.startswith("+") and not line.startswith("+++"):
                    self.console.print(f"[green]{line}[/green]")
                elif line.startswith("-") and not line.startswith("---"):
                    self.console.print(f"[red]{line}[/red]")
                else:
                    self.console.print(f"[dim]{line}[/dim]")
            self.console.print("--- End Design Changes ---\n")
    
    def print_progress(self, current: int, total: int, phase: str) -> None:
        """Print a progress indicator."""
        if self.mode != "war_room":
            return
        
        pct = (current / total) * 100 if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        
        self.console.print(f"[dim]{phase}: [{bar}] {pct:.0f}%[/dim]", end="\r")
    
    def show_spinner(self, message: str) -> None:
        """Show a loading spinner with message."""
        if self.mode != "war_room":
            return
        
        spinner = Spinner("dots", text=Text(message, style="cyan"))
        self.console.print(spinner, end="\r")
    
    def print_welcome_banner(self) -> None:
        """Print welcome banner at start."""
        if self.mode != "war_room":
            return
        
        banner = Text()
        banner.append("\n")
        banner.append("  ⚔️  ═══════════════════════════════════════════════════ ⚔️ \n", style="bold cyan")
        banner.append("         ", style="cyan")
        banner.append("THE CRUCIBLE", style="bold bright_cyan")
        banner.append(" - Adversarial Reasoning Engine\n", style="cyan")
        banner.append("  ⚔️  ═══════════════════════════════════════════════════ ⚔️ ", style="bold cyan")
        
        self.console.print(banner)
        self.console.print()
    
    def print_completion_celebration(self, state: CrucibleState) -> None:
        """Print celebration message on successful completion."""
        if self.mode != "war_room" or state.status != "STABLE":
            return
        
        celebration = Panel(
            Text("\n🎉 System hardened successfully! All vulnerabilities addressed. 🎉\n", 
                 justify="center", style="bold green"),
            border_style="green",
            box=box.DOUBLE,
        )
        self.console.print(celebration)
    
    def show_agent_activity(self, agent: str, status: str) -> None:
        """Show real-time agent activity status."""
        if self.mode != "war_room":
            return
        
        timestamp = self._get_relative_time()
        icon = AGENT_ICONS.get(agent, "•")
        color = AGENT_COLORS.get(agent, "white")
        
        # Show activity with spinner effect
        self.console.print(
            f"{icon} [{agent}] {timestamp} {status}...",
            style=f"dim {color}",
            end="\r"
        )
    
    def clear_agent_activity(self) -> None:
        """Clear the agent activity line."""
        if self.mode == "war_room":
            self.console.print(" " * 80, end="\r")
