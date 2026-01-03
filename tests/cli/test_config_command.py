"""
Tests for CLI config command.
"""

from click.testing import CliRunner
from apflow.cli.main import cli

runner = CliRunner()


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
        result = runner.invoke(cli, ["config", "init-server", "--url", "http://prod-server.com:8000"])
        assert result.exit_code == 0
        assert "✅" in result.stdout
        assert "prod-server.com:8000" in result.stdout
    
    def test_config_show_path(self):
        """Test config show-path command."""
        result = runner.invoke(cli, ["config", "show-path"])
        assert result.exit_code == 0
        assert ".aipartnerup" in result.stdout or "apflow" in result.stdout.lower()
    
    def test_config_token_masking(self):
        """Test that tokens are masked in output."""
        # Set a token
        runner.invoke(cli, ["config", "set", "api_auth_token", "secret-token-12345"])
        
        # Get it - should be masked (only first char + ...)
        result = runner.invoke(cli, ["config", "get", "api_auth_token"])
        assert result.exit_code == 0
        assert "***" in result.stdout
        # Most of the token should be masked
        assert result.stdout.count("*") >= 3
    
    def test_config_list_shows_masked_tokens(self):
        """Test that list command shows masked tokens."""
        runner.invoke(cli, ["config", "set", "api_auth_token", "secret-token"])
        
        result = runner.invoke(cli, ["config", "list"])
        assert result.exit_code == 0
        # Token should be masked
        if "secret" in result.stdout.lower():
            # If it appears, it should be in masked form
            assert "***" in result.stdout
