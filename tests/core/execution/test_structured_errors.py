"""
Tests for structured error messages

Verifies that error classes support the what/why/how_to_fix/context format
and generate properly formatted messages.
"""

from apflow.core.execution.errors import (
    ApflowError,
    BusinessError,
    ValidationError,
    ConfigurationError,
    NetworkError,
    AuthenticationError,
    SystemError,
    ExecutorError,
    StorageError,
)


class TestStructuredErrors:
    """Test structured error format"""

    def test_basic_error_without_structure(self):
        """Basic error message works without structured info"""
        error = ApflowError("Simple error message")
        assert str(error) == "Simple error message"

    def test_error_with_full_structure(self):
        """Error with all structured fields"""
        error = ApflowError(
            "fallback message",
            what="Connection failed",
            why="Server is unreachable",
            how_to_fix="1. Check network\n2. Verify server status",
            context={"host": "example.com", "port": 80},
        )

        error_str = str(error)
        assert "❌ Connection failed" in error_str
        assert "💡 Reason: Server is unreachable" in error_str
        assert "✅ Solution: 1. Check network" in error_str
        assert "📝 Context:" in error_str
        assert "host: example.com" in error_str
        assert "port: 80" in error_str

    def test_error_with_partial_structure(self):
        """Error with only what and how_to_fix"""
        error = NetworkError("fallback", what="HTTP timeout", how_to_fix="Increase timeout value")

        error_str = str(error)
        assert "❌ HTTP timeout" in error_str
        assert "✅ Solution: Increase timeout value" in error_str
        assert "💡 Reason:" not in error_str  # why not provided

    def test_validation_error(self):
        """ValidationError inherits structured format"""
        error = ValidationError(
            "fallback",
            what="Invalid input",
            why="Field 'email' is required",
            how_to_fix="Provide valid email address",
            context={"field": "email", "value": None},
        )

        assert isinstance(error, BusinessError)
        assert isinstance(error, ApflowError)
        assert "❌ Invalid input" in str(error)

    def test_configuration_error(self):
        """ConfigurationError inherits structured format"""
        error = ConfigurationError(
            "fallback",
            what="Missing API key",
            why="OPENAI_API_KEY not set in environment",
            how_to_fix="Set OPENAI_API_KEY environment variable",
            context={"env_var": "OPENAI_API_KEY"},
        )

        assert isinstance(error, BusinessError)
        assert "❌ Missing API key" in str(error)
        assert "OPENAI_API_KEY" in str(error)

    def test_network_error(self):
        """NetworkError inherits structured format"""
        error = NetworkError(
            "fallback",
            what="Connection timeout",
            why="No response within 30 seconds",
            how_to_fix="1. Check network\n2. Increase timeout",
            context={"url": "https://api.example.com", "timeout": 30},
        )

        assert isinstance(error, BusinessError)
        assert "Connection timeout" in str(error)

    def test_authentication_error(self):
        """AuthenticationError inherits structured format"""
        error = AuthenticationError(
            "fallback",
            what="SSH authentication failed",
            why="Invalid key permissions",
            how_to_fix="chmod 600 ~/.ssh/id_rsa",
            context={"key_file": "~/.ssh/id_rsa"},
        )

        assert isinstance(error, BusinessError)
        assert "SSH authentication failed" in str(error)

    def test_executor_error(self):
        """ExecutorError inherits structured format"""
        error = ExecutorError(
            "fallback",
            what="Executor runtime error",
            why="Unexpected state",
            how_to_fix="Check executor logs",
        )

        assert isinstance(error, SystemError)
        assert "Executor runtime error" in str(error)

    def test_storage_error(self):
        """StorageError inherits structured format"""
        error = StorageError(
            "fallback",
            what="Database connection failed",
            why="Connection pool exhausted",
            how_to_fix="Increase pool size",
        )

        assert isinstance(error, SystemError)
        assert "Database connection failed" in str(error)

    def test_error_attributes_accessible(self):
        """Error attributes can be accessed programmatically"""
        error = NetworkError(
            "fallback",
            what="Test error",
            why="Test reason",
            how_to_fix="Test solution",
            context={"key": "value"},
        )

        assert error.what == "Test error"
        assert error.why == "Test reason"
        assert error.how_to_fix == "Test solution"
        assert error.context == {"key": "value"}

    def test_error_without_context(self):
        """Error works without context dict"""
        error = NetworkError(
            "fallback", what="Test error", why="Test reason", how_to_fix="Test solution"
        )

        assert error.context == {}
        error_str = str(error)
        assert "📝 Context:" not in error_str

    def test_backward_compatibility_simple_message(self):
        """Old-style simple messages still work"""
        error1 = ValidationError("Simple validation error")
        error2 = ConfigurationError("Missing config")
        error3 = NetworkError("Connection failed")

        assert str(error1) == "Simple validation error"
        assert str(error2) == "Missing config"
        assert str(error3) == "Connection failed"
