"""
Caching utilities for the AI Crucible.

Provides embedding cache and optional Redis cache for LLM responses.
"""

import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar
import pickle

import numpy as np

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        pass


class FileCache(CacheBackend):
    """File-based cache backend for local caching."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".crucible" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        # Hash the key for safe filenames
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        path = self._get_path(key)
        if not path.exists():
            return None
        
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            
            # Check TTL if present
            if "expires_at" in data and data["expires_at"]:
                if datetime.utcnow() > data["expires_at"]:
                    self.delete(key)
                    return None
            
            return data["value"]
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        path = self._get_path(key)
        
        data = {
            "value": value,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(seconds=ttl) if ttl else None,
        }
        
        try:
            with open(path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def exists(self, key: str) -> bool:
        return self.get(key) is not None
    
    def delete(self, key: str) -> None:
        path = self._get_path(key)
        if path.exists():
            path.unlink()
    
    def clear(self) -> None:
        """Clear all cache files."""
        for f in self.cache_dir.glob("*.cache"):
            f.unlink()


class RedisCache(CacheBackend):
    """Redis-based cache backend for distributed caching."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        prefix: str = "crucible:",
        password: Optional[str] = None,
    ):
        self.prefix = prefix
        self._client = None
        self._connection_params = {
            "host": host,
            "port": port,
            "db": db,
            "password": password,
        }
    
    @property
    def client(self):
        """Lazy initialize Redis client."""
        if self._client is None:
            try:
                import redis
                self._client = redis.Redis(**self._connection_params)
                self._client.ping()  # Test connection
                logger.info("Connected to Redis cache")
            except ImportError:
                logger.warning("redis package not installed. Install with: pip install redis")
                raise
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                raise
        return self._client
    
    def _make_key(self, key: str) -> str:
        """Create a prefixed key."""
        return f"{self.prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        try:
            data = self.client.get(self._make_key(key))
            if data is None:
                return None
            return pickle.loads(data)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            data = pickle.dumps(value)
            if ttl:
                self.client.setex(self._make_key(key), ttl, data)
            else:
                self.client.set(self._make_key(key), data)
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
    
    def exists(self, key: str) -> bool:
        try:
            return self.client.exists(self._make_key(key)) > 0
        except Exception as e:
            logger.warning(f"Redis exists error: {e}")
            return False
    
    def delete(self, key: str) -> None:
        try:
            self.client.delete(self._make_key(key))
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")


class EmbeddingCache:
    """
    Cache for sentence-transformer embeddings.
    
    Caches both the model (in memory) and embeddings (to disk/Redis).
    """
    
    _model_instance = None
    _model_name: Optional[str] = None
    
    def __init__(self, backend: Optional[CacheBackend] = None):
        self.backend = backend or FileCache()
    
    @classmethod
    def get_model(cls, model_name: str = "all-MiniLM-L6-v2"):
        """
        Get or load the sentence-transformer model (singleton).
        
        This keeps the model in memory across calls.
        """
        if cls._model_instance is None or cls._model_name != model_name:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {model_name}")
            cls._model_instance = SentenceTransformer(model_name)
            cls._model_name = model_name
            logger.info("Embedding model loaded")
        return cls._model_instance
    
    @classmethod
    def preload_model(cls, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Preload the model in the background."""
        import threading
        
        def _load():
            cls.get_model(model_name)
        
        thread = threading.Thread(target=_load, daemon=True)
        thread.start()
    
    def _make_key(self, text: str, model_name: str) -> str:
        """Create a cache key for an embedding."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"emb:{model_name}:{text_hash}"
    
    def get_embedding(self, text: str, model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
        """
        Get embedding for text, using cache if available.
        """
        key = self._make_key(text, model_name)
        
        # Check cache
        cached = self.backend.get(key)
        if cached is not None:
            return np.array(cached)
        
        # Compute embedding
        model = self.get_model(model_name)
        embedding = model.encode([text])[0]
        
        # Cache it (embeddings don't expire)
        self.backend.set(key, embedding.tolist())
        
        return embedding
    
    def get_embeddings(
        self,
        texts: List[str],
        model_name: str = "all-MiniLM-L6-v2"
    ) -> np.ndarray:
        """
        Get embeddings for multiple texts, using cache where available.
        
        Batches uncached texts for efficiency.
        """
        results = [None] * len(texts)
        texts_to_encode = []
        indices_to_encode = []
        
        # Check cache for each text
        for i, text in enumerate(texts):
            key = self._make_key(text, model_name)
            cached = self.backend.get(key)
            if cached is not None:
                results[i] = np.array(cached)
            else:
                texts_to_encode.append(text)
                indices_to_encode.append(i)
        
        # Batch encode uncached texts
        if texts_to_encode:
            model = self.get_model(model_name)
            new_embeddings = model.encode(texts_to_encode)
            
            for i, idx in enumerate(indices_to_encode):
                embedding = new_embeddings[i]
                results[idx] = embedding
                
                # Cache it
                key = self._make_key(texts[idx], model_name)
                self.backend.set(key, embedding.tolist())
        
        return np.array(results)


class LLMResponseCache:
    """
    Cache for LLM responses.
    
    Useful for development and testing to avoid repeated API calls.
    """
    
    def __init__(
        self,
        backend: Optional[CacheBackend] = None,
        ttl: int = 3600,  # 1 hour default
        enabled: bool = True,
    ):
        self.backend = backend or FileCache()
        self.ttl = ttl
        self.enabled = enabled
    
    def _make_key(self, prompt: str, model: str, temperature: float) -> str:
        """Create a cache key for an LLM response."""
        content = f"{model}:{temperature}:{prompt}"
        return f"llm:{hashlib.sha256(content.encode()).hexdigest()}"
    
    def get(self, prompt: str, model: str, temperature: float) -> Optional[str]:
        """Get a cached response if available."""
        if not self.enabled:
            return None
        
        key = self._make_key(prompt, model, temperature)
        return self.backend.get(key)
    
    def set(self, prompt: str, model: str, temperature: float, response: str) -> None:
        """Cache a response."""
        if not self.enabled:
            return
        
        key = self._make_key(prompt, model, temperature)
        self.backend.set(key, response, ttl=self.ttl)


# Global cache instances
_embedding_cache: Optional[EmbeddingCache] = None
_llm_cache: Optional[LLMResponseCache] = None


def get_embedding_cache() -> EmbeddingCache:
    """Get or create the global embedding cache."""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache()
    return _embedding_cache


def get_llm_cache() -> LLMResponseCache:
    """Get or create the global LLM response cache."""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMResponseCache()
    return _llm_cache


def init_redis_cache(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
) -> None:
    """Initialize Redis-backed caches."""
    global _embedding_cache, _llm_cache
    
    redis_backend = RedisCache(host=host, port=port, db=db, password=password)
    _embedding_cache = EmbeddingCache(backend=redis_backend)
    _llm_cache = LLMResponseCache(backend=redis_backend)
    
    logger.info("Initialized Redis-backed caches")
