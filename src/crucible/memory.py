"""
Agent Memory for the AI Crucible.

Allows agents to reference findings from previous runs for better attacks/defenses.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    """Summary of a completed Crucible run."""
    
    run_id: str
    timestamp: datetime
    prompt: str
    iterations: int
    final_status: str
    
    # Vulnerability summary
    total_vulnerabilities: int
    critical_count: int
    high_count: int
    patched_count: int
    unresolved_count: int
    
    # By domain
    vulnerabilities_by_domain: Dict[str, int] = field(default_factory=dict)
    
    # Top issues (titles only for pattern matching)
    top_vulnerability_titles: List[str] = field(default_factory=list)
    
    # Effective patches
    effective_patch_descriptions: List[str] = field(default_factory=list)


@dataclass
class VulnerabilityPattern:
    """A pattern of vulnerabilities seen across runs."""
    
    title_pattern: str  # Normalized title
    occurrences: int
    domains: List[str]
    avg_severity: str
    successful_fix_rate: float
    common_fixes: List[str]


@dataclass
class DefensePattern:
    """A pattern of successful defenses."""
    
    vulnerability_type: str
    fix_description: str
    success_count: int
    failure_count: int
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0


class AgentMemory:
    """
    Persistent memory for agents across runs.
    
    Stores patterns of:
    - Common vulnerabilities
    - Effective patches
    - Attack strategies that work
    """
    
    def __init__(self, memory_path: Optional[Path] = None):
        self.memory_path = memory_path or Path.home() / ".crucible" / "memory.json"
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._runs: List[RunSummary] = []
        self._vulnerability_patterns: Dict[str, VulnerabilityPattern] = {}
        self._defense_patterns: Dict[str, DefensePattern] = {}
        
        self._load()
    
    def _load(self) -> None:
        """Load memory from disk."""
        if not self.memory_path.exists():
            return
        
        try:
            with open(self.memory_path) as f:
                data = json.load(f)
            
            self._runs = [
                RunSummary(**r) for r in data.get("runs", [])
            ]
            
            for pattern_data in data.get("vulnerability_patterns", []):
                pattern = VulnerabilityPattern(**pattern_data)
                self._vulnerability_patterns[pattern.title_pattern] = pattern
            
            for pattern_data in data.get("defense_patterns", []):
                pattern = DefensePattern(**pattern_data)
                self._defense_patterns[pattern.vulnerability_type] = pattern
            
            logger.info(f"Loaded memory: {len(self._runs)} runs, "
                       f"{len(self._vulnerability_patterns)} vuln patterns")
            
        except Exception as e:
            logger.warning(f"Failed to load memory: {e}")
    
    def _save(self) -> None:
        """Save memory to disk."""
        try:
            data = {
                "runs": [
                    {
                        "run_id": r.run_id,
                        "timestamp": r.timestamp.isoformat(),
                        "prompt": r.prompt,
                        "iterations": r.iterations,
                        "final_status": r.final_status,
                        "total_vulnerabilities": r.total_vulnerabilities,
                        "critical_count": r.critical_count,
                        "high_count": r.high_count,
                        "patched_count": r.patched_count,
                        "unresolved_count": r.unresolved_count,
                        "vulnerabilities_by_domain": r.vulnerabilities_by_domain,
                        "top_vulnerability_titles": r.top_vulnerability_titles,
                        "effective_patch_descriptions": r.effective_patch_descriptions,
                    }
                    for r in self._runs[-100:]  # Keep last 100 runs
                ],
                "vulnerability_patterns": [
                    {
                        "title_pattern": p.title_pattern,
                        "occurrences": p.occurrences,
                        "domains": p.domains,
                        "avg_severity": p.avg_severity,
                        "successful_fix_rate": p.successful_fix_rate,
                        "common_fixes": p.common_fixes,
                    }
                    for p in self._vulnerability_patterns.values()
                ],
                "defense_patterns": [
                    {
                        "vulnerability_type": p.vulnerability_type,
                        "fix_description": p.fix_description,
                        "success_count": p.success_count,
                        "failure_count": p.failure_count,
                    }
                    for p in self._defense_patterns.values()
                ],
            }
            
            with open(self.memory_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.debug(f"Saved memory to {self.memory_path}")
            
        except Exception as e:
            logger.warning(f"Failed to save memory: {e}")
    
    def record_run(self, summary: RunSummary) -> None:
        """Record a completed run."""
        self._runs.append(summary)
        
        # Update patterns
        for title in summary.top_vulnerability_titles:
            normalized = self._normalize_title(title)
            if normalized in self._vulnerability_patterns:
                self._vulnerability_patterns[normalized].occurrences += 1
            else:
                self._vulnerability_patterns[normalized] = VulnerabilityPattern(
                    title_pattern=normalized,
                    occurrences=1,
                    domains=[],
                    avg_severity="MEDIUM",
                    successful_fix_rate=0.5,
                    common_fixes=[],
                )
        
        self._save()
    
    def _normalize_title(self, title: str) -> str:
        """Normalize a vulnerability title for pattern matching."""
        # Remove specific identifiers, keep general pattern
        import re
        
        # Remove numbers
        normalized = re.sub(r'\d+', 'N', title)
        # Remove specific component names in brackets
        normalized = re.sub(r'\([^)]+\)', '', normalized)
        # Lowercase and strip
        normalized = normalized.lower().strip()
        
        return normalized
    
    def get_common_vulnerabilities(self, limit: int = 10) -> List[VulnerabilityPattern]:
        """Get the most common vulnerability patterns."""
        patterns = sorted(
            self._vulnerability_patterns.values(),
            key=lambda p: p.occurrences,
            reverse=True
        )
        return patterns[:limit]
    
    def get_effective_fixes(self, vuln_type: str) -> List[str]:
        """Get fixes that have worked for a vulnerability type."""
        normalized = self._normalize_title(vuln_type)
        
        if normalized in self._vulnerability_patterns:
            return self._vulnerability_patterns[normalized].common_fixes
        
        return []
    
    def suggest_attacks(self, design_keywords: List[str]) -> List[str]:
        """Suggest attacks based on historical patterns."""
        suggestions = []
        
        # Find patterns that match the design
        for pattern in self.get_common_vulnerabilities():
            if any(kw.lower() in pattern.title_pattern for kw in design_keywords):
                suggestions.append(f"Check for: {pattern.title_pattern} "
                                  f"(seen {pattern.occurrences}x)")
        
        return suggestions[:5]
    
    def suggest_defenses(self, vulnerabilities: List[str]) -> Dict[str, List[str]]:
        """Suggest defenses based on what has worked before."""
        suggestions = {}
        
        for vuln_title in vulnerabilities:
            fixes = self.get_effective_fixes(vuln_title)
            if fixes:
                suggestions[vuln_title] = fixes
        
        return suggestions
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall memory statistics."""
        if not self._runs:
            return {"runs": 0, "patterns": 0}
        
        total_vulns = sum(r.total_vulnerabilities for r in self._runs)
        total_patched = sum(r.patched_count for r in self._runs)
        
        return {
            "total_runs": len(self._runs),
            "total_vulnerabilities_seen": total_vulns,
            "total_patches_applied": total_patched,
            "overall_patch_rate": total_patched / total_vulns if total_vulns > 0 else 0,
            "unique_patterns": len(self._vulnerability_patterns),
            "most_common_vulns": [p.title_pattern for p in self.get_common_vulnerabilities(5)],
        }
    
    def clear(self) -> None:
        """Clear all memory."""
        self._runs.clear()
        self._vulnerability_patterns.clear()
        self._defense_patterns.clear()
        
        if self.memory_path.exists():
            self.memory_path.unlink()
        
        logger.info("Memory cleared")


