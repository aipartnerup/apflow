"""
Tests for CLI config command.
"""

from click.testing import CliRunner
import pytest
from apflow.cli.main import cli
from apflow.cli.cli_config import load_cli_config

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config_dir(monkeypatch, tmp_path):
    """
    Fixture to isolate test configuration from real config files.
    
    Uses APFLOW_CONFIG_DIR environment variable and patches config loading functions
    to point to a temporary directory, ensuring tests don't pollute the real config.cli.yaml file.
    """
    # Create temporary config directory
    test_config_dir = tmp_path / "test_config"
    test_config_dir.mkdir(parents=True, exist_ok=True)
    test_config_file = test_config_dir / "config.cli.yaml"
    
    # Set APFLOW_CONFIG_DIR to use test directory
    monkeypatch.setenv("APFLOW_CONFIG_DIR", str(test_config_dir))
    
    # Patch get_config_dir to return test directory
    from apflow.cli import cli_config
    original_get_config_dir = cli_config.get_config_dir
    original_get_all_cli_config_locations = cli_config.get_all_cli_config_locations
    original_get_cli_config_file_path = cli_config.get_cli_config_file_path
    
    def mock_get_config_dir():
        return test_config_dir
    
    def mock_get_all_cli_config_locations():
        """Return only test config file location."""
        return [test_config_file]
    
    def mock_get_cli_config_file_path():
        """Return test config file path."""
        return test_config_file
    
    monkeypatch.setattr(cli_config, "get_config_dir", mock_get_config_dir)
    monkeypatch.setattr(cli_config, "get_all_cli_config_locations", mock_get_all_cli_config_locations)
    monkeypatch.setattr(cli_config, "get_cli_config_file_path", mock_get_cli_config_file_path)
    
    yield test_config_dir
    
    # Cleanup: restore original functions
    monkeypatch.setattr(cli_config, "get_config_dir", original_get_config_dir)
    monkeypatch.setattr(cli_config, "get_all_cli_config_locations", original_get_all_cli_config_locations)
    monkeypatch.setattr(cli_config, "get_cli_config_file_path", original_get_cli_config_file_path)


