"""
Schema migration base classes and registry

This module provides the framework for managing schema migrations.
Each migration should inherit from Migration and implement upgrade/downgrade.

Migration files are named using the pattern: {id}_{description}.py
where id is auto-extracted as the unique migration identifier.

Example:
    001_add_task_tree_fields.py
    002_add_user_fields.py
    003_rename_column.py

The id is automatically extracted from the filename and used as the unique
identifier for tracking which migrations have been applied.
"""

from abc import ABC, abstractmethod
from sqlalchemy import Engine


class Migration(ABC):
    """Base class for schema migrations

    The migration id is automatically extracted from the filename.
    Subclasses only need to implement upgrade() and downgrade() methods.
    """

    # Migration description (explain what this migration does)
    description: str = ""

    # Optional list of alias IDs for this migration (for renaming migrations)
    aliases = []

    @property
    def id(self) -> str:
        """Migration ID (extracted from filename or class name)

        Subclasses can override this if needed, but typically it's auto-extracted.
        """
        # Default: use class name in lowercase with underscores
        class_name = self.__class__.__name__
        return class_name  # Will be overridden by MigrationManager when loading from file

    @abstractmethod
    def upgrade(self, engine: Engine) -> None:
        """
        Execute migration upgrade

        Args:
            engine: SQLAlchemy engine instance

        Raises:
            Exception: If migration fails
        """
        pass

    @abstractmethod
    def downgrade(self, engine: Engine) -> None:
        """
        Execute migration downgrade (rollback)

        Args:
            engine: SQLAlchemy engine instance

        Raises:
            Exception: If downgrade fails
        """
        pass

    def __repr__(self) -> str:
        return f"<Migration(id='{self.id}')>"