# Global memory instance
_memory: Optional[AgentMemory] = None


def get_memory() -> AgentMemory:
    """Get or create the global agent memory."""
    global _memory
    if _memory is None:
        _memory = AgentMemory()
    return _memory


def record_run_to_memory(
    run_id: str,
    prompt: str,
    iterations: int,
    final_status: str,
    vulnerabilities: List[dict],
    patches: List[dict],
) -> None:
    """Convenience function to record a run."""
    memory = get_memory()
    
    critical = sum(1 for v in vulnerabilities if v.get("severity") == "CRITICAL")
    high = sum(1 for v in vulnerabilities if v.get("severity") == "HIGH")
    patched_ids = {p.get("target_vulnerability_id") for p in patches}
    patched = sum(1 for v in vulnerabilities if v.get("vulnerability_id") in patched_ids)
    
    by_domain: Dict[str, int] = {}
    for v in vulnerabilities:
        domain = v.get("domain", "UNKNOWN")
        by_domain[domain] = by_domain.get(domain, 0) + 1
    
    summary = RunSummary(
        run_id=run_id,
        timestamp=datetime.utcnow(),
        prompt=prompt[:200],
        iterations=iterations,
        final_status=final_status,
        total_vulnerabilities=len(vulnerabilities),
        critical_count=critical,
        high_count=high,
        patched_count=patched,
        unresolved_count=len(vulnerabilities) - patched,
        vulnerabilities_by_domain=by_domain,
        top_vulnerability_titles=[v.get("title", "") for v in vulnerabilities[:10]],
        effective_patch_descriptions=[p.get("fix_description", "") for p in patches],
    )
    
    memory.record_run(summary)
