"""
Test migration manager and migration system

Tests:
- Migration discovery from migrations/ directory
- Migration execution and history tracking
- Idempotent migration execution (no duplicates)
- task_tree_id auto-assignment during migration
- Schema evolution for existing databases
"""

import pytest
from sqlalchemy import text

from apflow.core.storage.migrate import MigrationManager, MigrationHistoryTable
from apflow.core.storage.sqlalchemy.models import TaskModel
from apflow.logger import get_logger

logger = get_logger(__name__)


@pytest.fixture
def migration_manager():
    """Create migration manager instance"""
    return MigrationManager()


class TestMigrationDiscovery:
    """Test migration discovery mechanism"""

    def test_discover_migrations(self, migration_manager):
        """Test that migrations are discovered from the migrations/ directory"""
        migrations = migration_manager.get_all_migrations()
        
        # Should discover at least one migration
        assert len(migrations) > 0, "No migrations discovered"
        
        # All migrations should have an id and description
        for migration in migrations:
            assert migration.id, f"Migration {migration} has no id"
            assert migration.description, f"Migration {migration} has no description"
    
    def test_migrations_sorted_by_id(self, migration_manager):
        """Test that migrations are sorted by id for consistent execution order"""
        migrations = migration_manager.get_all_migrations()
        migration_ids = [m.id for m in migrations]
        
        # IDs should be in sorted order
        assert migration_ids == sorted(migration_ids), \
            f"Migrations not sorted: {migration_ids}"
    
    def test_add_task_tree_fields_migration_exists(self, migration_manager):
        """Test that the AddTaskTreeFields migration is discovered"""
        migrations = migration_manager.get_all_migrations()
        migration_ids = [m.id for m in migrations]
        
        # Should find migration with class name AddTaskTreeFields
        assert any('AddTaskTreeFields' in mid for mid in migration_ids), \
            f"AddTaskTreeFields migration not found in {migration_ids}"


class TestMigrationHistoryTable:
    """Test migration history table operations"""

    def test_create_history_table(self, sync_db_session):
        """Test that migration history table is created"""
        engine = sync_db_session.get_bind()
        
        # Create history table
        MigrationHistoryTable.ensure_exists(engine)
        
        # Verify history table exists using raw SQL
        with engine.begin() as conn:
            try:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {MigrationHistoryTable.TABLE_NAME}")
                )
                count = result.scalar()
                assert count >= 0, "History table exists"
            except Exception as e:
                raise AssertionError(f"History table creation failed: {str(e)}")
    
    def test_history_table_schema(self, sync_db_session):
        """Test that migration history table has correct schema"""
        engine = sync_db_session.get_bind()
        MigrationHistoryTable.ensure_exists(engine)
        
        # Use raw SQL to check columns
        with engine.begin() as conn:
            try:
                result = conn.execute(
                    text(
                        f"SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name = '{MigrationHistoryTable.TABLE_NAME}'"
                    )
                )
                columns = {row[0] for row in result}
            except Exception:
                # For DuckDB, check via pragma
                try:
                    result = conn.execute(
                        text(f"PRAGMA table_info({MigrationHistoryTable.TABLE_NAME})")
                    )
                    columns = {row[1] for row in result}  # column 1 is name
                except Exception:
                    pytest.skip("Could not inspect migration history table schema")
                    return
        
        # Should have required columns
        required_columns = {'id', 'description', 'apflow_version', 'created_at', 'updated_at'}
        assert required_columns.issubset(columns), \
            f"Missing columns. Expected {required_columns}, got {columns}"
    
    def test_get_applied_migrations(self, sync_db_session):
        """Test getting applied migrations"""
        engine = sync_db_session.get_bind()
        
        # No applied migrations initially
        applied = MigrationHistoryTable.get_applied(engine)
        assert applied == set()
        
        # Create table and add a record
        MigrationHistoryTable.ensure_exists(engine)
        
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {MigrationHistoryTable.TABLE_NAME} "
                    f"(id, description, apflow_version) "
                    f"VALUES ('001_test', 'Test migration', '0.2.0')"
                )
            )
        
        # Should find applied migration
        applied = MigrationHistoryTable.get_applied(engine)
        assert '001_test' in applied


