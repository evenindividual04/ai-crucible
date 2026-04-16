"""
Metrics tracking for the AI Crucible.

Tracks API calls, tokens, and timing for cost estimation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
import time


@dataclass
class APICallMetric:
    """Record of a single API call."""
    
    agent: str
    model: str
    timestamp: datetime
    duration_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class RunMetrics:
    """Aggregated metrics for a Crucible run."""
    
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    api_calls: List[APICallMetric] = field(default_factory=list)
    
    # Iteration tracking
    iterations_completed: int = 0
    
    def record_call(
        self,
        agent: str,
        model: str,
        duration_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """Record an API call."""
        self.api_calls.append(APICallMetric(
            agent=agent,
            model=model,
            timestamp=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
            error=error,
        ))
    
    def finish(self) -> None:
        """Mark the run as finished."""
        self.end_time = datetime.now(timezone.utc)
    
    @property
    def total_api_calls(self) -> int:
        """Total number of API calls made."""
        return len(self.api_calls)
    
    @property
    def successful_calls(self) -> int:
        """Number of successful API calls."""
        return sum(1 for c in self.api_calls if c.success)
    
    @property
    def failed_calls(self) -> int:
        """Number of failed API calls."""
        return sum(1 for c in self.api_calls if not c.success)
    
    @property
    def total_input_tokens(self) -> int:
        """Total input tokens used."""
        return sum(c.input_tokens for c in self.api_calls)
    
    @property
    def total_output_tokens(self) -> int:
        """Total output tokens generated."""
        return sum(c.output_tokens for c in self.api_calls)
    
    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def total_duration_seconds(self) -> float:
        """Total run duration in seconds."""
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()
    
    @property
    def estimated_cost_usd(self) -> float:
        """
        Estimate cost in USD.
        
        Based on Gemini 2.0 Flash pricing:
        - Input: $0.10 per 1M tokens
        - Output: $0.40 per 1M tokens
        """
        input_cost = (self.total_input_tokens / 1_000_000) * 0.10
        output_cost = (self.total_output_tokens / 1_000_000) * 0.40
        return input_cost + output_cost
    
    def summary(self) -> dict:
        """Get a summary of metrics."""
        return {
            "total_duration_seconds": round(self.total_duration_seconds, 1),
            "iterations_completed": self.iterations_completed,
            "api_calls": {
                "total": self.total_api_calls,
                "successful": self.successful_calls,
                "failed": self.failed_calls,
            },
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
                "total": self.total_tokens,
            },
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
        }
    
    def format_summary(self) -> str:
        """Format a human-readable summary."""
        duration = self.total_duration_seconds
        mins = int(duration // 60)
        secs = int(duration % 60)
        
        lines = [
            f"⏱️  Duration: {mins}m {secs}s",
            f"🔄 Iterations: {self.iterations_completed}",
            f"📡 API Calls: {self.total_api_calls} ({self.failed_calls} failed)",
            f"📊 Tokens: ~{self.total_tokens:,} (est. ${self.estimated_cost_usd:.4f})",
        ]
        return " | ".join(lines)


# Global metrics instance
_metrics: Optional[RunMetrics] = None


def get_metrics() -> RunMetrics:
    """Get or create the global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = RunMetrics()
    return _metrics


def reset_metrics() -> RunMetrics:
    """Reset and return a fresh metrics instance."""
    global _metrics
    _metrics = RunMetrics()
    return _metrics
