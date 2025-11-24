"""
Database session factory for creating database sessions
"""

from typing import Optional, Union
from pathlib import Path
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from aipartnerupflow.core.storage.sqlalchemy.models import Base
from aipartnerupflow.core.storage.dialects.registry import get_dialect_config
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Global default session instance (lazy loading)
_default_session: Optional[Union[Session, AsyncSession]] = None


def _get_default_db_path() -> str:
    """
    Get default database path.
    If examples module is available, use persistent database.
    Otherwise, use in-memory database.
    
    Returns:
        Database path string
    """
    # Check environment variable first
    env_path = os.getenv("AIPARTNERUPFLOW_DB_PATH")
    if env_path:
        return env_path
    
    # Check if examples module is available
    try:
        import aipartnerupflow.examples
        # Examples module is available, use persistent database
        # Default location: ~/.aipartnerup/data/aipartnerupflow.duckdb
        home_dir = Path.home()
        data_dir = home_dir / ".aipartnerup" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(data_dir / "aipartnerupflow.duckdb")
        logger.info(f"Examples module detected, using persistent database: {db_path}")
        return db_path
    except ImportError:
        # Examples module not available, use in-memory database
        logger.debug("Examples module not available, using in-memory database")
        return ":memory:"


def create_session(
    dialect: str = "duckdb",
    connection_string: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    async_mode: bool = True,
    **kwargs
) -> Union[Session, AsyncSession]:
    """
    Create database session
    
    Args:
        dialect: Database dialect, default "duckdb", optional "postgresql"
        connection_string: Connection string (if provided, will be used preferentially)
        path: Database file path (DuckDB only, default ":memory:")
        async_mode: Whether to use async mode
        **kwargs: Database connection parameters
            - DuckDB: path
            - PostgreSQL: user, password, host, port, database
    
    Returns:
        Database session (Session or AsyncSession)
    
    Examples:
        # Default DuckDB in-memory database
        session = create_session()
        
        # DuckDB persisted to file
        session = create_session(path="./data/agentflow.duckdb")
        
        # PostgreSQL (requires [postgres] installation)
        session = create_session(
            dialect="postgresql",
            user="postgres",
            password="password",
            host="localhost",
            port=5432,
            database="agentflow"
        )
    """
    try:
        dialect_config = get_dialect_config(dialect)
    except ValueError:
        # If PostgreSQL not installed, fallback to DuckDB
        if dialect == "postgresql":
            logger.warning(
                "PostgreSQL not available (install with [postgres] extra), "
                "falling back to DuckDB"
            )
            dialect = "duckdb"
            dialect_config = get_dialect_config(dialect)
        else:
            raise
    
    # Generate connection string
    if connection_string is None:
        if dialect == "duckdb":
            if path is None:
                path = ":memory:"
            elif path != ":memory:":
                path = str(Path(path).absolute())
            connection_string = dialect_config.get_connection_string(path=path)
        else:
            connection_string = dialect_config.get_connection_string(**kwargs)
    
    engine_kwargs = dialect_config.get_engine_kwargs()
    
    # Create engine and session
    if async_mode:
        engine = create_async_engine(connection_string, **engine_kwargs)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        session = session_maker()
    else:
        engine = create_engine(connection_string, **engine_kwargs)
        session_maker = sessionmaker(engine, class_=Session, expire_on_commit=False)
        session = session_maker()
    
    logger.info(f"Created {dialect} session: {connection_string}")
    
    # Ensure tables exist
    if engine:
        try:
            if async_mode:
                # For async, create tables using sync_engine
                if hasattr(engine, 'sync_engine'):
                    Base.metadata.create_all(engine.sync_engine)
            else:
                Base.metadata.create_all(engine)
        except Exception as e:
            logger.warning(f"Could not create tables automatically: {str(e)}")
    
    return session


def get_default_session(
    path: Optional[Union[str, Path]] = None,
    async_mode: Optional[bool] = None,
    **kwargs
) -> Union[Session, AsyncSession]:
    """
    Get default database session (singleton, DuckDB)
    
    Args:
        path: DuckDB database path. If None:
              - Uses AIPARTNERUPFLOW_DB_PATH environment variable if set
              - If examples module is available, uses persistent database at ~/.aipartnerup/data/aipartnerupflow.duckdb
              - Otherwise, uses ":memory:" (in-memory database)
        async_mode: Whether to use async mode. If None, defaults to False for DuckDB (sync mode)
                   since DuckDB doesn't support async drivers
        **kwargs: Other parameters
    
    Returns:
        Default database session
    """
    global _default_session
    
    if _default_session is None:
        # Determine database path
        if path is None:
            path = _get_default_db_path()
        
        # DuckDB doesn't support async drivers, so default to sync mode
        if async_mode is None:
            async_mode = False
        _default_session = create_session(
            dialect="duckdb",
            path=path,
            async_mode=async_mode,
            **kwargs
        )
    
    return _default_session


def set_default_session(session: Union[Session, AsyncSession]):
    """
    Set default session (mainly for testing)
    
    Args:
        session: Session to set as default
    """
    global _default_session
    _default_session = session


def reset_default_session():
    """Reset default session (mainly for testing)"""
    global _default_session
    if _default_session:
        if isinstance(_default_session, AsyncSession):
            # Note: close() is async, but this is for testing only
            pass
        else:
            _default_session.close()
    _default_session = None


# Backward compatibility aliases (deprecated)
def create_storage(*args, **kwargs):
    """Deprecated: Use create_session instead"""
    logger.warning("create_storage() is deprecated, use create_session() instead")
    return create_session(*args, **kwargs)


def get_default_storage(*args, **kwargs):
    """Deprecated: Use get_default_session instead"""
    logger.warning("get_default_storage() is deprecated, use get_default_session() instead")
    return get_default_session(*args, **kwargs)

