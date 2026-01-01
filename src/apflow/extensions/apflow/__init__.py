"""
apflow API executor feature

This feature provides capabilities to call other apflow API instances.
Useful for distributed task execution, service orchestration, and load balancing.
"""

from apflow.extensions.apflow.api_executor import ApFlowApiExecutor

__all__ = ["ApFlowApiExecutor"]

