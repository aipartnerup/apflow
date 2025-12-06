"""
Main entry point for aipartnerupflow API service

This is the application layer where environment variables can be used
for service deployment configuration.

Supports multiple network protocols:
- A2A Protocol Server (default): Agent-to-Agent communication protocol
- REST API (future): Direct HTTP REST endpoints

Protocol selection via AIPARTNERUPFLOW_API_PROTOCOL environment variable:
- "a2a" (default): A2A Protocol Server
- "rest" (future): REST API server
"""

import os
import sys
import warnings
import uvicorn
import time
from typing import Optional, Any

from aipartnerupflow.core.utils.helpers import get_url_with_host_and_port
from aipartnerupflow.core.utils.logger import get_logger

# Suppress specific warnings for cleaner output
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")

# Add project root to Python path for development
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# Initialize logger
logger = get_logger(__name__)
start_time = time.time()
logger.info("Starting aipartnerupflow service")

# Protocol dependency mapping: protocol -> (module_path, extra_name, description)
# This is the single source of truth for protocol configuration
PROTOCOL_DEPENDENCIES = {
    "a2a": (
        "aipartnerupflow.api.a2a.server",
        "a2a",
        "A2A Protocol Server",
    ),
    # Future protocols can be added here:
    # "rest": (
    #     "aipartnerupflow.api.rest.server",
    #     "rest",
    #     "REST API Server",
    # ),
    # "rpc": (
    #     "aipartnerupflow.api.rpc.server",
    #     "rpc",
    #     "RPC API Server",
    # ),
}

# Default protocol
DEFAULT_PROTOCOL = "a2a"


def get_supported_protocols() -> list[str]:
    """
    Get list of supported protocol names
    
    Returns:
        List of supported protocol names
    """
    return list(PROTOCOL_DEPENDENCIES.keys())


def get_protocol_dependency_info(protocol: str) -> tuple[str, str, str]:
    """
    Get dependency information for a protocol
    
    Args:
        protocol: Protocol name
    
    Returns:
        Tuple of (module_path, extra_name, description)
    
    Raises:
        ValueError: If protocol is not supported
    """
    if protocol not in PROTOCOL_DEPENDENCIES:
        supported = ", ".join(get_supported_protocols())
        raise ValueError(
            f"Unsupported protocol '{protocol}'. "
            f"Supported protocols: {supported}"
        )
    return PROTOCOL_DEPENDENCIES[protocol]


def get_default_protocol() -> str:
    """
    Get default protocol name
    
    Returns:
        Default protocol name
    """
    return DEFAULT_PROTOCOL


def get_protocol_from_env() -> str:
    """
    Get protocol from environment variable or return default
    
    Returns:
        Protocol name (lowercased)
    """
    protocol = os.getenv("AIPARTNERUPFLOW_API_PROTOCOL", DEFAULT_PROTOCOL)
    return protocol.lower()


def check_protocol_dependency(protocol: str) -> None:
    """
    Check if dependencies for the specified protocol are installed
    
    Args:
        protocol: Protocol name
    
    Raises:
        ValueError: If protocol is not supported
        ImportError: If protocol dependencies are not installed
    """
    module_path, extra_name, description = get_protocol_dependency_info(protocol)
    
    try:
        # Try to import the protocol server module to check if dependencies are installed
        __import__(module_path)
    except ImportError as e:
        error_msg = str(e)
        # Check if it's a dependency-related error
        if extra_name in error_msg.lower() or "No module named" in error_msg:
            raise ImportError(
                f"{description} dependencies are not installed. "
                f"Please install them using: pip install aipartnerupflow[{extra_name}]"
            ) from e
        raise

# Auto-discover built-in extensions (optional, extensions register via @executor_register, @storage_register, @hook_register decorators)
# This ensures extensions are available when TaskManager is used
try:
    from aipartnerupflow.extensions.stdio import SystemInfoExecutor, CommandExecutor  # noqa: F401
    logger.debug("Discovered stdio extension")
except ImportError:
    logger.debug("Stdio extension not available (optional)")
except Exception as e:
    logger.warning(f"Failed to discover stdio extension: {e}")

try:
    from aipartnerupflow.extensions.crewai import CrewManager  # noqa: F401
    logger.debug("Discovered crewai extension")
except ImportError:
    logger.debug("CrewAI extension not available (requires [crewai] extra)")
except Exception as e:
    logger.warning(f"Failed to discover crewai extension: {e}")

# Auto-discover new executor extensions
try:
    from aipartnerupflow.extensions.http import RestExecutor  # noqa: F401
    logger.debug("Discovered http extension")
except ImportError:
    logger.debug("HTTP extension not available")
except Exception as e:
    logger.warning(f"Failed to discover http extension: {e}")

try:
    from aipartnerupflow.extensions.ssh import SshExecutor  # noqa: F401
    logger.debug("Discovered ssh extension")
except ImportError:
    logger.debug("SSH extension not available (requires [ssh] extra)")
