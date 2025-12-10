"""
Test TaskModel customization functionality
"""
import pytest
from sqlalchemy import Column, String, Integer
from aipartnerupflow import (
    set_task_model_class,
    get_task_model_class,
    task_model_register,
    clear_config,
)
from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel, Base


class TestTaskModelCustomization:
    """Test TaskModel customization features"""
    
    def setup_method(self):
        """Clear config before each test"""
        clear_config()
    
    def test_task_model_register_decorator(self):
        """Test @task_model_register() decorator"""
        @task_model_register()
        class CustomTaskModel(TaskModel):
            __tablename__ = "apflow_tasks"
            __table_args__ = {'extend_existing': True}
            project_id = Column(String(255), nullable=True)  # Removed index=True to avoid conflicts
            department = Column(String(100), nullable=True)
        
        # Verify class was registered
        retrieved_class = get_task_model_class()
        assert retrieved_class == CustomTaskModel
        assert retrieved_class.__name__ == "CustomTaskModel"
    
    def test_task_model_register_validation(self):
        """Test that task_model_register validates inheritance"""
        with pytest.raises(TypeError, match="must be a subclass of TaskModel"):
            @task_model_register()
            class NotTaskModel:
                pass
    
    def test_set_task_model_class_validation(self):
        """Test that set_task_model_class validates inheritance"""
        class NotTaskModel:
            pass
        
        with pytest.raises(TypeError, match="must be a subclass of TaskModel"):
            set_task_model_class(NotTaskModel)
    
    def test_set_task_model_class_improved_error_message(self):
        """Test that set_task_model_class provides helpful error message"""
        class NotTaskModel:
            pass
        
        try:
            set_task_model_class(NotTaskModel)
            assert False, "Should have raised TypeError"
        except TypeError as e:
            error_msg = str(e)
            assert "must be a subclass of TaskModel" in error_msg
            assert "Please ensure your custom class inherits from TaskModel" in error_msg
            assert "class MyTaskModel(TaskModel):" in error_msg
    
    def test_task_model_register_error_message(self):
        """Test that task_model_register provides helpful error message"""
        try:
            @task_model_register()
            class NotTaskModel:
                pass
            assert False, "Should have raised TypeError"
        except TypeError as e:
            error_msg = str(e)
            assert "must be a subclass of TaskModel" in error_msg
            assert "Please ensure your class inherits from TaskModel" in error_msg
    
    def test_custom_task_model_with_fields(self):
        """Test creating and using custom TaskModel with additional fields"""
        @task_model_register()
        class ProjectTaskModel(TaskModel):
            __tablename__ = "apflow_tasks"
            __table_args__ = {'extend_existing': True}
            project_id = Column(String(255), nullable=True)  # Removed index=True to avoid conflicts
            department = Column(String(100), nullable=True)
            priority_level = Column(Integer, default=2)
        
        # Verify model class
        model_class = get_task_model_class()
        assert model_class == ProjectTaskModel
        
        # Verify custom fields exist
        assert hasattr(model_class, 'project_id')
        assert hasattr(model_class, 'department')
        assert hasattr(model_class, 'priority_level')
        
        # Verify it still has base TaskModel fields
        assert hasattr(model_class, 'id')
        assert hasattr(model_class, 'name')
        assert hasattr(model_class, 'status')
        assert hasattr(model_class, 'inputs')
        assert hasattr(model_class, 'result')
    
    def test_set_task_model_class_none(self):
        """Test that set_task_model_class(None) resets to default"""
        # Set custom model
        @task_model_register()
        class CustomTaskModel(TaskModel):
            __tablename__ = "apflow_tasks"
            __table_args__ = {'extend_existing': True}
            pass
        
        assert get_task_model_class() == CustomTaskModel
        
        # Reset to None (should use default)
        set_task_model_class(None)
        assert get_task_model_class() == TaskModel
    
    def test_get_task_model_class_default(self):
        """Test that get_task_model_class returns default when not set"""
        clear_config()
        model_class = get_task_model_class()
        assert model_class == TaskModel

