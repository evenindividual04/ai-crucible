"""
Novelty checker for semantic similarity detection.

Uses sentence-transformers to detect duplicate or rephrased vulnerabilities.
"""

from typing import List, Optional
import logging

import numpy as np

from crucible.config import get_config, CrucibleConfig
from crucible.state import Vulnerability

logger = logging.getLogger(__name__)


class NoveltyChecker:
    """
    Checks if vulnerabilities are novel using semantic similarity.
    
    Uses cosine similarity on embeddings from sentence-transformers.
    Falls back to exact match if embedding fails.
    """
    
    def __init__(self, config: Optional[CrucibleConfig] = None):
        self.config = config or get_config()
        self._model = None
        self._model_loaded = False
        self._load_attempted = False
    
    @property
    def threshold(self) -> float:
        """Get the similarity threshold from config."""
        return self.config.similarity.threshold
    
    def _ensure_model(self) -> bool:
        """Lazy load the sentence-transformer model using cache."""
        if self._load_attempted:
            return self._model_loaded
        
        self._load_attempted = True
        
        try:
            # Use centralized embedding cache for model
            from crucible.cache import EmbeddingCache
            
            model_name = self.config.similarity.model
            self._model = EmbeddingCache.get_model(model_name)
            self._model_loaded = True
            return True
            
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Falling back to exact match deduplication."
            )
            return False
        except Exception as e:
            logger.warning(
                f"Failed to load embedding model: {e}. "
                "Falling back to exact match deduplication."
            )
            return False
    
    def is_duplicate(
        self,
        new_vuln: Vulnerability,
        existing_vulns: List[Vulnerability]
    ) -> bool:
        """
        Check if a vulnerability is a duplicate of existing ones.
        
        Returns True if the vulnerability is too similar to an existing one.
        """
        if not existing_vulns:
            return False
        
        new_text = self._get_vuln_text(new_vuln)
        existing_texts = [self._get_vuln_text(v) for v in existing_vulns]
        
        # Try semantic similarity first
        if self._ensure_model():
            return self._semantic_duplicate(new_text, existing_texts)
        
        # Fallback to exact match
        if self.config.similarity.fallback_to_exact:
            return self._exact_duplicate(new_text, existing_texts)
        
        return False
    
    def _get_vuln_text(self, vuln: Vulnerability) -> str:
        """
        Extract the key text for comparison.
        
        Improve deduplication by including:
        - Domain (for same-domain filtering)
        - Title (primary identifier)
        - Attack vector (how it's exploited)
        - First 100 chars of description (for context)
        
        And normalizing the text.
        """
        parts = [
            f"[{vuln.domain}]",
            vuln.title,
            vuln.attack_vector,
            vuln.description[:100] if vuln.description else "",
        ]
        # Normalize: lowercase, remove extra whitespace
        text = " ".join(parts).lower()
        text = " ".join(text.split())  # Collapse whitespace
        return text
    
    def _semantic_duplicate(
        self,
        new_text: str,
        existing_texts: List[str]
    ) -> bool:
        """Check using semantic similarity."""
        if not self._model:
            return False
        
        # Encode all texts
        all_texts = [new_text] + existing_texts
        embeddings = self._model.encode(all_texts)
        
        new_embedding = embeddings[0]
        existing_embeddings = embeddings[1:]
        
        # Compute cosine similarities
        similarities = np.dot(existing_embeddings, new_embedding) / (
            np.linalg.norm(existing_embeddings, axis=1) * np.linalg.norm(new_embedding)
        )
        
        # Check if any similarity exceeds threshold
        max_similarity = float(np.max(similarities))
        is_dup = max_similarity >= self.threshold
        
        if is_dup:
            logger.debug(
                f"Duplicate detected with similarity {max_similarity:.2f} "
                f"(threshold: {self.threshold})"
            )
        
        return is_dup
    
    def _exact_duplicate(
        self,
        new_text: str,
        existing_texts: List[str]
    ) -> bool:
        """Check using exact match (case-insensitive)."""
        new_lower = new_text.lower().strip()
        for existing in existing_texts:
            if existing.lower().strip() == new_lower:
                return True
        return False
    
    def filter_novel(
        self,
        candidates: List[Vulnerability],
        existing: List[Vulnerability]
    ) -> List[Vulnerability]:
        """
        Filter a list of candidates to only novel vulnerabilities.
        
        Also deduplicates within the candidate list.
        """
        novel: List[Vulnerability] = []
        
        for candidate in candidates:
            # Check against existing
            if self.is_duplicate(candidate, existing):
                logger.debug(f"Filtering duplicate: {candidate.title}")
                continue
            
            # Check against already-accepted novel ones
            if self.is_duplicate(candidate, novel):
                logger.debug(f"Filtering internal duplicate: {candidate.title}")
                continue
            
            novel.append(candidate)
        
        return novel
