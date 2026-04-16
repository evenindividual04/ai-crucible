"""
Vulnerability deduplication for AI Crucible.

Detects and merges semantically similar vulnerabilities to reduce noise
and avoid redundant patching efforts.
"""

from typing import List, Tuple, Set
from crucible.state import Vulnerability
import hashlib
import logging

logger = logging.getLogger(__name__)


class VulnerabilityDeduplicator:
    """
    Detects and merges duplicate vulnerabilities using semantic similarity.
    
    Uses heuristic matching based on domain, severity, title, and affected
    components. Can be upgraded to use LLM embeddings for better accuracy.
    """
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize deduplicator.
        
        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider duplicates
        """
        self.threshold = similarity_threshold
    
    def compute_fingerprint(self, vuln: Vulnerability) -> str:
        """
        Compute a unique fingerprint for exact matching.
        
        Args:
            vuln: Vulnerability to fingerprint
            
        Returns:
            MD5 hash of key vulnerability attributes
        """
        # Normalize title and create key
        key = f"{vuln.severity}:{vuln.domain}:{vuln.title.lower().strip()}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _normalize_text(self, text: str) -> Set[str]:
        """Normalize text to word set for comparison."""
        # Simple normalization - convert to lowercase, split on whitespace/punctuation
        import re
        words = re.findall(r'\w+', text.lower())
        return set(words)
    
    def semantic_similarity(self, v1: Vulnerability, v2: Vulnerability) -> float:
        """
        Compute semantic similarity between two vulnerabilities.
        
        Uses weighted heuristics:
        - Domain match: 20%
        - Severity match: 30%
        - Title overlap: 30%
        - Component overlap: 20%
        
        Args:
            v1, v2: Vulnerabilities to compare
            
        Returns:
            Similarity score between 0 and 1
        """
        score = 0.0
        
        # Domain match (20% weight)
        if v1.domain == v2.domain:
            score += 0.2
        else:
            # Different domains = likely different issues
            return 0.0
        
        # Severity match (30% weight)
        if v1.severity == v2.severity:
            score += 0.3
        elif abs(self._severity_rank(v1.severity) - self._severity_rank(v2.severity)) == 1:
            # Adjacent severities get partial credit
            score += 0.15
        
        # Title similarity (30% weight)
        title1_words = self._normalize_text(v1.title)
        title2_words = self._normalize_text(v2.title)
        
        if title1_words and title2_words:
            title_intersection = len(title1_words & title2_words)
            title_union = len(title1_words | title2_words)
            title_jaccard = title_intersection / title_union if title_union > 0 else 0
            score += 0.3 * title_jaccard
        
        # Component overlap (20% weight)
        comp1 = set(v1.affected_components)
        comp2 = set(v2.affected_components)
        
        if comp1 and comp2:
            comp_intersection = len(comp1 & comp2)
            comp_union = len(comp1 | comp2)
            comp_jaccard = comp_intersection / comp_union if comp_union > 0 else 0
            score += 0.2 * comp_jaccard
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _severity_rank(self, severity: str) -> int:
        """Convert severity to numeric rank for comparison."""
        ranks = {
            "CRITICAL": 4,
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1
        }
        return ranks.get(severity, 0)
    
    def find_duplicates(
        self, 
        new_vulns: List[Vulnerability],
        existing_vulns: List[Vulnerability],
        skip_patched: bool = True
    ) -> List[Tuple[Vulnerability, Vulnerability, float]]:
        """
        Find duplicates between new and existing vulnerabilities.
        
        Args:
            new_vulns: Newly discovered vulnerabilities
            existing_vulns: Previously discovered vulnerabilities
            skip_patched: If True, don't match against patched vulnerabilities
            
        Returns:
            List of (new_vuln, existing_vuln, similarity_score) tuples
        """
        duplicates = []
        
        # Build fingerprint index for fast exact matching
        fingerprint_map = {}
        for existing_v in existing_vulns:
            # Skip if patched and skip_patched is True
            if skip_patched and getattr(existing_v, 'is_patched', False):
                continue
            
            fingerprint = self.compute_fingerprint(existing_v)
            if fingerprint not in fingerprint_map:
                fingerprint_map[fingerprint] = []
            fingerprint_map[fingerprint].append(existing_v)
        
        # Check each new vulnerability
        for new_v in new_vulns:
            # First check for exact fingerprint match
            new_fingerprint = self.compute_fingerprint(new_v)
            if new_fingerprint in fingerprint_map:
                # Exact match found
                for existing_v in fingerprint_map[new_fingerprint]:
                    duplicates.append((new_v, existing_v, 1.0))
                continue
            
            # No exact match, check semantic similarity
            best_match = None
            best_score = 0.0
            
            for existing_v in existing_vulns:
                if skip_patched and getattr(existing_v, 'is_patched', False):
                    continue
                
                similarity = self.semantic_similarity(new_v, existing_v)
                
                if similarity >= self.threshold and similarity > best_score:
                    best_match = existing_v
                    best_score = similarity
            
            if best_match is not None:
                duplicates.append((new_v, best_match, best_score))
        
        return duplicates
    
    def merge_vulnerabilities(
        self, 
        v1: Vulnerability, 
        v2: Vulnerability
    ) -> Vulnerability:
        """
        Merge two similar vulnerabilities, keeping the best data from each.
        
        Args:
            v1, v2: Vulnerabilities to merge
            
        Returns:
            Merged vulnerability
        """
        # Start with the higher confidence vulnerability
        if v1.confidence_score >= v2.confidence_score:
            merged = v1.model_copy(deep=True)
            other = v2
        else:
            merged = v2.model_copy(deep=True)
            other = v1
        
        # Enhance description with note about duplication
        if merged.description != other.description:
            merged.description = (
                f"{merged.description}\n\n"
                f"**Also reported as:** {other.title}\n"
                f"{other.description}"
            )
        
        # Combine attack vectors if different
        if hasattr(merged, 'attack_vector') and hasattr(other, 'attack_vector'):
            if merged.attack_vector != other.attack_vector:
                merged.attack_vector = f"{merged.attack_vector} | {other.attack_vector}"
        
        # Merge affected components (union)
        all_components = list(set(merged.affected_components + other.affected_components))
        merged.affected_components = all_components
        
        # Use higher severity if different
        if self._severity_rank(other.severity) > self._severity_rank(merged.severity):
            merged.severity = other.severity
        
        # Use higher confidence
        merged.confidence = max(merged.confidence, other.confidence)
        
        return merged
    
    def filter_duplicates(
        self,
        new_vulns: List[Vulnerability],
        existing_vulns: List[Vulnerability]
    ) -> Tuple[List[Vulnerability], List[Tuple[Vulnerability, Vulnerability, float]]]:
        """
        Filter out duplicate vulnerabilities from a new set.
        
        Args:
            new_vulns: Newly discovered vulnerabilities
            existing_vulns: Previously discovered vulnerabilities
            
        Returns:
            (unique_vulnerabilities, duplicate_matches) tuple
        """
        duplicates = self.find_duplicates(new_vulns, existing_vulns)
        
        # Build set of duplicate new vulnerability IDs
        duplicate_ids = {new_v.vulnerability_id for new_v, _, _ in duplicates}
        
        # Filter to unique vulnerabilities only
        unique_vulns = [v for v in new_vulns if v.vulnerability_id not in duplicate_ids]
        
        logger.info(
            f"Deduplication: {len(new_vulns)} new -> {len(unique_vulns)} unique, "
            f"{len(duplicates)} duplicates filtered"
        )
        
        return unique_vulns, duplicates
