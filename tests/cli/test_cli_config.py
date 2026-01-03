"""
Tests for CLI configuration management.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apflow.cli.cli_config import (
    load_cli_config,
    save_cli_config,
    generate_admin_token,
    get_config_value,
    set_config_value,
    list_config_values,
)


class TestCLIConfigPersistence:
    """Test CLI configuration persistence."""
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "cli_config.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                # Save config
                test_config = {
                    "api_server_url": "http://localhost:8000",
                    "api_auth_token": "test-token-123",
                }
                save_cli_config(test_config)
                
                # Verify file was created
                assert config_file.exists()
                
                # Load config
                loaded = load_cli_config()
                assert loaded == test_config
    
    def test_load_nonexistent_config(self):
        """Test loading nonexistent config returns empty dict."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "nonexistent.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                loaded = load_cli_config()
                assert loaded == {}
    
    def test_generate_admin_token(self):
        """Test admin token generation."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "cli_config.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                # Generate token
                token = generate_admin_token()
                assert token
                assert len(token) > 0
                assert isinstance(token, str)
                
                # Token should be valid JWT (no validation, just format check)
                parts = token.split('.')
                assert len(parts) == 3  # Header.Payload.Signature
    
    def test_get_set_config_value(self):
        """Test get/set individual config values."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "cli_config.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                # Set value
                set_config_value("test_key", "test_value")
                
                # Get value
                value = get_config_value("test_key")
                assert value == "test_value"
                
                # Get nonexistent value
                value = get_config_value("nonexistent")
                assert value is None
    
    def test_delete_config_value(self):
        """Test deleting config values."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "cli_config.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                # Set value
                set_config_value("key_to_delete", "value")
                assert get_config_value("key_to_delete") == "value"
                
                # Delete value
                set_config_value("key_to_delete", None)
                assert get_config_value("key_to_delete") is None
    
    def test_list_config_masks_tokens(self):
        """Test that list_config_values masks sensitive tokens."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "cli_config.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                # Save config with token
                config = {
                    "api_server_url": "http://localhost:8000",
                    "api_auth_token": "very-secret-token-12345",
                }
                save_cli_config(config)
                
                # List should mask token
                listed = list_config_values()
                
                # URL should be visible
                assert listed["api_server_url"] == "http://localhost:8000"
                
                # Token should be masked
                assert "***" in listed["api_auth_token"]
                assert "secret" not in listed["api_auth_token"]


class TestCLIConfigIntegration:
    """Test CLI configuration integration."""
    
    def test_multiple_config_keys(self):
        """Test saving and loading multiple config keys."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "cli_config.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                # Set multiple values
                set_config_value("api_server_url", "http://api.example.com")
                set_config_value("api_auth_token", "token-xyz")
                set_config_value("api_timeout", "60")
                
                # Load and verify
                loaded = load_cli_config()
                assert len(loaded) == 3
                assert loaded["api_server_url"] == "http://api.example.com"
                assert loaded["api_auth_token"] == "token-xyz"
                assert loaded["api_timeout"] == "60"
    
    def test_config_file_json_format(self):
        """Test that config file is valid JSON."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "cli_config.json"
            
            with patch("apflow.cli.cli_config.CONFIG_FILE", config_file):
                # Save config
                test_config = {"key1": "value1", "key2": "value2"}
                save_cli_config(test_config)
                
                # Read file directly and parse JSON
                with open(config_file, "r") as f:
                    file_content = json.load(f)
                
                assert file_content == test_config
