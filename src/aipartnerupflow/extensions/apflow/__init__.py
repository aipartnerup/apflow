"""
aipartnerupflow API executor feature

This feature provides capabilities to call other aipartnerupflow API instances.
Useful for distributed task execution, service orchestration, and load balancing.
"""

from aipartnerupflow.extensions.apflow.api_executor import ApFlowApiExecutor

__all__ = ["ApFlowApiExecutor"]