class TestConfigCommand:
    """Test CLI config command."""

    def test_config_set_command(self):
        """Test config set command."""
        result = runner.invoke(
            cli,
            ["config", "set", "test_key", "test_value"],
        )
        assert result.exit_code == 0
        assert "✅" in result.stdout
        assert "test_key" in result.stdout

    def test_config_get_command(self):
        """Test config get command."""
        # First set a value
        runner.invoke(cli, ["config", "set", "test_key", "test_value"])

        # Then get it
        result = runner.invoke(cli, ["config", "get", "test_key"])
        assert result.exit_code == 0
        assert "test_value" in result.stdout

    def test_config_get_nonexistent(self):
        """Test config get for nonexistent key."""
        result = runner.invoke(cli, ["config", "get", "nonexistent_key_xyz"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_config_list_command(self):
        """Test config list command."""
        # Set some values
        runner.invoke(cli, ["config", "set", "key1", "value1"])
        runner.invoke(cli, ["config", "set", "key2", "value2"])

        # List configs
        result = runner.invoke(cli, ["config", "list"])
        assert result.exit_code == 0

    def test_config_list_json_format(self):
        """Test config list with JSON format."""
        runner.invoke(cli, ["config", "set", "key1", "value1"])

        result = runner.invoke(cli, ["config", "list", "-f", "json"])
        assert result.exit_code == 0
        assert "key1" in result.stdout

    def test_config_unset_command(self):
        """Test config unset command."""
        # First set a value
        runner.invoke(cli, ["config", "set", "key_to_delete", "value"])

        # Then unset it with --yes
        result = runner.invoke(
            cli,
            ["config", "unset", "key_to_delete", "--yes"],
        )
        assert result.exit_code == 0
        assert "✅" in result.stdout

    def test_config_init_server_default(self):
        """Test config init-server command with default URL."""
        result = runner.invoke(cli, ["config", "init-server"])
        assert result.exit_code == 0
        assert "✅" in result.stdout
        assert "localhost:8000" in result.stdout

    def test_config_init_server_custom_url(self):
        """Test config init-server command with custom URL."""
        result = runner.invoke(
            cli, ["config", "init-server", "--url", "http://prod-server.com:8000"]
        )
        assert result.exit_code == 0
        assert "✅" in result.stdout
        assert "prod-server.com:8000" in result.stdout

    def test_config_show_path(self):
        """Test config show-path command."""
        result = runner.invoke(cli, ["config", "show-path"])
        assert result.exit_code == 0
        assert "config.cli.yaml" in result.stdout

    def test_config_token_masking(self):
        """Test that tokens are masked in output."""
        # Set a token (using admin_auth_token)
        runner.invoke(cli, ["config", "set", "admin_auth_token", "secret-token-12345"])

        # Get it - should be masked (only first char + ...)
        result = runner.invoke(cli, ["config", "get", "admin_auth_token"])
        assert result.exit_code == 0
        assert "***" in result.stdout
        # Most of the token should be masked
        assert result.stdout.count("*") >= 3

    def test_config_list_shows_masked_tokens(self):
        """Test that list command shows masked tokens."""
        runner.invoke(cli, ["config", "set", "admin_auth_token", "secret-token"])

        result = runner.invoke(cli, ["config", "list"])
        assert result.exit_code == 0
        # Token should be masked
        if "secret" in result.stdout.lower():
            # If it appears, it should be in masked form
            assert "***" in result.stdout

    def test_config_set_admin_auth_token(self):
        """Test setting admin_auth_token."""
        result = runner.invoke(
            cli, ["config", "set", "admin_auth_token", "test-token-xyz"]
        )
        assert result.exit_code == 0
        assert "✅" in result.stdout

    def test_config_set_api_token_alias(self):
        """Test that api-token alias maps to admin_auth_token."""
        result = runner.invoke(
            cli, ["config", "set", "api-token", "test-token-xyz"]
        )
        assert result.exit_code == 0
        assert "✅" in result.stdout

        # Verify it was saved as admin_auth_token
        result = runner.invoke(cli, ["config", "get", "admin_auth_token"])
        assert result.exit_code == 0
        assert "***" in result.stdout  # Masked


class TestInitServerEnvSync:
    """Test init-server command with .env file synchronization."""

    def test_init_server_uses_env_jwt_secret(self, tmp_path, monkeypatch, isolated_config_dir):
        """Test that init-server uses APFLOW_JWT_SECRET from .env file."""
        # Create .env file with APFLOW_JWT_SECRET
        env_file = tmp_path / ".env"
        test_secret = "test-jwt-secret-from-env-12345"
        env_file.write_text(f"APFLOW_JWT_SECRET={test_secret}\n")

        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)
        # Clear any existing env var
        monkeypatch.delenv("APFLOW_JWT_SECRET", raising=False)

        # Run init-server command
        result = runner.invoke(cli, ["config", "init-server"])

        # Should succeed
        assert result.exit_code == 0
        assert "✅" in result.stdout
        assert "Using JWT secret from .env file" in result.stdout

        # Verify jwt_secret was saved to config
        config = load_cli_config()
        assert config.get("jwt_secret") == test_secret
        assert config.get("api_server_url") == "http://localhost:8000"
        assert "admin_auth_token" in config

    def test_init_server_generates_secret_when_env_not_set(self, tmp_path, monkeypatch, isolated_config_dir):
        """Test that init-server disables auth when .env doesn't have APFLOW_JWT_SECRET."""
        # Create .env file without APFLOW_JWT_SECRET
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_VAR=some_value\n")

        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)
        # Clear any existing env var
        monkeypatch.delenv("APFLOW_JWT_SECRET", raising=False)

        # Clear any existing jwt_secret from config to ensure fresh test
        config = load_cli_config()
        if "jwt_secret" in config:
            runner.invoke(cli, ["config", "unset", "jwt_secret", "--yes"])

        # Run init-server command
        result = runner.invoke(cli, ["config", "init-server"])

        # Should succeed
        assert result.exit_code == 0
        assert "✅" in result.stdout
        assert "authentication disabled" in result.stdout

        # Verify jwt_secret was NOT created and auth is disabled
        config = load_cli_config()
        assert "jwt_secret" not in config or not config.get("jwt_secret")
        assert config.get("api_server_url") == "http://localhost:8000"
        assert "admin_auth_token" not in config or not config.get("admin_auth_token")

    def test_init_server_generates_secret_when_no_env_file(self, tmp_path, monkeypatch, isolated_config_dir):
        """Test that init-server disables auth when .env file doesn't exist."""
        # Don't create .env file

        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)
        # Clear any existing env var
        monkeypatch.delenv("APFLOW_JWT_SECRET", raising=False)

        # Clear any existing jwt_secret from config to ensure fresh test
        config = load_cli_config()
        if "jwt_secret" in config:
            runner.invoke(cli, ["config", "unset", "jwt_secret", "--yes"])

        # Run init-server command
        result = runner.invoke(cli, ["config", "init-server"])

        # Should succeed
        assert result.exit_code == 0
        assert "✅" in result.stdout
        assert "authentication disabled" in result.stdout

        # Verify jwt_secret was NOT created and auth is disabled
        config = load_cli_config()
        assert "jwt_secret" not in config or not config.get("jwt_secret")
        assert config.get("api_server_url") == "http://localhost:8000"
        assert "admin_auth_token" not in config or not config.get("admin_auth_token")

    def test_init_server_env_secret_syncs_with_existing_config(self, tmp_path, monkeypatch, isolated_config_dir):
        """Test that env secret overrides existing jwt_secret in config."""
        # Create .env file with APFLOW_JWT_SECRET
        env_file = tmp_path / ".env"
        test_secret = "env-secret-override-67890"
        env_file.write_text(f"APFLOW_JWT_SECRET={test_secret}\n")

        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)
        # Clear any existing env var
        monkeypatch.delenv("APFLOW_JWT_SECRET", raising=False)

        # First, set an existing jwt_secret
        runner.invoke(cli, ["config", "set", "jwt_secret", "old-secret-123"])

        # Run init-server command
        result = runner.invoke(cli, ["config", "init-server"])

        # Should succeed and use env secret
        assert result.exit_code == 0
        assert "Using JWT secret from .env file" in result.stdout

        # Verify jwt_secret was overridden with env value
        config = load_cli_config()
        assert config.get("jwt_secret") == test_secret
        assert config.get("jwt_secret") != "old-secret-123"
