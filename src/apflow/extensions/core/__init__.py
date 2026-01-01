"""
Core built-in executors for common task patterns
"""

# Import aggregate_results_executor to trigger registration
from apflow.extensions.core.aggregate_results_executor import AggregateResultsExecutor  # noqa: F401

__all__ = [
    "AggregateResultsExecutor",
]

