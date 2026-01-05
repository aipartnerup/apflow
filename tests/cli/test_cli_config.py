"""
Tests for CLI configuration management.
"""

import yaml
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


from apflow.cli.cli_config import (
    load_cli_config,
    save_cli_config_yaml,
    get_config_value,
    set_config_value,
    list_config_values,
    is_localhost_url,
    validate_cli_config,
)


class TestCLIConfigPersistence:
    """Test CLI configuration persistence."""

    def test_save_and_load_yaml_config(self):
        """Test saving and loading YAML configuration."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.cli.yaml"

            with patch("apflow.cli.cli_config.get_config_dir", return_value=config_dir):
                with patch("apflow.cli.cli_config.get_cli_config_file_path", return_value=config_file):
                    with patch("apflow.cli.cli_config.get_all_cli_config_locations", return_value=[config_file]):
                        # Save config
                        test_config = {
                            "api_server_url": "http://localhost:8000",
                            "admin_auth_token": "test-token-123",
                        }
                        save_cli_config_yaml(test_config)

                        # Verify file was created
                        assert config_file.exists()

                        # Verify file permissions (600)
                        assert oct(config_file.stat().st_mode)[-3:] == "600"

                        # Load config
                        loaded = load_cli_config()
                        assert loaded["api_server_url"] == test_config["api_server_url"]
                        assert loaded["admin_auth_token"] == test_config["admin_auth_token"]

                        # Verify YAML format
                        with open(config_file, "r") as f:
                            yaml_content = yaml.safe_load(f)
                        assert yaml_content["api_server_url"] == test_config["api_server_url"]
                        assert yaml_content["admin_auth_token"] == test_config["admin_auth_token"]

    def test_load_nonexistent_config(self):
        """Test loading nonexistent config returns empty dict."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            nonexistent_file = config_dir / "config.cli.yaml"

            with patch("apflow.cli.cli_config.get_config_dir", return_value=config_dir):
                with patch("apflow.cli.cli_config.get_cli_config_file_path", return_value=nonexistent_file):
                    with patch("apflow.cli.cli_config.get_all_cli_config_locations", return_value=[nonexistent_file]):
                        loaded = load_cli_config()
                        assert loaded == {}

    def test_get_set_config_value(self):
        """Test get/set individual config values."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.cli.yaml"

            with patch("apflow.cli.cli_config.get_config_dir", return_value=config_dir):
                with patch("apflow.cli.cli_config.get_cli_config_file_path", return_value=config_file):
                    with patch("apflow.cli.cli_config.get_all_cli_config_locations", return_value=[config_file]):
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
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.cli.yaml"

            with patch("apflow.cli.cli_config.get_config_dir", return_value=config_dir):
                with patch("apflow.cli.cli_config.get_cli_config_file_path", return_value=config_file):
                    with patch("apflow.cli.cli_config.get_all_cli_config_locations", return_value=[config_file]):
                        # Set value
                        set_config_value("key_to_delete", "value")
                        assert get_config_value("key_to_delete") == "value"

                        # Delete value
                        set_config_value("key_to_delete", None)
                        assert get_config_value("key_to_delete") is None

    def test_list_config_masks_tokens(self):
        """Test that list_config_values masks sensitive tokens."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.cli.yaml"

            with patch("apflow.cli.cli_config.get_config_dir", return_value=config_dir):
                with patch("apflow.cli.cli_config.get_cli_config_file_path", return_value=config_file):
                    with patch("apflow.cli.cli_config.get_all_cli_config_locations", return_value=[config_file]):
                        # Save config with token
                        config = {
                            "api_server_url": "http://localhost:8000",
                            "admin_auth_token": "very-secret-token-12345",
                            "jwt_secret": "secret-key-123",
                        }
                        save_cli_config_yaml(config)

                        # List should mask token
                        listed = list_config_values()

                        # URL should be visible
                        assert listed["api_server_url"] == "http://localhost:8000"

                        # Token should be masked
                        assert "***" in listed["admin_auth_token"]
                        assert "secret" not in listed["admin_auth_token"]

                        # jwt_secret should be masked
                        assert "***" in listed["jwt_secret"]
                        assert "secret" not in listed["jwt_secret"]


