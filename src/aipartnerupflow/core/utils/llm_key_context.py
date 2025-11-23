"""
LLM Key Context Manager

Provides thread-local context for LLM API keys during task execution.
Supports two sources with priority:
1. Request header - for demo/one-time usage
2. User config - for multi-user scenarios

Note: Environment variables (OPENAI_API_KEY) are automatically read by CrewAI/LiteLLM,
so we don't need to handle them here.
"""

import os
import threading
from typing import Optional
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Thread-local storage for LLM key context
_context = threading.local()


def set_llm_key_from_header(api_key: Optional[str], provider: Optional[str] = None) -> None:
    """
    Set LLM API key and provider from request header
    
    Args:
        api_key: LLM API key from request header
        provider: Optional provider name from request header
    """
    _context.llm_key_header = api_key
    if provider:
        _context.llm_provider_header = provider
    if api_key:
        logger.debug(f"Set LLM key from request header (provider: {provider or 'auto'})")


def get_llm_key_from_header() -> Optional[str]:
    """
    Get LLM API key from request header
    
    Returns:
        LLM API key if set, None otherwise
    """
    return getattr(_context, 'llm_key_header', None)


def get_llm_provider_from_header() -> Optional[str]:
    """
    Get LLM provider from request header
    
    Returns:
        LLM provider name if set, None otherwise
    """
    return getattr(_context, 'llm_provider_header', None)


def get_llm_key(user_id: Optional[str] = None, provider: Optional[str] = None) -> Optional[str]:
    """
    Get LLM API key with priority: header > user config
    
    Note: Environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) are automatically
    read by CrewAI/LiteLLM, so we don't need to return them here. We only handle dynamic
    keys from header/config.
    
    Args:
        user_id: Optional user ID for user config lookup
        provider: Optional provider name for provider-specific key lookup.
                   If None, will use provider from request header if available.
        
    Returns:
        LLM API key, or None if not found
    """
    # Priority 1: Request header
    header_key = get_llm_key_from_header()
    if header_key:
        # Use provider from header if not explicitly provided
        header_provider = get_llm_provider_from_header()
        if not provider and header_provider:
            provider = header_provider
        logger.debug(f"Using LLM key from request header (provider: {provider or 'auto'})")
        return header_key
    
    # Priority 2: User config
    if user_id:
        try:
            from aipartnerupflow.extensions.llm_key_config import LLMKeyConfigManager
            config_manager = LLMKeyConfigManager()
            # Try provider-specific key first, then default
            user_key = config_manager.get_key(user_id, provider=provider)
            if not user_key and provider:
                # Fallback to default key if provider-specific not found
                user_key = config_manager.get_key(user_id, provider=None)
            if user_key:
                logger.debug(f"Using LLM key from user config for user {user_id}, provider {provider or 'default'}")
                return user_key
        except ImportError:
            # llm-key-config extension not installed
            pass
        except Exception as e:
            logger.warning(f"Failed to get LLM key from user config: {e}")
    
    # Return None - CrewAI/LiteLLM will automatically use provider-specific env vars
    return None


def clear_llm_key_context() -> None:
    """
    Clear LLM key context (mainly for testing)
    """
    if hasattr(_context, 'llm_key_header'):
        delattr(_context, 'llm_key_header')
    if hasattr(_context, 'llm_provider_header'):
        delattr(_context, 'llm_provider_header')

