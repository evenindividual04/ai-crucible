"""
Rate limiting and retry utilities for the AI Crucible.

Provides exponential backoff with jitter for API calls.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, TypeVar, Optional, Any
import re

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RateLimitInfo:
    """Information about a rate limit error."""
    
    is_rate_limited: bool
    retry_after_seconds: Optional[float] = None
    quota_exceeded: bool = False
    daily_limit_hit: bool = False
    message: str = ""


def detect_rate_limit(error: Exception) -> RateLimitInfo:
    """
    Detect if an exception is a rate limit error.
    
    Returns RateLimitInfo with details about the rate limit.
    """
    error_str = str(error).lower()
    
    # Check for rate limit indicators
    rate_limit_keywords = [
        "rate limit",
        "rate_limit",
        "too many requests",
        "429",
        "resource_exhausted",
        "quota exceeded",
        "quota_exceeded",
    ]
    
    is_rate_limited = any(kw in error_str for kw in rate_limit_keywords)
    
    if not is_rate_limited:
        return RateLimitInfo(is_rate_limited=False)
    
    # Try to extract retry delay
    retry_after = None
    
    # Look for "retry in Xs" pattern
    retry_match = re.search(r"retry\s+in\s+([\d.]+)\s*s", error_str)
    if retry_match:
        retry_after = float(retry_match.group(1))
    
    # Look for "retryDelay": "Xs" pattern
    delay_match = re.search(r"retrydelay[\"':]+\s*[\"']?(\d+)", error_str)
    if delay_match:
        retry_after = float(delay_match.group(1))
    
    # Check for daily limit
    daily_limit_hit = "per day" in error_str or "daily" in error_str
    quota_exceeded = "quota" in error_str
    
    return RateLimitInfo(
        is_rate_limited=True,
        retry_after_seconds=retry_after,
        quota_exceeded=quota_exceeded,
        daily_limit_hit=daily_limit_hit,
        message=str(error)[:200],
    )


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: float = 0.1,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int, rate_limit_info: Optional[RateLimitInfo] = None) -> float:
        """
        Calculate the delay before the next retry.
        
        Uses exponential backoff with jitter.
        """
        # If we have a retry-after hint, use it (with some padding)
        if rate_limit_info and rate_limit_info.retry_after_seconds:
            return min(rate_limit_info.retry_after_seconds + 1.0, self.max_delay)
        
        # Exponential backoff
        delay = self.initial_delay * (self.exponential_base ** attempt)
        
        # Add jitter (random factor between 1-jitter and 1+jitter)
        jitter_factor = 1.0 + random.uniform(-self.jitter, self.jitter)
        delay *= jitter_factor
        
        # Cap at max delay
        return min(delay, self.max_delay)


async def retry_with_backoff(
    func: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
    **kwargs: Any,
) -> T:
    """
    Execute a function with retry and exponential backoff.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration
        on_retry: Callback called before each retry (attempt, delay, error)
        **kwargs: Keyword arguments for func
    
    Returns:
        Result of the function
    
    Raises:
        The last exception if all retries fail
    """
    config = config or RetryConfig()
    last_error: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
                
        except Exception as e:
            last_error = e
            rate_limit_info = detect_rate_limit(e)
            
            # Don't retry if daily limit is hit
            if rate_limit_info.daily_limit_hit:
                logger.error("Daily API quota exhausted. Cannot retry.")
                raise
            
            # Check if we have retries left
            if attempt >= config.max_retries:
                logger.error(f"All {config.max_retries} retries exhausted")
                raise
            
            # Calculate delay
            delay = config.get_delay(attempt, rate_limit_info)
            
            # Log and callback
            if rate_limit_info.is_rate_limited:
                logger.warning(
                    f"Rate limited (attempt {attempt + 1}/{config.max_retries + 1}). "
                    f"Retrying in {delay:.1f}s..."
                )
            else:
                logger.warning(
                    f"Error (attempt {attempt + 1}/{config.max_retries + 1}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
            
            if on_retry:
                on_retry(attempt, delay, e)
            
            # Wait before retry
            await asyncio.sleep(delay)
    
    # Should never reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Retry loop exited unexpectedly")


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry behavior to async functions.
    
    Usage:
        @with_retry(RetryConfig(max_retries=5))
        async def my_api_call():
            ...
    """
    config = config or RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_with_backoff(func, *args, config=config, **kwargs)
        return wrapper
    
    return decorator