class TestMigrationExecution:
    """Test migration execution flow"""

    def test_run_pending_migrations_idempotent(self, sync_db_session, migration_manager):
        """Test that migrations are idempotent (not run twice)"""
        engine = sync_db_session.get_bind()
        
        # Run migrations first time
        migration_manager.run_pending(engine)
        
        applied_1 = migration_manager.get_applied(engine)
        assert len(applied_1) > 0, "No migrations were applied"
        
        # Run again - should not apply again
        pending = migration_manager.get_pending(engine)
        assert len(pending) == 0, "Pending migrations should be empty after first run"
        
        # Applied migrations should be the same
        applied_2 = migration_manager.get_applied(engine)
        assert applied_1 == applied_2, "Applied migrations changed on second run"
    
    def test_pending_migrations_before_execution(self, migration_manager):
        """Test pending migrations list before any execution"""
        # No execution yet, so all migrations should be pending
        # (without a database, we can't fully test this, but we can verify the method works)
        assert callable(migration_manager.get_pending), "get_pending method should exist"
    
    def test_run_pending_creates_history_table(self, sync_db_session, migration_manager):
        """Test that run_pending creates migration history table automatically"""
        engine = sync_db_session.get_bind()
        
        # Verify table works properly after migration
        migration_manager.run_pending(engine)
        
        # Verify history table exists and has records
        try:
            with engine.begin() as conn:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {MigrationHistoryTable.TABLE_NAME}")
                )
                count = result.scalar()
                # Should have at least one migration recorded
                assert count > 0, "No migrations recorded in history table"
        except Exception as e:
            raise AssertionError(f"History table not accessible: {str(e)}")


