"""
Extension management for apflow

This module handles initialization and configuration of optional extensions.
Extensions are automatically detected based on installed dependencies.
"""

import os
from typing import Any, Optional, Dict
from apflow.core.execution.errors import ExecutorError
from apflow.logger import get_logger

logger = get_logger(__name__)

# Extension configuration: maps extension names to their dependencies and module paths
# This aligns with pyproject.toml optional-dependencies
EXTENSION_CONFIG: dict[str, dict[str, Any]] = {
    "core": {
        "dependencies": [],  # Core extension, always available
        "module": "apflow.extensions.core",
        "classes": [("AggregateResultsExecutor", "aggregate_results_executor")],
        "always_available": True,
    },
    "stdio": {
        "dependencies": [],  # Always available (stdlib)
        "module": "apflow.extensions.stdio",
        "classes": [
            ("SystemInfoExecutor", "system_info_executor"),
            ("CommandExecutor", "command_executor"),
        ],
        "always_available": True,
    },
    "crewai": {
        "dependencies": ["crewai"],  # From [crewai] extra
        "module": "apflow.extensions.crewai",
        "classes": [("CrewaiExecutor", "crewai_executor")],
    },
    "http": {
        "dependencies": ["httpx"],  # From [a2a] extra
        "module": "apflow.extensions.http",
        "classes": [("RestExecutor", "rest_executor")],
    },
    "ssh": {
        "dependencies": ["asyncssh"],  # From [ssh] extra
        "module": "apflow.extensions.ssh",
        "classes": [("SshExecutor", "ssh_executor")],
    },
    "docker": {
        "dependencies": ["docker"],  # From [docker] extra
        "module": "apflow.extensions.docker",
        "classes": [("DockerExecutor", "docker_executor")],
    },
    "grpc": {
        "dependencies": ["grpclib"],  # From [grpc] extra (pure-Python backend)
        "module": "apflow.extensions.grpc",
        "classes": [("GrpcExecutor", "grpc_executor")],
    },
    "websocket": {
        "dependencies": ["websockets"],  # From [a2a] extra
        "module": "apflow.extensions.websocket",
        "classes": [("WebSocketExecutor", "websocket_executor")],
    },
    "apflow": {
        "dependencies": [],  # Core extension, always available
        "module": "apflow.extensions.apflow",
        "classes": [("ApFlowApiExecutor", "apflow_api_executor")],
        "always_available": True,
    },
    "mcp": {
        "dependencies": [],  # Uses stdlib, always available
        "module": "apflow.extensions.mcp",
        "classes": [("McpExecutor", "mcp_executor")],
        "always_available": True,
    },
}


# Build mapping from executor_id to extension_name
# This allows loading a specific extension when an executor is requested
EXECUTOR_ID_TO_EXTENSION: dict[str, str] = {}
for ext_name, ext_config in EXTENSION_CONFIG.items():
    for _, executor_id in ext_config.get("classes", []):
        EXECUTOR_ID_TO_EXTENSION[executor_id] = ext_name


def _is_package_installed(package_name: str) -> bool:
    """
    Check if a package is installed using importlib.metadata

    For standard library packages, this function tries to import them directly.
    For third-party packages, it checks installed distributions.

    This function handles various import-related errors, including:
    - ImportError: Package not installed
    - ModuleNotFoundError: Package not found (Python 3.6+)
    - AttributeError: Dependency chain version incompatibility (e.g., pycares/aiodns)
    - Other exceptions: Unexpected errors during import

    Args:
        package_name: Package name to check (e.g., "crewai", "httpx", "os")

    Returns:
        True if package is installed/available, False otherwise
    """
    # First, try importing directly (works for stdlib and installed packages)
    try:
        __import__(package_name)
        return True
    except (ImportError, ModuleNotFoundError):
        # If direct import fails, check installed distributions
        # This handles cases where package name differs from import name
        pass
    except (AttributeError, TypeError, ValueError) as e:
        # Handle dependency chain errors:
        # - AttributeError: Version incompatibility in dependency chain
        #   (e.g., pycares 5.0.0 removed ares_query_a_result, breaking aiodns)
        # - TypeError/ValueError: Other dependency-related errors
        # Log the issue but continue to check installed distributions
        # The package may be installed but not importable due to dependency issues
        logger.debug(
            f"Package {package_name} has dependency issues during import: {e}. "
            f"Will check installed distributions."
        )
        # Continue to check installed distributions below
        pass
    except Exception as e:
        # Catch-all for any other unexpected errors during import
        # This is defensive programming - we don't want package detection to crash
        logger.debug(
            f"Unexpected error importing package {package_name}: {e}. "
            f"Will check installed distributions."
        )
        # Continue to check installed distributions below
        pass

    # Check installed distributions for third-party packages
    try:
        # Python 3.8+ has importlib.metadata in stdlib
        from importlib.metadata import distributions
    except ImportError:
        # Python 3.7 fallback (shouldn't be needed as we require 3.10+)
        try:
            from importlib_metadata import distributions
        except ImportError:
            return False

    # Check all installed distributions
    for dist in distributions():
        # Normalize package name (handle case differences, hyphens vs underscores)
        dist_name = dist.metadata.get("Name", "").lower().replace("-", "_")
        package_normalized = package_name.lower().replace("-", "_")

        if dist_name == package_normalized:
            return True

    return False


