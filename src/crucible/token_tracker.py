"""
Token tracking and budgeting for AI Crucible.

Tracks token usage across iterations to prevent rate limit exhaustion
and enable smart batching decisions.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import json
from pathlib import Path


@dataclass
class TokenUsage:
    """Record of a single LLM operation's token usage."""
    
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: float
    agent_name: Optional[str] = None
    operation: Optional[str] = None  # e.g., "architect", "red_team", "defender"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "timestamp": self.timestamp,
            "agent_name": self.agent_name,
            "operation": self.operation
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TokenUsage":
        """Create from dictionary."""
        return cls(**data)


class TokenBudget:
    """
    Manages token budget and provides warnings when thresholds are exceeded.
    
    Tracks token usage across iterations and provides smart batching
    recommendations based on remaining budget.
    """
    
    def __init__(
        self, 
        daily_limit: int = 100_000,
        warn_threshold: float = 0.8,
        critical_threshold: float = 0.9
    ):
        """
        Initialize token budget tracker.
        
        Args:
            daily_limit: Maximum tokens allowed per day
            warn_threshold: Percentage to trigger warning (default 80%)
            critical_threshold: Percentage to trigger critical warning (default 90%)
        """
        self.daily_limit = daily_limit
        self.warn_threshold = warn_threshold
        self.critical_threshold = critical_threshold
        self.usage_history: List[TokenUsage] = []
        self.warned_80 = False
        self.warned_90 = False
    
    def add_usage(self, usage: TokenUsage) -> None:
        """
        Record token usage from an operation.
        
        Args:
            usage: TokenUsage record to add
        """
        self.usage_history.append(usage)
    
    @property
    def total_used(self) -> int:
        """Total tokens consumed so far."""
        return sum(u.total_tokens for u in self.usage_history)
    
    @property
    def remaining(self) -> int:
        """Tokens remaining in budget."""
        return max(0, self.daily_limit - self.total_used)
    
    @property
    def percent_used(self) -> float:
        """Percentage of budget consumed (0-100)."""
        if self.daily_limit == 0:
            return 100.0
        return (self.total_used / self.daily_limit) * 100
    
    def check_threshold(self) -> Optional[str]:
        """
        Check if any threshold has been crossed.
        
        Returns:
            Warning message if threshold crossed, None otherwise.
            Only returns warning once per threshold.
        """
        pct = self.percent_used
        
        # Critical threshold (90%)
        if pct >= (self.critical_threshold * 100) and not self.warned_90:
            self.warned_90 = True
            return (
                f"⚠️  CRITICAL: {pct:.1f}% token budget used "
                f"({self.total_used:,}/{self.daily_limit:,} tokens). "
                f"Only {self.remaining:,} tokens remaining!"
            )
        
        # Warning threshold (80%)
        if pct >= (self.warn_threshold * 100) and not self.warned_80:
            self.warned_80 = True
            return (
                f"⚠️  WARNING: {pct:.1f}% token budget used "
                f"({self.total_used:,}/{self.daily_limit:,} tokens). "
                f"{self.remaining:,} tokens remaining."
            )
        
        return None
    
    def can_afford(self, estimated_tokens: int) -> bool:
        """
        Check if we have enough budget for an operation.
        
        Args:
            estimated_tokens: Estimated token cost of operation
            
        Returns:
            True if operation is within budget
        """
        return self.remaining >= estimated_tokens
    
    def estimate_operation_cost(self, operation_type: str) -> int:
        """
        Estimate token cost for an operation based on history.
        
        Args:
            operation_type: Type of operation (e.g., "architect", "red_team")
            
        Returns:
            Estimated token cost, or conservative estimate if no history
        """
        # Filter usage history for this operation type
        relevant_usage = [
            u for u in self.usage_history 
            if u.operation == operation_type
        ]
        
        if not relevant_usage:
            # Conservative estimates for different operations
            defaults = {
                "architect": 2000,
                "red_team": 800,
                "defender": 1000,
                "judge": 500,
            }
            return defaults.get(operation_type, 1000)
        
        # Average of recent operations (last 5)
        recent = relevant_usage[-5:]
        avg = sum(u.total_tokens for u in recent) / len(recent)
        
        # Add 20% buffer for safety
        return int(avg * 1.2)
    
    def get_usage_by_iteration(self) -> dict[int, int]:
        """
        Get token usage broken down by iteration.
        
        Returns:
            Dictionary mapping iteration number to token count
        """
        # This would need iteration tracking in TokenUsage
        # For now, return total
        return {0: self.total_used}
    
    def get_usage_by_agent(self) -> dict[str, int]:
        """
        Get token usage broken down by agent.
        
        Returns:
            Dictionary mapping agent name to token count
        """
        usage_by_agent = {}
        for usage in self.usage_history:
            if usage.agent_name:
                agent = usage.agent_name
                usage_by_agent[agent] = usage_by_agent.get(agent, 0) + usage.total_tokens
        return usage_by_agent
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "daily_limit": self.daily_limit,
            "warn_threshold": self.warn_threshold,
            "critical_threshold": self.critical_threshold,
            "total_used": self.total_used,
            "remaining": self.remaining,
            "percent_used": self.percent_used,
            "usage_history": [u.to_dict() for u in self.usage_history],
            "warned_80": self.warned_80,
            "warned_90": self.warned_90,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TokenBudget":
        """Create from dictionary."""
        budget = cls(
            daily_limit=data["daily_limit"],
            warn_threshold=data["warn_threshold"],
            critical_threshold=data["critical_threshold"]
        )
        budget.warned_80 = data.get("warned_80", False)
        budget.warned_90 = data.get("warned_90", False)
        
        # Restore usage history
        for usage_dict in data.get("usage_history", []):
            budget.add_usage(TokenUsage.from_dict(usage_dict))
        
        return budget
    
    def save_to_file(self, filepath: Path) -> None:
        """Save budget to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: Path) -> "TokenBudget":
        """Load budget from JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        return cls.from_dict(data)


def get_parallelism_recommendation(budget: TokenBudget) -> tuple[bool, int]:
    """
    Recommend parallelism settings based on remaining budget.
    
    Args:
        budget: Current token budget
        
    Returns:
        (should_run_parallel, max_concurrent_agents)
    """
    pct_used = budget.percent_used
    
    # If we've used 80%+ of budget, run sequentially
    if pct_used >= 80:
        return False, 1
    
    # If we've used 50-80%, limit concurrency
    if pct_used >= 50:
        return True, 3
    
    # Otherwise, full parallelism
    return True, 6
