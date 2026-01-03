"""
Configuration persistence module for APFlow CLI and API.

Handles saving/loading configuration with multi-location and multi-file support:

File Structure:
  config.json   - Non-sensitive configuration (shared between CLI & API)
  secrets.json  - Sensitive configuration (API auth tokens, JWT secrets)

Location Priority:
  1. APFLOW_CONFIG_DIR environment variable (highest priority)
  2. Project-local: <project_root>/.data/ (if in project)
  3. User-global: ~/.aipartnerup/apflow/ (default fallback)

Permissions:
  config.json  - 644 (readable by all, writable by owner)
  secrets.json - 600 (readable/writable by owner only)

Environment Variables:
  APFLOW_CONFIG_DIR: Override config directory location (highest priority)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from apflow.logger import get_logger

logger = get_logger(__name__)

# User-global configuration (default)
USER_CONFIG_DIR = Path.home() / ".aipartnerup" / "apflow"

# Configuration file names
CONFIG_FILE = "config.json"      # Non-sensitive configuration
SECRETS_FILE = "secrets.json"    # Sensitive configuration (API tokens, JWT)


def get_project_root() -> Optional[Path]:
    """
    Find project root by looking for pyproject.toml or .git directory.

    Walks up the directory tree from current working directory
    until it finds a project marker or reaches filesystem root.

    Returns:
        Project root path if found, None otherwise
    """
    current = Path.cwd()

    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        # Check for project markers
        if (parent / "pyproject.toml").exists() or (
            parent / ".git"
        ).exists():
            logger.debug(f"Found project root: {parent}")
            return parent

    return None


def get_project_config_dir() -> Optional[Path]:
    """
    Get project-local config directory if in project context.

    Returns:
        <project_root>/.data if in project, None otherwise
    """
    project_root = get_project_root()
    if project_root:
        return project_root / ".data"
    return None


def get_config_dir() -> Path:
    """
    Get the appropriate config directory based on context and environment.

    Priority order:
    1. APFLOW_CONFIG_DIR environment variable
    2. Project-local <project_root>/.data (if in project)
    3. User-global ~/.aipartnerup/apflow (default)

    Returns:
        Path to config directory
    """
    # Check environment variable override
    env_config_dir = os.getenv("APFLOW_CONFIG_DIR")
    if env_config_dir:
        return Path(env_config_dir)

    # Check if we're in a project and use project-local config
    project_config_dir = get_project_config_dir()
    if project_config_dir:
        return project_config_dir

    # Default to user-global config
    return USER_CONFIG_DIR


def get_all_config_locations() -> list[Path]:
    """
    Get all possible config file locations in priority order.

    Returns:
        List of config.json paths in priority order
    """
    project_config_dir = get_project_config_dir()
    locations = []

    # Add project-local if applicable
    if project_config_dir:
        locations.append(project_config_dir / CONFIG_FILE)

    # Add user-global
    locations.append(USER_CONFIG_DIR / CONFIG_FILE)

    return locations


def get_all_secrets_locations() -> list[Path]:
    """
    Get all possible secrets file locations in priority order.

    Returns:
        List of secrets.json paths in priority order
    """
    project_config_dir = get_project_config_dir()
    locations = []

    # Add project-local if applicable
    if project_config_dir:
        locations.append(project_config_dir / SECRETS_FILE)

    # Add user-global
    locations.append(USER_CONFIG_DIR / SECRETS_FILE)

    return locations


def get_config_file_path(filename: str = CONFIG_FILE) -> Path:
    """
    Get the path to a config file for reading/writing.

    For reading: Returns path to first existing file in priority order
    For writing: Returns path where config should be saved (respects priority)

    Args:
        filename: "config.json" or "secrets.json"

    Returns:
        Path to config file
    """
    # Check environment variable override
    env_config_dir = os.getenv("APFLOW_CONFIG_DIR")
    if env_config_dir:
        return Path(env_config_dir) / filename

    # Check if we're in a project and use project-local config
    project_config_dir = get_project_config_dir()
    if project_config_dir:
        return project_config_dir / filename

    # Default to user-global config
    return USER_CONFIG_DIR / filename


def ensure_config_dir() -> None:
    """Ensure the configuration directory exists."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)


