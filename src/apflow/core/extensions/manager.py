"""
Extension management for apflow

This module handles initialization and configuration of optional extensions.
Extensions are automatically detected using AST-based scanning (no imports).
"""

import os
from typing import Any, Optional, Dict
from apflow.core.execution.errors import ExecutorError
from apflow.core.extensions.scanner import ExtensionScanner
from apflow.logger import get_logger

logger = get_logger(__name__)


# DEPRECATED: EXTENSION_CONFIG is no longer used
# Extensions are now auto-discovered via ExtensionScanner
# This is kept for backward compatibility (will be removed in future version)
EXTENSION_CONFIG: dict[str, dict[str, Any]] = {}

# DEPRECATED: EXECUTOR_ID_TO_EXTENSION is no longer used
# Use ExtensionScanner.get_executor_metadata() instead
EXECUTOR_ID_TO_EXTENSION: dict[str, str] = {}


def _is_package_installed(package_name: str) -> bool:
    """
    Check if a package is installed WITHOUT importing it (lazy loading safe)

    Uses importlib.metadata to check installed distributions without importing.
    This is critical for CLI --help performance and lazy loading architecture.

    Args:
        package_name: Package name to check (e.g., "httpx", "docker")

    Returns:
        True if package is installed, False otherwise
    """
    try:
        # Python 3.8+ has importlib.metadata in stdlib
        from importlib.metadata import distributions
    except ImportError:
        # Python 3.7 fallback (shouldn't be needed as we require 3.10+)
        try:
            from importlib_metadata import distributions
        except ImportError:
            return False

    # Check all installed distributions WITHOUT importing
    for dist in distributions():
        # Normalize package name (handle case differences, hyphens vs underscores)
        dist_name = dist.metadata.get("Name", "").lower().replace("-", "_")
        package_normalized = package_name.lower().replace("-", "_")

        if dist_name == package_normalized:
            return True

    return False


def get_extension_env() -> Optional[str]:
    """
    Get the value of the APFLOW_EXTENSIONS environment variable

    Returns:
        The value of APFLOW_EXTENSIONS, or None if not set
    """
    return os.getenv("APFLOW_EXTENSIONS")


def get_allowed_executor_ids() -> Optional[set[str]]:
    """
    Get the set of allowed executor IDs from environment configuration

    If APFLOW_EXTENSIONS is set, only those executor IDs are allowed.
    This provides security control to restrict which executors users can access.

    Returns:
        Set of allowed executor IDs, or None if no restrictions (allow all)

    Example:
        APFLOW_EXTENSIONS=rest_executor,command_executor -> Only these executors allowed
        APFLOW_EXTENSIONS not set -> All executors allowed (no restrictions)
    """
    extensions_env = get_extension_env()
    if extensions_env is None:
        return None

    extensions_env = extensions_env.strip()
    enabled_ids = [e.strip() for e in extensions_env.split(",") if e.strip()]

    if not enabled_ids:
        return None

    return set(enabled_ids)


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
            logger.warning(
                f"Extension '{extension_name}' skipped: missing dependencies {missing_deps}"
            )
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
                        _register_extension(
                            executor_class, ExtensionCategory.EXECUTOR, override=True
                        )
                        logger.debug(
                            f"Manually re-registered executor '{executor_id}' from extension '{extension_name}'"
                        )
                    except (AttributeError, Exception) as e:
                        logger.warning(f"Failed to re-register executor '{executor_id}': {e}")

        _loaded_extensions[extension_name] = True
    except Exception as e:
        logger.warning(f"Failed to load extension {extension_name}: {e}")


