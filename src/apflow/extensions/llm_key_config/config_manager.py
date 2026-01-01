"""
LLM Key Configuration Manager

Manages user-level LLM API keys in memory (not stored in database).
Supports multi-user scenarios where each user can have their own LLM key.
Supports multiple providers - users can have different keys for different LLM providers.
"""

from typing import Optional, Dict
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class LLMKeyConfigManager:
    """
    Manages LLM API keys per user and provider (stored in memory)
    
    Keys are never stored in the database. This is a simple in-memory store.
    For production multi-server scenarios, consider using Redis.
    
    Supports multiple providers per user: user_id -> {provider -> api_key}
    """
    
    _instance: Optional["LLMKeyConfigManager"] = None
    _user_keys: Dict[str, Dict[str, str]] = {}  # user_id -> {provider -> api_key}
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._user_keys = {}
        return cls._instance
    
    def set_key(self, user_id: str, api_key: str, provider: Optional[str] = None) -> None:
        """
        Set LLM API key for a user
        
        Args:
            user_id: User ID
            api_key: LLM API key
            provider: Optional provider name (e.g., "openai", "anthropic").
                     If None, stores as "default" (for backward compatibility)
        """
        if user_id not in self._user_keys:
            self._user_keys[user_id] = {}
        
        provider_key = provider or "default"
        self._user_keys[user_id][provider_key] = api_key
        logger.debug(f"Set LLM key for user {user_id}, provider {provider_key} (key length: {len(api_key)})")
    
    def get_key(self, user_id: str, provider: Optional[str] = None) -> Optional[str]:
        """
        Get LLM API key for a user
        
        Args:
            user_id: User ID
            provider: Optional provider name. If None, tries "default" first
            
        Returns:
            API key if exists, None otherwise
        """
        if user_id not in self._user_keys:
            return None
        
        user_keys = self._user_keys[user_id]
        
        # If provider specified, return that key
        if provider:
            return user_keys.get(provider)
        
        # Otherwise, return default key (for backward compatibility)
        return user_keys.get("default")
    
    def delete_key(self, user_id: str, provider: Optional[str] = None) -> bool:
        """
        Delete LLM API key for a user
        
        Args:
            user_id: User ID
            provider: Optional provider name. If None, deletes all keys for user
            
        Returns:
            True if key(s) were deleted, False if not found
        """
        if user_id not in self._user_keys:
            return False
        
        if provider:
            # Delete specific provider key
            if provider in self._user_keys[user_id]:
                del self._user_keys[user_id][provider]
                logger.debug(f"Deleted LLM key for user {user_id}, provider {provider}")
                return True
        else:
            # Delete all keys for user
            del self._user_keys[user_id]
            logger.debug(f"Deleted all LLM keys for user {user_id}")
            return True
        
        return False
    
    def has_key(self, user_id: str, provider: Optional[str] = None) -> bool:
        """
        Check if user has an LLM key configured
        
        Args:
            user_id: User ID
            provider: Optional provider name. If None, checks if any key exists
            
        Returns:
            True if key exists, False otherwise
        """
        if user_id not in self._user_keys:
            return False
        
        if provider:
            return provider in self._user_keys[user_id]
        
        # Check if any key exists
        return len(self._user_keys[user_id]) > 0
    
    def get_all_providers(self, user_id: str) -> Dict[str, str]:
        """
        Get all providers and keys for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary mapping provider to API key (keys masked for security)
        """
        if user_id not in self._user_keys:
            return {}
        
        # Return provider names only (not the actual keys for security)
        return {provider: "***" for provider in self._user_keys[user_id].keys()}
    
    def clear_all(self) -> None:
        """
        Clear all stored keys (mainly for testing)
        """
        self._user_keys.clear()
        logger.debug("Cleared all LLM keys")

