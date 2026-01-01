"""
A2A Protocol implementation for apflow

This module contains the A2A (Agent-to-Agent) Protocol Server implementation.
"""

from apflow.api.a2a.server import create_a2a_server
from apflow.api.a2a.agent_executor import AIPartnerUpFlowAgentExecutor
from apflow.api.a2a.custom_starlette_app import CustomA2AStarletteApplication
from apflow.api.a2a.event_queue_bridge import EventQueueBridge

__all__ = [
    "create_a2a_server",
    "AIPartnerUpFlowAgentExecutor",
    "CustomA2AStarletteApplication",
    "EventQueueBridge",
]

