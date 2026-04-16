"""
Metric aggregation strategies for AI Crucible evaluation.

This module provides different strategies for combining multiple criterion
scores into a single aggregate score.
"""

from abc import ABC, abstractmethod
from typing import Any

from crucible.eval.schemas import CriterionScore


class AggregationStrategy(ABC):
    """
    Abstract base class for aggregation strategies.

    Each strategy defines how to combine multiple criterion scores
    into a single aggregate score.
    """

    name: str = "base"

    def __init__(self, weights: dict[str, float] | None = None):
        """
        Initialize the aggregation strategy.

        Args:
            weights: Optional mapping of criterion names to weights.
                      Unspecified criteria use default weight of 1.0.
        """
        self.weights = weights or {}

    @abstractmethod
    def aggregate(self, scores: dict[str, CriterionScore]) -> float:
        """
        Aggregate multiple scores into a single value.

        Args:
            scores: Mapping of criterion names to scores

        Returns:
            Aggregate score between 0 and 1
        """
        pass

    def _get_weight(self, criterion_name: str) -> float:
        """Get the weight for a criterion."""
        return self.weights.get(criterion_name, 1.0)


class WeightedAverageStrategy(AggregationStrategy):
    """
    Weighted average aggregation strategy.

    This strategy calculates the weighted average of all criterion
    scores. Criteria with higher weights contribute more to the
    final score.
    """

    name = "weighted_average"

    def aggregate(self, scores: dict[str, CriterionScore]) -> float:
        """Calculate weighted average."""
        if not scores:
            return 0.0

        total = 0.0
        weight_sum = 0.0

        for name, score in scores.items():
            weight = self._get_weight(name)
            total += weight * score.value
            weight_sum += weight

        return total / weight_sum if weight_sum > 0 else 0.0


class MinStrategy(AggregationStrategy):
    """
    Minimum score aggregation strategy.

    This conservative strategy returns the minimum score across
    all criteria. This represents a "weakest link" approach
    where any single failure brings down the overall score.
    """

    name = "min"

    def aggregate(self, scores: dict[str, CriterionScore]) -> float:
        """Return the minimum score."""
        if not scores:
            return 0.0

        return min(s.value for s in scores.values())


class MaxStrategy(AggregationStrategy):
    """
    Maximum score aggregation strategy.

    This optimistic strategy returns the maximum score across
    all criteria. This highlights the best-performing aspect
    of the system.
    """

    name = "max"

    def aggregate(self, scores: dict[str, CriterionScore]) -> float:
        """Return the maximum score."""
        if not scores:
            return 0.0

        return max(s.value for s in scores.values())


class ProductStrategy(AggregationStrategy):
    """
    Product aggregation strategy.

    This strategy multiplies all criterion scores together.
    This heavily penalizes any single failure - even one low
    score will significantly reduce the aggregate.
    """

    name = "product"

    def aggregate(self, scores: dict[str, CriterionScore]) -> float:
        """Calculate product of all scores."""
        if not scores:
            return 0.0

        result = 1.0
        for score in scores.values():
            result *= score.value

        return result


class CustomFormulaStrategy(AggregationStrategy):
    """
    Custom formula aggregation strategy.

    This strategy allows for domain-specific aggregation formulas.
    The formula is provided as a callable that receives a mapping of
    criterion names to values and returns an aggregate score.
    """

    name = "custom"

    def __init__(
        self,
        formula: "Callable[[dict[str, float]], float]",
        weights: dict[str, float] | None = None,
    ):
        """
        Initialize custom formula strategy.

        Args:
            formula: Callable that takes criterion values and returns aggregate
            weights: Optional mapping of criterion names to weights
        """
        super().__init__(weights)
        self.formula = formula

    def aggregate(self, scores: dict[str, CriterionScore]) -> float:
        """Apply custom formula."""
        if not scores:
            return 0.0

        values = {name: s.value for name, s in scores.items()}
        result = self.formula(values)

        # Ensure result is in [0, 1] range
        return max(0.0, min(1.0, result))


# Pre-defined strategies for common use cases

SECURITY_FOCUSED = WeightedAverageStrategy(
    weights={
        "attack_effectiveness": 2.0,  # Weighted higher
        "convergence_speed": 1.0,
        "redundancy": 1.0,
        "token_efficiency": 0.5,  # Weighted lower
    }
)

CONSERVATIVE = MinStrategy()  # "Weakest link"

OPTIMISTIC = MaxStrategy()  # Highlight best performance

BALANCED = WeightedAverageStrategy()  # Equal weights