except Exception as e:
    logger.warning(f"Failed to discover ssh extension: {e}")

try:
    from aipartnerupflow.extensions.docker import DockerExecutor  # noqa: F401
    logger.debug("Discovered docker extension")
except ImportError:
    logger.debug("Docker extension not available (requires [docker] extra)")
except Exception as e:
    logger.warning(f"Failed to discover docker extension: {e}")

try:
    from aipartnerupflow.extensions.grpc import GrpcExecutor  # noqa: F401
    logger.debug("Discovered grpc extension")
except ImportError:
    logger.debug("gRPC extension not available (requires [grpc] extra)")
except Exception as e:
    logger.warning(f"Failed to discover grpc extension: {e}")

try:
    from aipartnerupflow.extensions.websocket import WebSocketExecutor  # noqa: F401
    logger.debug("Discovered websocket extension")
except ImportError:
    logger.debug("WebSocket extension not available")
except Exception as e:
    logger.warning(f"Failed to discover websocket extension: {e}")

try:
    from aipartnerupflow.extensions.apflow import ApFlowApiExecutor  # noqa: F401
    logger.debug("Discovered apflow extension")
except ImportError:
    logger.debug("ApFlow extension not available")
except Exception as e:
    logger.warning(f"Failed to discover apflow extension: {e}")

try:
    from aipartnerupflow.extensions.mcp import McpExecutor  # noqa: F401
    logger.debug("Discovered mcp extension")
except ImportError:
    logger.debug("MCP extension not available")
except Exception as e:
    logger.warning(f"Failed to discover mcp extension: {e}")


def _load_custom_task_model():
    """Load custom TaskModel class from environment variable if specified"""
    task_model_class_path = os.getenv("AIPARTNERUPFLOW_TASK_MODEL_CLASS")
    if task_model_class_path:
        try:
            from importlib import import_module
            from aipartnerupflow import set_task_model_class
            module_path, class_name = task_model_class_path.rsplit(".", 1)
            module = import_module(module_path)
            task_model_class = getattr(module, class_name)
            set_task_model_class(task_model_class)
            logger.info(f"Loaded custom TaskModel: {task_model_class_path}")
        except Exception as e:
            logger.warning(f"Failed to load custom TaskModel from {task_model_class_path}: {e}")


def _auto_init_examples_if_needed():
    """Auto-initialize examples data if database is empty and examples are available"""
    try:
        # Check if examples module is available (requires [examples] or [all] extra)
        try:
            from aipartnerupflow.examples.init import init_examples_data_sync
            from aipartnerupflow.core.storage import get_default_session
            from aipartnerupflow.core.storage.sqlalchemy.task_repository import TaskRepository
            from aipartnerupflow.core.config import get_task_model_class
            from sqlalchemy import select, func
        except ImportError:
            # Examples module not available (not installed with [examples] or [all])
            logger.debug("Examples module not available (requires [examples] or [all] extra)")
            return
        
        # Check if database is empty
        try:
            db_session = get_default_session()
            task_repository = TaskRepository(db_session, task_model_class=get_task_model_class())
            
            # Count total tasks in database (use sync query for simplicity)
            if task_repository.is_async:
                # For async sessions, we'll use a simple approach
                import asyncio
                async def check_and_init():
                    stmt = select(func.count()).select_from(task_repository.task_model_class)
                    result = await db_session.execute(stmt)
                    count = result.scalar() or 0
                    
                    if count == 0:
                        logger.info("Database is empty, initializing examples data...")
                        from aipartnerupflow.examples.init import init_examples_data
                        await init_examples_data(force=False)
                        logger.info("Examples data initialized successfully")
                    else:
                        logger.debug(f"Database has {count} tasks, skipping examples initialization")
                
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Event loop already running, skip auto-init to avoid issues
                        logger.debug("Event loop already running, skipping auto-init")
                        return
                    else:
                        loop.run_until_complete(check_and_init())
                except RuntimeError:
                    asyncio.run(check_and_init())
            else:
                count = db_session.query(task_repository.task_model_class).count()
                
                if count == 0:
                    logger.info("Database is empty, initializing examples data...")
                    try:
                        created_count = init_examples_data_sync(force=False)
                        if created_count > 0:
                            logger.info(f"Examples data initialized successfully: {created_count} tasks created")
                        else:
                            logger.info("Examples data already exists or initialization skipped")
                    except Exception as init_error:
                        logger.error(f"Failed to initialize examples data: {init_error}", exc_info=True)
                else:
                    logger.debug(f"Database has {count} tasks, skipping examples initialization")
        except Exception as e:
            logger.warning(f"Failed to auto-initialize examples data: {e}", exc_info=True)
            # Don't fail startup if examples initialization fails
    except Exception as e:
        logger.warning(f"Examples auto-initialization check failed: {e}", exc_info=True)
        # Don't fail startup if examples are not available


