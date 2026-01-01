"""
LLM Key Configuration Extension

This extension provides user-level LLM key management for multi-user scenarios.
LLM keys are stored in memory (or Redis in future) and never stored in the database.

Requires: pip install apflow[llm-key-config]
"""

from apflow.extensions.llm_key_config.config_manager import LLMKeyConfigManager

__all__ = ["LLMKeyConfigManager"]