class TestCLIConfigIntegration:
    """Test CLI configuration integration."""

    def test_multiple_config_keys(self):
        """Test saving and loading multiple config keys."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.cli.yaml"

            with patch("apflow.cli.cli_config.get_config_dir", return_value=config_dir):
                with patch("apflow.cli.cli_config.get_cli_config_file_path", return_value=config_file):
                    with patch("apflow.cli.cli_config.get_all_cli_config_locations", return_value=[config_file]):
                        # Set multiple values (use localhost to avoid jwt_secret requirement)
                        set_config_value("api_server_url", "http://localhost:8000")
                        set_config_value("admin_auth_token", "token-xyz")
                        set_config_value("jwt_secret", "secret-123")

                        # Load and verify
                        loaded = load_cli_config()
                        assert loaded["api_server_url"] == "http://localhost:8000"
                        assert loaded["admin_auth_token"] == "token-xyz"
                        assert loaded["jwt_secret"] == "secret-123"

    def test_config_file_yaml_format(self):
        """Test that config file is valid YAML."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.cli.yaml"

            with patch("apflow.cli.cli_config.get_config_dir", return_value=config_dir):
                with patch("apflow.cli.cli_config.get_cli_config_file_path", return_value=config_file):
                    # Save config
                    test_config = {"key1": "value1", "key2": "value2"}
                    save_cli_config_yaml(test_config)

                    # Read file directly and parse YAML
                    with open(config_file, "r") as f:
                        file_content = yaml.safe_load(f)

                    assert file_content == test_config


class TestLocalhostDetection:
    """Test localhost URL detection."""

    def test_is_localhost_url(self):
        """Test localhost URL detection."""
        assert is_localhost_url("http://localhost:8000") is True
        assert is_localhost_url("http://127.0.0.1:8000") is True
        assert is_localhost_url("http://localhost") is True
        assert is_localhost_url("https://localhost:443") is True
        assert is_localhost_url("http://api.example.com:8000") is False
        assert is_localhost_url("http://192.168.1.1:8000") is False

    def test_localhost_with_port(self):
        """Test localhost detection with various ports."""
        assert is_localhost_url("http://localhost:3000") is True
        assert is_localhost_url("http://localhost:8080") is True
        assert is_localhost_url("http://127.0.0.1:9000") is True


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_localhost_no_jwt_secret_required(self):
        """Test that jwt_secret is optional for localhost."""
        config = {
            "api_server_url": "http://localhost:8000",
            "admin_auth_token": "token-123",
        }
        # Should not raise
        validate_cli_config(config)
        # jwt_algorithm should be set to default
        assert config["jwt_algorithm"] == "HS256"

    def test_validate_non_localhost_requires_jwt_secret(self):
        """Test that jwt_secret is NOT required for non-localhost (auth can be disabled)."""
        config = {
            "api_server_url": "http://api.example.com:8000",
            "admin_auth_token": "token-123",
        }
        # Should NOT raise ValueError - auth can be disabled even for non-localhost
        validate_cli_config(config)
        assert config.get("api_server_url") == "http://api.example.com:8000"

    def test_validate_non_localhost_with_jwt_secret(self):
        """Test that non-localhost with jwt_secret is valid."""
        config = {
            "api_server_url": "http://api.example.com:8000",
            "admin_auth_token": "token-123",
            "jwt_secret": "secret-key-123",
        }
        # Should not raise
        validate_cli_config(config)
        # jwt_algorithm should be set to default
        assert config["jwt_algorithm"] == "HS256"

    def test_validate_sets_default_jwt_algorithm(self):
        """Test that jwt_algorithm defaults to HS256."""
        config = {
            "api_server_url": "http://localhost:8000",
        }
        validate_cli_config(config)
        assert config["jwt_algorithm"] == "HS256"

    def test_validate_preserves_existing_jwt_algorithm(self):
        """Test that existing jwt_algorithm is preserved."""
        config = {
            "api_server_url": "http://localhost:8000",
            "jwt_algorithm": "HS512",
        }
        validate_cli_config(config)
        assert config["jwt_algorithm"] == "HS512"