def load_extension_by_id(executor_id: str) -> None:
    """
    Load extension for a specific executor ID (LAZY - imports only when called)

    This is called ONLY when actually executing a task with that executor.
    CLI --help or listing executors does NOT trigger this function.

    Uses ExtensionScanner to get metadata (no import), then imports only
    the specific executor module when dependencies are satisfied.

    Args:
        executor_id: Executor ID (e.g., "system_info_executor", "rest_executor")

    Raises:
        ExecutorError: If executor not found or dependencies missing
    """
    metadata = ExtensionScanner.get_executor_metadata(executor_id)

    if not metadata:
        raise ExecutorError(f"Unknown executor: {executor_id}")

    from apflow.core.extensions import get_registry

    registry = get_registry()
    if registry.is_registered(executor_id):
        logger.debug(f"Executor '{executor_id}' already loaded")
        return

    if not metadata.always_available:
        missing_deps = [dep for dep in metadata.dependencies if not _is_package_installed(dep)]
        if missing_deps:
            raise ExecutorError(f"Executor '{executor_id}' requires: {', '.join(missing_deps)}")

    logger.debug(f"Lazy loading executor '{executor_id}' from {metadata.module_path}")

    try:
        module = __import__(metadata.module_path, fromlist=[metadata.class_name])

        if not registry.is_registered(executor_id):
            executor_class = getattr(module, metadata.class_name)
            from apflow.core.extensions.decorators import _register_extension
            from apflow.core.extensions.types import ExtensionCategory

            _register_extension(executor_class, ExtensionCategory.EXECUTOR, override=True)

        logger.info(f"Loaded executor '{executor_id}'")

    except Exception as e:
        logger.error(f"Failed to load executor '{executor_id}': {e}")
        raise ExecutorError(f"Failed to load executor '{executor_id}': {e}")


def _load_all_extensions() -> None:
    """
    Load all available extensions (LAZY - only on-demand)

    Scans extensions directory using AST (no imports) and loads executors
    based on APFLOW_EXTENSIONS environment variable.

    This function is called when listing available executors to ensure
    the registry contains all available executors.
    """
    ExtensionScanner.scan_builtin_executors()

    extensions_env = get_extension_env()
    if extensions_env:
        enabled_ids = [e.strip() for e in extensions_env.split(",") if e.strip()]
        executor_ids_to_load = enabled_ids
        logger.debug(f"APFLOW_EXTENSIONS set, loading: {executor_ids_to_load}")
    else:
        executor_ids_to_load = ExtensionScanner.get_all_executor_ids()
        logger.debug(f"Loading all {len(executor_ids_to_load)} discovered executors")

    for executor_id in executor_ids_to_load:
        try:
            load_extension_by_id(executor_id)
        except ExecutorError as e:
            logger.warning(f"Skipped executor '{executor_id}': {e}")


def get_available_executors() -> dict[str, Any]:
    """
    Get list of available executors (NO IMPORTS - fast)

    This function returns metadata for all executors without importing them.
    Used by CLI --help and API listing endpoints for fast startup.

    Returns:
        Dictionary with:
            - executors: List of available executor metadata
            - restricted: Boolean indicating if access is restricted by APFLOW_EXTENSIONS
            - allowed_ids: List of allowed executor IDs (if restricted)
    """
    ExtensionScanner.scan_builtin_executors()

    all_executor_ids = ExtensionScanner.get_all_executor_ids()

    allowed_executor_ids = get_allowed_executor_ids()
    is_restricted = allowed_executor_ids is not None

    if is_restricted:
        available_ids = [
            eid for eid in all_executor_ids if allowed_executor_ids and eid in allowed_executor_ids
        ]
    else:
        available_ids = all_executor_ids

    executors_list = []
    for executor_id in available_ids:
        metadata = ExtensionScanner.get_executor_metadata(executor_id)
        if metadata:
            executors_list.append(
                {
                    "id": metadata.id,
                    "name": metadata.name,
                    "description": metadata.description,
                    "tags": metadata.tags,
                    "dependencies": metadata.dependencies,
                    "available": metadata.always_available
                    or all(_is_package_installed(dep) for dep in metadata.dependencies),
                }
            )

    result = {
        "executors": executors_list,
        "count": len(executors_list),
        "restricted": is_restricted,
    }

    if is_restricted and allowed_executor_ids:
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