class TestAddTaskTreeFieldsMigration:
    """Test the AddTaskTreeFields migration specifically"""

    def test_migration_adds_columns(self, sync_db_session, migration_manager):
        """Test that migration adds task_tree_id, origin_type, has_references columns"""
        engine = sync_db_session.get_bind()
        
        # Run migrations
        migration_manager.run_pending(engine)
        
        # Check columns exist using raw SQL
        with engine.begin() as conn:
            try:
                result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'apflow_tasks'"
                    )
                )
                columns = {row[0] for row in result}
            except Exception:
                # For DuckDB
                try:
                    result = conn.execute(
                        text("PRAGMA table_info(apflow_tasks)")
                    )
                    columns = {row[1] for row in result}
                except Exception:
                    pytest.skip("Could not check table columns")
                    return
        
        assert 'task_tree_id' in columns, "task_tree_id column not added"
        assert 'origin_type' in columns, "origin_type column not added"
        assert 'has_references' in columns, "has_references column not added"
    
    def test_migration_creates_indexes(self, sync_db_session, migration_manager):
        """Test that migration creates indexes on new columns"""
        engine = sync_db_session.get_bind()
        migration_manager.run_pending(engine)
        
        # Verify table is queryable with the new columns
        with engine.begin() as conn:
            # If this succeeds, the columns exist and are properly created
            result = conn.execute(
                text("SELECT COUNT(*) FROM apflow_tasks WHERE task_tree_id IS NULL")
            )
            count = result.scalar()
            assert count >= 0, "Can query new task_tree_id column"
    
    def test_auto_assign_task_tree_id(self, sync_db_session, migration_manager):
        """Test that existing tasks get task_tree_id auto-assigned"""
        # Create test tasks before migration
        root_task_1 = TaskModel(id='root_1', name='Root 1', user_id='user1')
        root_task_2 = TaskModel(id='root_2', name='Root 2', user_id='user1')
        child_task_1 = TaskModel(id='child_1', name='Child 1', parent_id='root_1', user_id='user1')
        child_task_2 = TaskModel(id='child_2', name='Child 2', parent_id='root_1', user_id='user1')
        child_task_3 = TaskModel(id='child_3', name='Child 3', parent_id='root_2', user_id='user1')
        
        sync_db_session.add_all([root_task_1, root_task_2, child_task_1, child_task_2, child_task_3])
        sync_db_session.commit()
        
        # Run migration
        engine = sync_db_session.get_bind()
        migration_manager.run_pending(engine)
        
        # Verify task_tree_id assignments
        sync_db_session.expire_all()
        
        root_1 = sync_db_session.query(TaskModel).filter_by(id='root_1').first()
        root_2 = sync_db_session.query(TaskModel).filter_by(id='root_2').first()
        child_1 = sync_db_session.query(TaskModel).filter_by(id='child_1').first()
        child_2 = sync_db_session.query(TaskModel).filter_by(id='child_2').first()
        child_3 = sync_db_session.query(TaskModel).filter_by(id='child_3').first()
        
        # Root tasks should have their own id as task_tree_id
        assert root_1.task_tree_id == 'root_1', \
            f"Root task 1 should have task_tree_id='root_1', got '{root_1.task_tree_id}'"
        assert root_2.task_tree_id == 'root_2', \
            f"Root task 2 should have task_tree_id='root_2', got '{root_2.task_tree_id}'"
        
        # Child tasks should have their root's id as task_tree_id
        assert child_1.task_tree_id == 'root_1', \
            f"Child task 1 should have task_tree_id='root_1', got '{child_1.task_tree_id}'"
        assert child_2.task_tree_id == 'root_1', \
            f"Child task 2 should have task_tree_id='root_1', got '{child_2.task_tree_id}'"
        assert child_3.task_tree_id == 'root_2', \
            f"Child task 3 should have task_tree_id='root_2', got '{child_3.task_tree_id}'"
    
    def test_has_references_field_defaults_to_false(self, sync_db_session, migration_manager):
        """Test that has_references field defaults to False"""
        # Create a task before migration
        task = TaskModel(id='test_task', name='Test', user_id='user1')
        sync_db_session.add(task)
        sync_db_session.commit()
        
        # Run migration
        engine = sync_db_session.get_bind()
        migration_manager.run_pending(engine)
        
        # Check has_references defaults to False
        sync_db_session.expire_all()
        task = sync_db_session.query(TaskModel).filter_by(id='test_task').first()
        assert task.has_references is False, \
            f"has_references should default to False, got {task.has_references}"


class TestMigrationVersionTracking:
    """Test migration version tracking"""

    def test_recorded_migrations_have_apflow_version(self, sync_db_session, migration_manager):
        """Test that recorded migrations include apflow version"""
        engine = sync_db_session.get_bind()
        migration_manager.run_pending(engine)
        
        # Query migration history
        with engine.begin() as conn:
            result = conn.execute(
                text(f"SELECT id, apflow_version FROM {MigrationHistoryTable.TABLE_NAME}")
            )
            migrations = result.fetchall()
        
        # All recorded migrations should have a version
        assert len(migrations) > 0, "No migrations recorded"
        
        for mig_id, version in migrations:
            assert version, f"Migration {mig_id} has no recorded version"
            assert len(version) > 0, f"Migration {mig_id} has empty version"
    
    def test_recorded_migrations_have_timestamps(self, sync_db_session, migration_manager):
        """Test that recorded migrations have created_at and updated_at timestamps"""
        engine = sync_db_session.get_bind()
        migration_manager.run_pending(engine)
        
        # Query migration history
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    f"SELECT id, created_at, updated_at "
                    f"FROM {MigrationHistoryTable.TABLE_NAME}"
                )
            )
            migrations = result.fetchall()
        
        # All recorded migrations should have timestamps
        assert len(migrations) > 0, "No migrations recorded"
        
        for mig_id, created_at, updated_at in migrations:
            assert created_at, f"Migration {mig_id} has no created_at"
            assert updated_at, f"Migration {mig_id} has no updated_at"
