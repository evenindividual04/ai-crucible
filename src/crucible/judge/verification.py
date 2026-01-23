"""
Patch verification heuristics for the AI Crucible.

Implements diff-based and pattern-based verification as defined in verification.md.
"""

import difflib
import re
from typing import List, Optional, Set
import logging

from crucible.config import get_config, CrucibleConfig
from crucible.state import Vulnerability, Patch

logger = logging.getLogger(__name__)


# Domain-specific patterns from verification.md
DOMAIN_PATTERNS: dict[str, dict[str, Set[str]]] = {
    "SECURITY": {
        "SQL Injection": {"parameterized", "prepared_statement", "escape", "sanitize", "orm"},
        "XSS": {"escape_html", "sanitize", "content-security-policy", "dompurify"},
        "Auth Bypass": {"authenticate", "authorize", "validate_token", "session_check"},
        "CSRF": {"csrf_token", "samesite", "origin-check"},
        "Rate Limiting": {"rate_limit", "throttle", "quota", "backoff"},
    },
    "SCALABILITY": {
        "Race Condition": {"atomic", "lock", "mutex", "transaction", "cas", "idempotent"},
        "Bottleneck": {"cache", "cdn", "replica", "read_replica", "shard"},
        "Memory Leak": {"cleanup", "dispose", "close", "context_manager", "with"},
        "OOM Risk": {"pagination", "streaming", "chunk", "limit", "cap"},
    },
    "COST": {
        "API Overuse": {"cache", "batch", "throttle", "quota"},
        "Storage Bloat": {"ttl", "expiration", "cleanup", "archive", "compress"},
        "Compute Spike": {"queue", "async", "background", "rate_limit"},
    },
    "LOGIC": {
        "Deadlock": {"ordering", "timeout", "try_lock", "hierarchy"},
        "State Corruption": {"transaction", "rollback", "checkpoint", "validate"},
        "Ordering Issue": {"sequence", "timestamp", "vector_clock", "barrier"},
    },
}


class PatchVerifier:
    """
    Verifies patches using heuristic checks.
    
    Implements:
    - Diff-based impact detection
    - Pattern-based fix verification
    - Regression detection
    """
    
    def __init__(self, config: Optional[CrucibleConfig] = None):
        self.config = config or get_config()
    
    def verify_patch_impact(
        self,
        old_design: str,
        new_design: str,
        patch: Patch
    ) -> tuple[bool, str]:
        """
        Verify that a patch made a meaningful change.
        
        Returns (is_effective, reason).
        """
        # Check diff thresholds
        diff = self._compute_diff(old_design, new_design)
        
        chars_changed = diff["chars_added"] + diff["chars_removed"]
        lines_changed = diff["lines_added"] + diff["lines_removed"]
        
        min_chars = self.config.verification.min_diff_chars
        min_lines = self.config.verification.min_diff_lines
        
        if chars_changed >= min_chars or lines_changed >= min_lines:
            return True, f"Changed {chars_changed} chars, {lines_changed} lines"
        
        return False, f"Insufficient change: {chars_changed} chars, {lines_changed} lines"
    
    def _compute_diff(self, old_text: str, new_text: str) -> dict:
        """Compute diff statistics between two texts."""
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        differ = difflib.unified_diff(old_lines, new_lines, lineterm='')
        diff_lines = list(differ)
        
        lines_added = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        lines_removed = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
        
        chars_added = sum(len(line) - 1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        chars_removed = sum(len(line) - 1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
        
        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "chars_added": chars_added,
            "chars_removed": chars_removed,
        }
    
    def check_pattern_fix(
        self,
        new_design: str,
        vulnerability: Vulnerability
    ) -> tuple[bool, List[str]]:
        """
        Check if the new design contains patterns that indicate a fix.
        
        Returns (found_pattern, matched_keywords).
        """
        domain = vulnerability.domain
        patterns = DOMAIN_PATTERNS.get(domain, {})
        
        if not patterns:
            return False, []
        
        new_design_lower = new_design.lower()
        matched_keywords: List[str] = []
        
        # Check all pattern categories for this domain
        for category, keywords in patterns.items():
            for keyword in keywords:
                if keyword in new_design_lower:
                    matched_keywords.append(keyword)
        
        return bool(matched_keywords), matched_keywords
    
    def detect_regression(
        self,
        new_design: str,
        patched_vulnerabilities: List[Vulnerability]
    ) -> List[Vulnerability]:
        """
        Detect if patched vulnerabilities might be reintroduced.
        
        Returns list of potentially regressed vulnerabilities.
        """
        regressed: List[Vulnerability] = []
        new_design_lower = new_design.lower()
        
        for vuln in patched_vulnerabilities:
            # Extract keywords from the vulnerability
            vuln_keywords = self._extract_vulnerability_keywords(vuln)
            
            # Check if negative patterns are present
            anti_patterns = self._get_anti_patterns(vuln.domain)
            
            for pattern in anti_patterns:
                if pattern in new_design_lower:
                    # This might indicate regression
                    logger.warning(
                        f"Potential regression detected: {pattern} found in design "
                        f"(related to patched vulnerability: {vuln.title})"
                    )
                    regressed.append(vuln)
                    break
        
        return regressed
    
    def _extract_vulnerability_keywords(self, vuln: Vulnerability) -> Set[str]:
        """Extract key terms from a vulnerability for matching."""
        text = f"{vuln.title} {vuln.description} {vuln.attack_vector}".lower()
        # Simple word extraction
        words = re.findall(r'\b\w{4,}\b', text)
        return set(words)
    
    def _get_anti_patterns(self, domain: str) -> Set[str]:
        """Get patterns that indicate potential vulnerability."""
        anti_patterns: dict[str, Set[str]] = {
            "SECURITY": {
                "string concatenation", "exec(", "eval(",
                "disable_security", "skip_auth", "no_validation",
            },
            "SCALABILITY": {
                "single instance", "no caching", "synchronous",
                "unbounded", "no limit",
            },
            "COST": {
                "unlimited", "no quota", "uncapped",
            },
            "LOGIC": {
                "no transaction", "no validation", "skip check",
            },
        }
        return anti_patterns.get(domain, set())
