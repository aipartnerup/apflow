"""
LLM Key Configuration Extension

This extension provides user-level LLM key management for multi-user scenarios.
LLM keys are stored in memory (or Redis in future) and never stored in the database.

Requires: pip install aipartnerupflow[llm-key-config]
"""

from aipartnerupflow.extensions.llm_key_config.config_manager import LLMKeyConfigManager

__all__ = ["LLMKeyConfigManager"]

