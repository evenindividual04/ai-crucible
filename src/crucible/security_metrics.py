"""
Security metrics and scoring for AI Crucible.

Calculates security scores, risk levels, and tracks improvement over iterations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional
from crucible.state import CrucibleState, Vulnerability


@dataclass
class SecurityScore:
    """Security score and metrics for a single iteration."""
    
    overall_score: float  # 0-100
    letter_grade: str     # A+, A, B+, B, C, D, F
    risk_level: str       # CRITICAL, HIGH, MEDIUM, LOW, SECURE
    
    # Vulnerability breakdown
    unpatched_critical: int
    unpatched_high: int
    unpatched_medium: int
    unpatched_low: int
    
    patched_count: int
    total_vulnerabilities: int
    patch_effectiveness: float  # 0-1
    
    # Component analysis
    high_risk_components: List[str] = field(default_factory=list)
    component_coverage: float = 0.0  # % of components with no critical issues
    
    # Metadata
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    iteration: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": self.overall_score,
            "letter_grade": self.letter_grade,
            "risk_level": self.risk_level,
            "unpatched_critical": self.unpatched_critical,
            "unpatched_high": self.unpatched_high,
            "unpatched_medium": self.unpatched_medium,
            "unpatched_low": self.unpatched_low,
            "patched_count": self.patched_count,
            "total_vulnerabilities": self.total_vulnerabilities,
            "patch_effectiveness": self.patch_effectiveness,
            "high_risk_components": self.high_risk_components,
            "component_coverage": self.component_coverage,
            "calculated_at": self.calculated_at.isoformat(),
            "iteration": self.iteration,
        }


class SecurityScorer:
    """Calculate security scores and metrics."""
    
    def __init__(self):
        """Initialize the security scorer."""
        # Severity weights for scoring
        self.severity_weights = {
            "CRITICAL": 15,
            "HIGH": 8,
            "MEDIUM": 3,
            "LOW": 1,
        }
    
    def calculate_overall_score(self, state: CrucibleState) -> SecurityScore:
        """
        Calculate comprehensive security score for the current state.
        
        Args:
            state: Current crucible state
            
        Returns:
            SecurityScore with all metrics
        """
        # Get unpatched vulnerabilities
        patched_ids = {p.target_vulnerability_id for p in state.patches}
        unpatched = [v for v in state.vulnerabilities if v.vulnerability_id not in patched_ids]
        
        # Count by severity
        unpatched_critical = sum(1 for v in unpatched if v.severity == "CRITICAL")
        unpatched_high = sum(1 for v in unpatched if v.severity == "HIGH")
        unpatched_medium = sum(1 for v in unpatched if v.severity == "MEDIUM")
        unpatched_low = sum(1 for v in unpatched if v.severity == "LOW")
        
        # Calculate base score (start at 100, deduct for vulnerabilities)
        score = 100.0
        
        for vuln in unpatched:
            weight = self.severity_weights.get(vuln.severity, 1)
            score -= weight
        
        # Bonus for patch effectiveness
        if state.vulnerabilities:
            effectiveness = len(patched_ids) / len(state.vulnerabilities)
            score += effectiveness * 10  # Up to +10 bonus
        else:
            effectiveness = 0.0
        
        # Bonus for component coverage
        if state.design_components:
            safe_components = self._count_safe_components(state, unpatched)
            coverage = safe_components / len(state.design_components)
            score += coverage * 10  # Up to +10 bonus
        else:
            coverage = 0.0
        
        # Clamp to 0-100
        score = max(0, min(100, score))
        
        # Determine letter grade
        letter_grade = self._get_letter_grade(score)
        
        # Determine overall risk level
        risk_level = self._get_risk_level(unpatched_critical, unpatched_high, score)
        
        # Identify high-risk components
        high_risk_components = self._get_high_risk_components(state, unpatched)
        
        return SecurityScore(
            overall_score=score,
            letter_grade=letter_grade,
            risk_level=risk_level,
            unpatched_critical=unpatched_critical,
            unpatched_high=unpatched_high,
            unpatched_medium=unpatched_medium,
            unpatched_low=unpatched_low,
            patched_count=len(patched_ids),
            total_vulnerabilities=len(state.vulnerabilities),
            patch_effectiveness=effectiveness,
            high_risk_components=high_risk_components,
            component_coverage=coverage,
            iteration=state.iteration_count,
        )
    
    def get_component_risk_map(self, state: CrucibleState) -> Dict[str, str]:
        """
        Generate risk level for each component.
        
        Args:
            state: Current crucible state
            
        Returns:
            Dict mapping component name to risk level
        """
        patched_ids = {p.target_vulnerability_id for p in state.patches}
        unpatched = [v for v in state.vulnerabilities if v.vulnerability_id not in patched_ids]
        
        risk_map = {}
        
        for component in state.design_components:
            # Find vulnerabilities affecting this component
            component_vulns = [
                v for v in unpatched 
                if component.name in v.affected_components
            ]
            
            if not component_vulns:
                risk_map[component.name] = "SECURE"
            elif any(v.severity == "CRITICAL" for v in component_vulns):
                risk_map[component.name] = "CRITICAL"
            elif any(v.severity == "HIGH" for v in component_vulns):
                risk_map[component.name] = "HIGH"
            elif any(v.severity == "MEDIUM" for v in component_vulns):
                risk_map[component.name] = "MEDIUM"
            else:
                risk_map[component.name] = "LOW"
        
        return risk_map
    
    def calculate_iteration_delta(self, prev: SecurityScore, curr: SecurityScore) -> float:
        """
        Calculate score improvement between iterations.
        
        Args:
            prev: Previous iteration's score
            curr: Current iteration's score
            
        Returns:
            Score delta (positive = improvement)
        """
        return curr.overall_score - prev.overall_score
    
    def _get_letter_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def _get_risk_level(self, critical: int, high: int, score: float) -> str:
        """Determine overall risk level."""
        if critical > 0 or score < 50:
            return "CRITICAL"
        elif high > 0 or score < 70:
            return "HIGH"
        elif score < 85:
            return "MEDIUM"
        elif score < 95:
            return "LOW"
        else:
            return "SECURE"
    
    def _count_safe_components(self, state: CrucibleState, unpatched: List[Vulnerability]) -> int:
        """Count components with no critical or high vulnerabilities."""
        count = 0
        
        for component in state.design_components:
            component_vulns = [
                v for v in unpatched 
                if component.name in v.affected_components
            ]
            
            # Consider safe if no critical or high vulnerabilities
            has_critical_or_high = any(
                v.severity in ("CRITICAL", "HIGH") 
                for v in component_vulns
            )
            
            if not has_critical_or_high:
                count += 1
        
        return count
    
    def _get_high_risk_components(self, state: CrucibleState, unpatched: List[Vulnerability]) -> List[str]:
        """Identify components with critical or high vulnerabilities."""
        high_risk = []
        
        for component in state.design_components:
            component_vulns = [
                v for v in unpatched 
                if component.name in v.affected_components
            ]
            
            has_critical_or_high = any(
                v.severity in ("CRITICAL", "HIGH") 
                for v in component_vulns
            )
            
            if has_critical_or_high:
                high_risk.append(component.name)
        
        return high_risk