def get_extension_env() ->Optional[str]:
    """
    Get the value of the APFLOW_EXTENSIONS environment variable

    Returns:
        The value of APFLOW_EXTENSIONS, or None if not set
    """
    return os.getenv("APFLOW_EXTENSIONS")


def get_allowed_executor_ids() -> Optional[set[str]]:
    """
    Get the set of allowed executor IDs from environment configuration

    If APFLOW_EXTENSIONS is set, only executors from those extensions are allowed.
    This provides security control to restrict which executors users can access.

    Returns:
        Set of allowed executor IDs, or None if no restrictions (allow all)

    Example:
        APFLOW_EXTENSIONS=stdio,http -> Only stdio and http executors allowed
        APFLOW_EXTENSIONS not set -> All executors allowed (no restrictions)
    """
    extensions_env = get_extension_env()
    if extensions_env is None:
        return None  # No restrictions
    
    extensions_env = extensions_env.strip()
    # Parse enabled extensions
    enabled_extensions = [e.strip().lower() for e in extensions_env.split(",") if e.strip()]
    
    if not enabled_extensions:
        return None  # Empty or whitespace-only treated as no restrictions

    # Collect executor IDs from enabled extensions
    allowed_executor_ids: set[str] = set()
    for ext_name in enabled_extensions:
        ext_config = EXTENSION_CONFIG.get(ext_name)
        if ext_config:
            # Get executor IDs from this extension
            for _, executor_id in ext_config.get("classes", []):
                allowed_executor_ids.add(executor_id)

    return allowed_executor_ids


# Track whether all extensions have been loaded
_all_extensions_loaded = False

_loaded_extensions: Dict[str, bool] = {}  # Track which extensions have been loaded
    

def load_extension_by_name(extension_name: str) -> None:
    """
    Load a specific extension by name.
    
    Args:
        extension_name: Name of the extension to load
    """
    global _loaded_extensions
    ext_config = EXTENSION_CONFIG.get(extension_name)
    if not ext_config:
        raise ValueError(f"Unknown extension: {extension_name}")
    
    # Check dependencies if not always available
    if not ext_config.get("always_available", False):
        dependencies = ext_config.get("dependencies", [])
        missing_deps = [dep for dep in dependencies if not _is_package_installed(dep)]
        if missing_deps:
            logger.warning(f"Extension '{extension_name}' skipped: missing dependencies {missing_deps}")
            return
    
    module_path = ext_config["module"]
    classes = ext_config["classes"]
    
    # Check if executors are already registered (in case registry was cleared)
    from apflow.core.extensions import get_registry
    registry = get_registry()
    all_registered = True
    for _, executor_id in classes:
        if not registry.is_registered(executor_id):
            all_registered = False
            break
    
    # If already loaded and all executors registered, nothing to do
    if _loaded_extensions.get(extension_name) and all_registered:
        return
    
    # Load the module (this will trigger decorator registration if not already imported)
    try:
        module = __import__(module_path, fromlist=[cls[0] for cls in classes])
        logger.debug(f"Loaded extension '{extension_name}', module: {module.__name__}")
        
        # If module was already imported but executors not registered, manually register them
        if _loaded_extensions.get(extension_name) and not all_registered:
            from apflow.core.extensions.decorators import _register_extension
            from apflow.core.extensions.types import ExtensionCategory
            for class_name, executor_id in classes:
                if not registry.is_registered(executor_id):
                    try:
                        executor_class = getattr(module, class_name)
                        _register_extension(executor_class, ExtensionCategory.EXECUTOR, override=True)
                        logger.debug(f"Manually re-registered executor '{executor_id}' from extension '{extension_name}'")
                    except (AttributeError, Exception) as e:
                        logger.warning(f"Failed to re-register executor '{executor_id}': {e}")
        
        _loaded_extensions[extension_name] = True
    except Exception as e:
        logger.warning(f"Failed to load extension {extension_name}: {e}")


def load_extension_by_id(executor_id: str) -> None:
    """
    Load extension for a specific executor ID.
    
    This is used when executing a task - loads only the extension needed
    for that executor, avoiding unnecessary loading of all extensions.
    
    Args:
        executor_id: Executor ID (e.g., "system_info_executor", "rest_executor")
    """
    ext_name = EXECUTOR_ID_TO_EXTENSION.get(executor_id)
    if ext_name:
        load_extension_by_name(ext_name)
    else:
        raise ExecutorError(f"Unknown executor: {executor_id}")



