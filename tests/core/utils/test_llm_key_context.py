"""
Tests for LLM key context management
"""

from unittest.mock import patch
from apflow.core.utils.llm_key_context import (
    get_llm_key,
    get_llm_provider_from_header,
    set_llm_key_from_header,
    clear_llm_key_context,
)


class TestLLMKeyContext:
    """Test LLM key context management"""

    def setup_method(self):
        """Clean up before each test"""
        clear_llm_key_context()

    def teardown_method(self):
        """Clean up after each test"""
        clear_llm_key_context()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"}, clear=True)
    def test_get_llm_key_from_environment(self):
        """Test getting LLM key from environment variables"""
        clear_llm_key_context()  # Ensure clean state
        key = get_llm_key(user_id="user123", provider="openai", context="api")
        assert key == "sk-env-key"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_llm_key_from_header(self):
        """Test getting LLM key from header context"""
        set_llm_key_from_header("sk-header-key", "openai")
        key = get_llm_key(user_id="user123", provider="openai", context="api")
        assert key == "sk-header-key"

    def test_get_llm_provider_from_header_with_provider(self):
        """Test extracting provider from header with explicit provider"""
        set_llm_key_from_header("sk-test123", "openai")
        provider = get_llm_provider_from_header()
        assert provider == "openai"

    def test_set_and_clear_llm_key_header(self):
        """Test setting and clearing LLM key header"""
        set_llm_key_from_header("sk-test123", "openai")
        assert get_llm_provider_from_header() == "openai"
        
        clear_llm_key_context()
        assert get_llm_provider_from_header() is None
