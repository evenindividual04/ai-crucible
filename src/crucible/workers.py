"""
Worker pool for the AI Crucible.

Provides pre-warmed agents and parallel execution utilities.
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar
import multiprocessing as mp

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class WorkerResult:
    """Result from a worker task."""
    
    worker_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0


class AgentPool:
    """
    Pool of pre-warmed agents for parallel execution.
    
    Reduces startup time by keeping agents ready.
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._agents: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._initialized = False
    
    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor
    
    def prewarm(self, agent_classes: List[type]) -> None:
        """
        Pre-initialize agent instances.
        
        Call this early in the run to have agents ready.
        """
        def _init_agent(agent_class: type) -> None:
            try:
                agent = agent_class()
                with self._lock:
                    self._agents[agent_class.__name__] = agent
                logger.debug(f"Pre-warmed agent: {agent_class.__name__}")
            except Exception as e:
                logger.warning(f"Failed to pre-warm {agent_class.__name__}: {e}")
        
        # Initialize agents in parallel
        executor = self._get_executor()
        futures = [executor.submit(_init_agent, cls) for cls in agent_classes]
        
        # Wait for all to complete
        for future in futures:
            future.result()
        
        self._initialized = True
        logger.info(f"Pre-warmed {len(self._agents)} agents")
    
    def get_agent(self, agent_class: type) -> Any:
        """
        Get a pre-warmed agent or create a new one.
        """
        name = agent_class.__name__
        
        with self._lock:
            if name in self._agents:
                return self._agents[name]
        
        # Create new instance
        agent = agent_class()
        with self._lock:
            self._agents[name] = agent
        
        return agent
    
    async def run_agents_parallel(
        self,
        agent_classes: List[type],
        invoke_fn: Callable[[Any], Any],
        **kwargs: Any,
    ) -> List[WorkerResult]:
        """
        Run multiple agents in parallel.
        
        Args:
            agent_classes: List of agent classes to run
            invoke_fn: Async function that takes an agent and returns a result
            **kwargs: Arguments passed to invoke_fn
        
        Returns:
            List of WorkerResult objects
        """
        import time
        
        async def _run_agent(agent_class: type) -> WorkerResult:
            name = agent_class.__name__
            start_time = time.time()
            
            try:
                agent = self.get_agent(agent_class)
                result = await invoke_fn(agent, **kwargs)
                
                return WorkerResult(
                    worker_id=name,
                    success=True,
                    result=result,
                    duration_ms=(time.time() - start_time) * 1000,
                )
                
            except Exception as e:
                return WorkerResult(
                    worker_id=name,
                    success=False,
                    error=str(e),
                    duration_ms=(time.time() - start_time) * 1000,
                )
        
        # Run all agents concurrently
        tasks = [_run_agent(cls) for cls in agent_classes]
        return await asyncio.gather(*tasks)
    
    def shutdown(self) -> None:
        """Shutdown the pool."""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        self._agents.clear()
        self._initialized = False


class BackgroundLoader:
    """
    Utility for loading resources in the background.
    
    Used for lazy model loading.
    """
    
    def __init__(self):
        self._threads: Dict[str, threading.Thread] = {}
        self._results: Dict[str, Any] = {}
        self._errors: Dict[str, Exception] = {}
        self._lock = threading.Lock()
    
    def start_loading(
        self,
        name: str,
        loader_fn: Callable[[], T],
        on_complete: Optional[Callable[[T], None]] = None,
    ) -> None:
        """
        Start loading a resource in the background.
        
        Args:
            name: Unique name for this resource
            loader_fn: Function that loads and returns the resource
            on_complete: Optional callback when loading completes
        """
        def _load():
            try:
                result = loader_fn()
                with self._lock:
                    self._results[name] = result
                if on_complete:
                    on_complete(result)
                logger.debug(f"Background loading complete: {name}")
            except Exception as e:
                with self._lock:
                    self._errors[name] = e
                logger.warning(f"Background loading failed: {name}: {e}")
        
        thread = threading.Thread(target=_load, daemon=True, name=f"loader-{name}")
        
        with self._lock:
            self._threads[name] = thread
        
        thread.start()
        logger.debug(f"Started background loading: {name}")
    
    def get_result(self, name: str, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get the result of a background load.
        
        Args:
            name: Name of the resource
            timeout: Max seconds to wait (None = wait forever)
        
        Returns:
            The loaded resource, or None if not ready/failed
        """
        with self._lock:
            thread = self._threads.get(name)
        
        if thread is None:
            return None
        
        # Wait for thread to complete
        thread.join(timeout=timeout)
        
        with self._lock:
            if name in self._errors:
                raise self._errors[name]
            return self._results.get(name)
    
    def is_ready(self, name: str) -> bool:
        """Check if a resource is ready."""
        with self._lock:
            return name in self._results
    
    def wait_all(self, timeout: Optional[float] = None) -> None:
        """Wait for all background loads to complete."""
        with self._lock:
            threads = list(self._threads.values())
        
        for thread in threads:
            thread.join(timeout=timeout)


# Global instances
_agent_pool: Optional[AgentPool] = None
_background_loader: Optional[BackgroundLoader] = None


def get_agent_pool(max_workers: int = 4) -> AgentPool:
    """Get or create the global agent pool."""
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = AgentPool(max_workers=max_workers)
    return _agent_pool


def get_background_loader() -> BackgroundLoader:
    """Get or create the global background loader."""
    global _background_loader
    if _background_loader is None:
        _background_loader = BackgroundLoader()
    return _background_loader


def prewarm_resources() -> None:
    """
    Pre-warm all resources needed for a Crucible run.
    
    Call this early in the CLI to reduce startup latency.
    """
    from crucible.cache import EmbeddingCache, get_embedding_cache
    from crucible.agents import (
        ArchitectAgent,
        SecurityHawk,
        ScaleMonster,
        CostAnalyst,
        LogicBreaker,
        DefenderAgent,
    )
    
    loader = get_background_loader()
    
    # Pre-load embedding model in background
    loader.start_loading(
        "embedding_model",
        lambda: EmbeddingCache.get_model(),
    )
    
    # Pre-warm agents
    pool = get_agent_pool()
    pool.prewarm([
        ArchitectAgent,
        SecurityHawk,
        ScaleMonster,
        CostAnalyst,
        LogicBreaker,
        DefenderAgent,
    ])
    
    logger.info("All resources pre-warming started")
