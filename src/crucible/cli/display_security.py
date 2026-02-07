"""
Additional display methods for security metrics.

Extends CrucibleDisplay with security scoring visualization.
"""

from crucible.cli.display import CrucibleDisplay
from rich.panel import Panel


# Patch the display class with security score method
def print_security_score(self, security_score, improvement=None):
    """
    Print security score with visual indicators.
    
    Args:
        security_score: SecurityScore object
        improvement: Score change from previous iteration (None if first)
    """
    if self.mode == "json":
        return
    
    score = security_score.overall_score
    grade = security_score.letter_grade
    risk = security_score.risk_level
    
    # Color based on grade
    if score >= 90:
        score_color = "green"
    elif score >= 80:
        score_color = "yellow"
    elif score >= 70:
        score_color = "orange"
    else:
        score_color = "red"
    
    risk_icons = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🟢",
        "SECURE": "✅",
    }
    
    # Build header
    header = f"[bold]{risk_icons.get(risk, '📊')} SECURITY SCORE: [{score_color}]{score:.0f}/100 ({grade})[/{score_color}]"
    
    if improvement is not None:
        if improvement > 0:
            header += f" [green]⬆️ +{improvement:.0f}[/green]"
        elif improvement < 0:
            header += f" [red]⬇️ {improvement:.0f}[/red]"
        else:
            header += " [dim]→[/dim]"
    
    # Build vulnerability breakdown
    lines = [header, ""]
    lines.append(f"Risk Level: {risk}")
    lines.append("")
    lines.append("Unpatched:")
    lines.append(f"  🔴 {security_score.unpatched_critical} CRITICAL  🟠 {security_score.unpatched_high} HIGH  🟡 {security_score.unpatched_medium} MEDIUM  🟢 {security_score.unpatched_low} LOW")
    
    effectiveness_pct = security_score.patch_effectiveness * 100
    coverage_pct = security_score.component_coverage * 100
    
    lines.append(f"Patched: {security_score.patched_count}/{security_score.total_vulnerabilities} ({effectiveness_pct:.0f}%) | Coverage: {coverage_pct:.0f}%")
    
    panel = Panel(
        "\n".join(lines),
        border_style=score_color,
        padding=(0, 2),
    )
    
    self.console.print(panel)


# Monkey-patch the method onto CrucibleDisplay
CrucibleDisplay.print_security_score = print_security_score