def _load_all_extensions() -> None:
    """
    Dynamically load all extension modules to register executors.
    
    This function is called when listing available executors to ensure
    the registry contains all available executors. Extensions are loaded
    on-demand rather than at startup to minimize startup time.
    
    Respects APFLOW_EXTENSIONS environment variable - if set, only loads
    specified extensions for security and performance reasons.
    
    This function checks the current APFLOW_EXTENSIONS setting each time
    and only loads extensions that haven't been loaded yet. This ensures
    that changes to APFLOW_EXTENSIONS are respected.
    """
    # Check if APFLOW_EXTENSIONS is set - if so, only load specified extensions
    extensions_env = get_extension_env()
    if extensions_env:
        # Parse enabled extensions from environment
        enabled_extensions = [e.strip().lower() for e in extensions_env.split(",") if e.strip()]
        extensions_to_load = [ext_name for ext_name in EXTENSION_CONFIG.keys() 
                            if ext_name.lower() in enabled_extensions]
        logger.debug(f"APFLOW_EXTENSIONS set, loading only specified extensions: {extensions_to_load}")
    else:
        # Load all extensions if no restrictions
        extensions_to_load = list(EXTENSION_CONFIG.keys())
        logger.debug("No APFLOW_EXTENSIONS restriction, loading all extensions")
    
    # Load extensions that haven't been loaded yet or need re-registration
    # load_extension_by_name() will check if executors are registered and
    # re-register them if needed (e.g., after registry was cleared)
    for ext_name in extensions_to_load:
        load_extension_by_name(ext_name)


def get_available_executors() -> dict[str, Any]:
    """
    Get list of available executors based on APFLOW_EXTENSIONS configuration

    This function returns metadata for all executors that are currently accessible,
    considering APFLOW_EXTENSIONS restrictions. Used by API/CLI to show users
    which executors they can use.

    Returns:
        Dictionary with:
            - executors: List of available executor metadata
            - restricted: Boolean indicating if access is restricted by APFLOW_EXTENSIONS
            - allowed_ids: List of allowed executor IDs (if restricted)

    Example:
        {
            "executors": [
                {"id": "system_info_executor", "name": "System Info", ...},
                {"id": "command_executor", "name": "Command", ...}
            ],
            "restricted": True,
            "allowed_ids": ["system_info_executor", "command_executor"]
        }
    """
    from apflow.core.extensions import get_all_executor_metadata

    # Load all extensions to populate registry
    _load_all_extensions()

    # Get all executor metadata from registry
    all_metadata = get_all_executor_metadata()

    # Check if access is restricted
    allowed_executor_ids = get_allowed_executor_ids()
    is_restricted = allowed_executor_ids is not None

    # Filter executors based on restrictions
    if is_restricted:
        available_metadata = {
            executor_id: metadata
            for executor_id, metadata in all_metadata.items()
            if executor_id in allowed_executor_ids
        }
    else:
        available_metadata = all_metadata

    # Convert to list format
    executors_list = [
        {"id": executor_id, **metadata}
        for executor_id, metadata in available_metadata.items()
    ]

    result = {
        "executors": executors_list,
        "count": len(executors_list),
        "restricted": is_restricted,
    }

    if is_restricted:
        result["allowed_ids"] = sorted(allowed_executor_ids)

    return result


def _ensure_extension_registered(executor_class: Any, extension_id: str) -> None:
    """
    Ensure an extension is registered in the registry

    This function checks if an extension is already registered, and if not,
    manually registers it. This handles the case where modules were imported
    before but the registry was cleared (e.g., in tests).

    Args:
        executor_class: Executor class to register
        extension_id: Expected extension ID
    """
    from apflow.core.extensions import get_registry

    registry = get_registry()

    # If already registered, nothing to do
    if registry.is_registered(extension_id):
        return

    # Module was imported but extension not registered (e.g., registry was cleared)
    # Manually register it
    try:
        from apflow.core.extensions.decorators import _register_extension
        from apflow.core.extensions.types import ExtensionCategory

        _register_extension(executor_class, ExtensionCategory.EXECUTOR, override=True)
        logger.debug(f"Manually registered extension '{extension_id}'")
    except Exception as reg_error:
        logger.warning(f"Failed to manually register {executor_class.__name__}: {reg_error}")


def _load_custom_task_model() -> None:
    """Load custom TaskModel class from environment variable if specified"""
    task_model_class_path = os.getenv("APFLOW_TASK_MODEL_CLASS")
    if task_model_class_path:
        try:
            from importlib import import_module

            from apflow import set_task_model_class

            module_path, class_name = task_model_class_path.rsplit(".", 1)
            module = import_module(module_path)
            task_model_class = getattr(module, class_name)
            set_task_model_class(task_model_class)
            logger.info(f"Loaded custom TaskModel: {task_model_class_path}")
        except Exception as e:
            logger.warning(f"Failed to load custom TaskModel from {task_model_class_path}: {e}")



def initialize_extensions() -> None:
    """
    Initialize apflow extensions intelligently

    """
    logger.info("Initializing apflow extensions...")

    _load_all_extensions()
    # Load custom TaskModel
    _load_custom_task_model()

    logger.info("Extension initialization completed")