def load_cli_config() -> dict:
    """
    Load CLI configuration from config.json.

    Checks multiple locations in priority order:
    1. Project-local: .data/config.json
    2. User-global: ~/.aipartnerup/apflow/config.json

    Returns:
        Dictionary with config, empty dict if no config found
    """
    for config_path in get_all_config_locations():
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    logger.debug(f"Loaded config from {config_path}")
                    return config
            except Exception as e:
                logger.warning(
                    f"Failed to load config from {config_path}: {e}"
                )
                continue

    logger.debug("No config found, using empty config")
    return {}


def save_cli_config(config: dict) -> None:
    """
    Save CLI configuration to config.json.

    Saves to appropriate location based on context:
    - Project-local if in project context
    - User-global otherwise

    Sets file permissions to 644 (readable by all).

    Args:
        config: Configuration dictionary to save
    """
    ensure_config_dir()
    config_file = get_config_file_path(CONFIG_FILE)

    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        # Set readable permissions (644)
        config_file.chmod(0o644)
        logger.debug(f"Saved config to {config_file}")
    except Exception as e:
        logger.error(f"Failed to save config to {config_file}: {e}")
        raise


def load_secrets_config() -> dict:
    """
    Load sensitive configuration from secrets.json.

    Checks multiple locations in priority order:
    1. Project-local: .data/secrets.json
    2. User-global: ~/.aipartnerup/apflow/secrets.json

    Returns:
        Dictionary with secrets, empty dict if no file found
    """
    for secrets_path in get_all_secrets_locations():
        if secrets_path.exists():
            try:
                with open(secrets_path, "r") as f:
                    secrets = json.load(f)
                    logger.debug(f"Loaded secrets from {secrets_path}")
                    return secrets
            except Exception as e:
                logger.warning(
                    f"Failed to load secrets from {secrets_path}: {e}"
                )
                continue

    logger.debug("No secrets file found, using empty secrets")
    return {}


def save_secrets_config(secrets: dict) -> None:
    """
    Save sensitive configuration to secrets.json.

    Saves to appropriate location based on context:
    - Project-local if in project context
    - User-global otherwise

    Sets file permissions to 600 (owner-only access).

    Args:
        secrets: Secrets dictionary to save
    """
    ensure_config_dir()
    secrets_file = get_config_file_path(SECRETS_FILE)

    try:
        with open(secrets_file, "w") as f:
            json.dump(secrets, f, indent=2)

        # Set restricted permissions (600 - owner only)
        secrets_file.chmod(0o600)
        logger.debug(f"Saved secrets to {secrets_file}")
    except Exception as e:
        logger.error(f"Failed to save secrets to {secrets_file}: {e}")
        raise


def generate_admin_token() -> str:
    """
    Generate a JWT admin token for localhost.
    
    Uses local JWT secret for consistency.
    Sets admin role in token claims.
    
    Returns:
        JWT admin token string
    """
    from apflow.cli.jwt_token import generate_token
    
    token = generate_token(
        subject="admin",
        extra_claims={"role": "admin"},
        expiry_days=365,
    )
    return token


def get_config_value(key: str) -> Optional[str]:
    """
    Get a configuration value from config.json or secrets.json.

    Checks both non-sensitive and sensitive config.

    Args:
        key: Configuration key

    Returns:
        Configuration value or None if not found
    """
    # Try config.json first
    config = load_cli_config()
    if key in config:
        return config.get(key)

    # Then try secrets.json
    secrets = load_secrets_config()
    return secrets.get(key)


def set_config_value(key: str, value: Optional[str], is_sensitive: bool = False) -> None:
    """
    Set a configuration value in the appropriate config file.

    Args:
        key: Configuration key
        value: Configuration value (None to delete)
        is_sensitive: If True, saves to secrets.json; otherwise config.json
    """
    if is_sensitive:
        secrets = load_secrets_config()
        if value is None:
            secrets.pop(key, None)
        else:
            secrets[key] = value
        save_secrets_config(secrets)
    else:
        config = load_cli_config()
        if value is None:
            config.pop(key, None)
        else:
            config[key] = value
        save_cli_config(config)


def list_config_values() -> dict:
    """
    List all configuration values.

    Sensitive values (tokens) are masked.

    Returns:
        Dictionary of configuration values with tokens masked
    """
    config = load_cli_config()
    secrets = load_secrets_config()

    # Combine and mask
    display_config = {}

    # Add non-sensitive config
    for key, value in config.items():
        display_config[key] = value

    # Add sensitive values from secrets (masked)
    for key, value in secrets.items():
        if isinstance(value, str) and len(value) > 3:
            display_config[key] = f"{value[:3]}...***"
        else:
            display_config[key] = "***"

    return display_config
