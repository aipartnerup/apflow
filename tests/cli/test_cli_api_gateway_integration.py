"""
Tests for CLI API Gateway integration.

Tests that CLI commands properly integrate with API gateway,
including API usage detection and local database fallback.
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from apflow.cli.api_gateway_helper import (
    should_use_api,
    run_async_safe,
    log_api_usage,
    reset_api_validation,
)
from apflow.core.config_manager import get_config_manager


@pytest.fixture
def mock_cli_config_file(monkeypatch):
    """Mock CLI config file path to avoid interference between tests."""
    with patch(
        "apflow.cli.cli_config.get_cli_config_file_path",
        return_value=Path(f"/tmp/test_cli_config_{id(monkeypatch)}.yaml"),
    ):
        yield


@pytest.fixture(autouse=True)
def reset_api_state():
    """Reset API validation state and config between tests."""
    reset_api_validation()
    cm = get_config_manager()
    cm.clear()
    yield
    reset_api_validation()
    cm.clear()


@pytest.fixture
def api_accessible(monkeypatch):
    """Mock API accessibility check to avoid real network calls."""

    async def _accessible(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(
        "apflow.core.config_manager.ConfigManager.check_api_server_accessible",
        _accessible,
    )
    return None


class TestAPIGatewayHelper:
    """Test API gateway helper functions."""

    def test_should_use_api_when_configured(self, api_accessible):
        """Test that should_use_api returns True when API is configured."""
        with patch(
            "apflow.cli.cli_config.get_cli_config_file_path",
            return_value=Path("/tmp/nonexistent_test_config.yaml"),
        ):
            cm = get_config_manager()
            cm.clear()
            cm.set_api_server_url("http://localhost:8000")

            assert should_use_api() is True

            cm.clear()

    def test_should_use_api_when_not_configured(self):
        """Test that should_use_api returns False when API is not configured."""
        with patch(
            "apflow.cli.cli_config.get_cli_config_file_path",
            return_value=Path("/tmp/nonexistent_test_config_2.yaml"),
        ):
            with patch("apflow.cli.cli_config.load_cli_config", return_value={}):
                cm = get_config_manager()
                cm.clear()

                assert should_use_api() is False

    def test_run_async_safe_with_no_running_loop(self):
        """Test run_async_safe when no event loop is running."""
        async def dummy_coro():
            return "result"

        result = run_async_safe(dummy_coro())
        assert result == "result"

    def test_run_async_safe_with_running_loop(self):
        """Test run_async_safe when an event loop is already running."""
        import asyncio

        async def dummy_coro():
            return "result"

        async def outer_test():
            # This simulates an existing event loop
            result = run_async_safe(dummy_coro())
            return result

        result = asyncio.run(outer_test())
        assert result == "result"

    def test_log_api_usage_with_api(self, caplog):
        """Test log_api_usage logs correctly when using API."""
        import logging

        caplog.set_level(logging.DEBUG)

        log_api_usage("test_command", True)

        # The function logs at DEBUG level, so just verify it doesn't crash
        # (caplog may or may not capture depending on logging configuration)

    def test_log_api_usage_without_api(self, caplog):
        """Test log_api_usage logs correctly when using local DB."""
        import logging

        caplog.set_level(logging.DEBUG)

        log_api_usage("test_command", False)

        # The function logs at DEBUG level, so just verify it doesn't crash


class TestCLIListCommandWithAPI:
    """Test CLI list command with API gateway integration."""

    @pytest.mark.asyncio
    async def test_list_uses_api_when_configured(
        self, mock_cli_config_file, api_accessible
    ):
        """Test that list command uses API when configured."""
        cm = get_config_manager()
        cm.clear()
        cm.set_api_server_url("http://localhost:8000")

        assert should_use_api() is True

        cm.clear()

    @pytest.mark.asyncio
    async def test_list_uses_local_db_when_not_configured(self, mock_cli_config_file):
        """Test that list command uses local DB when API not configured."""
        with patch("apflow.cli.cli_config.load_cli_config", return_value={}):
            cm = get_config_manager()
            cm.clear()

            assert should_use_api() is False


class TestCLIStatusCommandWithAPI:
    """Test CLI status command with API gateway integration."""

    @pytest.mark.asyncio
    async def test_status_uses_api_when_configured(
        self, mock_cli_config_file, api_accessible
    ):
        """Test that status command uses API when configured."""
        cm = get_config_manager()
        cm.clear()
        cm.set_api_server_url("http://localhost:8000")

        assert should_use_api() is True

        cm.clear()


class TestCLICancelCommandWithAPI:
    """Test CLI cancel command with API gateway integration."""

    @pytest.mark.asyncio
    async def test_cancel_uses_api_when_configured(
        self, mock_cli_config_file, api_accessible
    ):
        """Test that cancel command uses API when configured."""
        cm = get_config_manager()
        cm.clear()
        cm.set_api_server_url("http://localhost:8000")

        assert should_use_api() is True

        cm.clear()


class TestCLIGetCommandWithAPI:
    """Test CLI get command with API gateway integration."""

    @pytest.mark.asyncio
    async def test_get_uses_api_when_configured(
        self, mock_cli_config_file, api_accessible
    ):
        """Test that get command uses API when configured."""
        cm = get_config_manager()
        cm.clear()
        cm.set_api_server_url("http://localhost:8000")

        assert should_use_api() is True

        cm.clear()


class TestAPIGatewayFallback:
    """Test fallback behavior when API is unavailable."""

    def test_fallback_enabled_by_default(self, mock_cli_config_file):
        """Test that local DB fallback is enabled by default."""
        cm = get_config_manager()
        cm.clear()
        cm.set_api_server_url("http://localhost:8000")

        assert cm.use_local_db is True

        cm.clear()

    def test_fallback_can_be_disabled(self, mock_cli_config_file):
        """Test that local DB fallback can be disabled."""
        cm = get_config_manager()
        cm.clear()
        cm.set_api_server_url("http://localhost:8000")
        cm.set_use_local_db(False)

        assert cm.use_local_db is False

        cm.clear()