def _create_a2a_server(
    jwt_secret_key: Optional[str],
    jwt_algorithm: str,
    base_url: str,
    enable_system_routes: bool,
    enable_docs: bool = True,
):
    """Create A2A Protocol Server"""
    from aipartnerupflow.api.a2a.server import create_a2a_server
    
    # Get TaskModel class from registry for logging
    from aipartnerupflow.core.config import get_task_model_class
    task_model_class = get_task_model_class()
    
    logger.info(
        f"A2A Protocol Server configuration: "
        f"JWT enabled={bool(jwt_secret_key)}, "
        f"System routes={enable_system_routes}, "
        f"Docs={enable_docs}, "
        f"TaskModel={task_model_class.__name__}"
    )
    
    a2a_server_instance = create_a2a_server(
        verify_token_secret_key=jwt_secret_key,
        verify_token_algorithm=jwt_algorithm,
        base_url=base_url,
        enable_system_routes=enable_system_routes,
        enable_docs=enable_docs,
    )
    
    return a2a_server_instance.build()


def _create_rest_server():
    """Create REST API Server (future implementation)"""
    # TODO: Implement REST API server when ready
    raise NotImplementedError(
        "REST API server is not yet implemented. "
        "Please use A2A Protocol Server (set AIPARTNERUPFLOW_API_PROTOCOL=a2a or leave unset)."
    )


def create_app_by_protocol(protocol: Optional[str] = None) -> Any:
    """
    Create application based on protocol type
    
    This is the main function for creating API applications. It should be used
    by both CLI commands and programmatic API usage.
    
    Args:
        protocol: Protocol type. If None, uses environment variable
                  AIPARTNERUPFLOW_API_PROTOCOL or defaults to "a2a"
    
    Returns:
        Starlette/FastAPI application instance
    
    Raises:
        ValueError: If protocol is not supported
        ImportError: If protocol dependencies are not installed
    """
    # Determine protocol
    if protocol is None:
        protocol = get_protocol_from_env()
    else:
        protocol = protocol.lower()
    
    # Check if protocol is supported and dependencies are installed
    check_protocol_dependency(protocol)
    
    # Get protocol dependency info for logging
    _, _, description = get_protocol_dependency_info(protocol)
    logger.info(f"Creating {description} application")
    # Common configuration
    jwt_secret_key = os.getenv("AIPARTNERUPFLOW_JWT_SECRET_KEY")
    jwt_algorithm = os.getenv("AIPARTNERUPFLOW_JWT_ALGORITHM", "HS256")
    enable_system_routes = os.getenv("AIPARTNERUPFLOW_ENABLE_SYSTEM_ROUTES", "true").lower() in ("true", "1", "yes")
    enable_docs = os.getenv("AIPARTNERUPFLOW_ENABLE_DOCS", "true").lower() in ("true", "1", "yes")
    host = os.getenv("AIPARTNERUPFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    port = int(os.getenv("AIPARTNERUPFLOW_API_PORT", os.getenv("PORT", "8000")))
    default_url = get_url_with_host_and_port(host, port)
    base_url = os.getenv("AIPARTNERUPFLOW_BASE_URL", default_url)
    
    # Create app based on protocol
    if protocol == "a2a":
        return _create_a2a_server(
            jwt_secret_key=jwt_secret_key,
            jwt_algorithm=jwt_algorithm,
            base_url=base_url,
            enable_system_routes=enable_system_routes,
            enable_docs=enable_docs,
        )
    elif protocol == "rest":
        return _create_rest_server()
    else:
        raise ValueError(
            f"Unknown protocol: {protocol}. "
            f"Supported protocols: 'a2a', 'rest' (future). "
            f"Set AIPARTNERUPFLOW_API_PROTOCOL environment variable."
        )


def main():
    """
    Main entry point for API service (can be called via entry point)
    
    Protocol selection via AIPARTNERUPFLOW_API_PROTOCOL environment variable:
    - "a2a" (default): A2A Protocol Server
    - "rest" (future): REST API server
    """
    # Log startup time
    startup_time = time.time() - start_time
    logger.info(f"Service initialization completed in {startup_time:.2f} seconds")
    
    # Load custom TaskModel if specified
    _load_custom_task_model()
    
    # Auto-initialize examples data if database is empty
    _auto_init_examples_if_needed()
    
    # Determine protocol (default to A2A for backward compatibility)
    protocol = get_protocol_from_env()
    logger.info(f"Starting API service with protocol: {protocol}")
    
    # Create app based on protocol
    app = create_app_by_protocol(protocol)
    
    # Service-level configuration
    host = os.getenv("AIPARTNERUPFLOW_API_HOST", os.getenv("API_HOST", "0.0.0.0"))
    port = int(os.getenv("AIPARTNERUPFLOW_API_PORT", os.getenv("PORT", "8000")))
    
    # Run server
    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=1,  # Single worker for async app
        loop="asyncio",  # Use asyncio event loop
        limit_concurrency=100,  # Increase concurrency limit
        limit_max_requests=1000,  # Increase max requests
        access_log=True  # Enable access logging for debugging
    )


if __name__ == "__main__":
    main()

