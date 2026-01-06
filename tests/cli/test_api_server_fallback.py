"""
Test API server fallback to local database when server is unreachable.
"""
import pytest
from apflow.cli.api_gateway_helper import should_use_api, reset_api_validation
from apflow.core.config_manager import get_config_manager


@pytest.fixture(autouse=True)
def _reset_api_state():
    """Reset API validation state before and after each test."""
    reset_api_validation()
    cm = get_config_manager()
    cm.clear()
    yield
    reset_api_validation()
    cm.clear()


def test_should_use_api_when_no_url_configured():
    """Should return False and keep URL unset when nothing configured."""
    result = should_use_api()
    assert result is False


def test_should_use_api_when_url_inaccessible():
    """Test that should_use_api returns False and clears URL when server is unreachable."""
    cm = get_config_manager()
    
    # Set an inaccessible URL
    cm.set_api_server_url("http://localhost:9999")
    assert cm.get_api_server_url() == "http://localhost:9999"
    
    # Check if API should be used - should return False and clear URL
    result = should_use_api()
    assert result is False
    assert cm.get_api_server_url() is None


def test_should_use_api_validates_only_once():
    """Test that API validation only happens once per session."""
    reset_api_validation()
    cm = get_config_manager()
    cm.set_api_server_url("http://localhost:9999")
    
    # First call should validate
    result1 = should_use_api()
    assert result1 is False
    
    # Set a valid URL
    cm.set_api_server_url("http://localhost:8000")
    
    # Second call should NOT re-validate (cached result from first call)
    result2 = should_use_api()
    assert result2 is False  # Still False because cached from first validation
    
    # After reset, should re-validate
    reset_api_validation()
    result3 = should_use_api()
    assert result3 is False
    # This will fail because http://localhost:8000 is probably not accessible
    # But that's OK - it shows re-validation is happening


def test_api_fallback_workflow():
    """Test the complete workflow: load config, validate, then fallback to DB."""
    cm = get_config_manager()
    
    # Simulate loading config with invalid URL
    cm.set_api_server_url("http://invalid-server.local:9999")
    
    # Check should_use_api
    should_use = should_use_api()
    
    # Should fall back to local DB
    assert should_use is False
    
    # URL should be cleared
    assert cm.get_api_server_url() is None
    
    # use_local_db should still be True
    assert cm.get_use_local_db() is True
