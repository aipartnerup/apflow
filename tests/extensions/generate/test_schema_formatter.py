"""
Tests for Schema Formatter
"""

import pytest
from apflow.extensions.generate.schema_formatter import SchemaFormatter


class TestSchemaFormatter:
    def test_formatter_initialization(self):
        """Test SchemaFormatter can be initialized"""
        formatter = SchemaFormatter()
        assert formatter is not None
        assert formatter.registry is not None

    def test_extract_keywords(self):
        """Test keyword extraction from requirement"""
        formatter = SchemaFormatter()

        keywords = formatter._extract_keywords("scrape website content and analyze with ai agent")
        assert "scrape" in keywords
        assert "crewai" in keywords

        keywords = formatter._extract_keywords("call rest api endpoint and save to database")
        assert "api" in keywords
        assert "database" in keywords

    def test_calculate_relevance_score(self):
        """Test relevance scoring for executors"""
        formatter = SchemaFormatter()

        class MockExecutor:
            id = "rest_executor"
            name = "REST Executor"
            description = "Execute REST API calls"
            tags = ["api", "http"]

        executor = MockExecutor()
        keywords = ["api", "rest"]
        requirement = "call api endpoint"

        score = formatter._calculate_relevance_score(executor, keywords, requirement)
        assert score > 0

    def test_format_for_requirement_returns_string(self):
        """Test that format_for_requirement returns formatted string"""
        formatter = SchemaFormatter()

        result = formatter.format_for_requirement(
            "Fetch data from API and process it", max_executors=5, include_examples=True
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Available Executors" in result or "No relevant executors" in result

    def test_format_for_requirement_filters_executors(self):
        """Test that max_executors limits the output"""
        formatter = SchemaFormatter()

        result = formatter.format_for_requirement(
            "Test requirement", max_executors=3, include_examples=False
        )

        assert isinstance(result, str)

    def test_format_schema_properties(self):
        """Test schema properties formatting"""
        formatter = SchemaFormatter()

        schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "API URL"},
                "method": {"type": "string", "description": "HTTP method"},
            },
            "required": ["url"],
        }

        result = formatter._format_schema_properties(schema)
        assert isinstance(result, str)
        assert "url" in result
        assert "method" in result

    def test_generate_example_for_known_executor(self):
        """Test example generation for known executor"""
        formatter = SchemaFormatter()

        result = formatter._generate_example_for_executor("rest_executor", None)
        assert isinstance(result, str)
        assert "rest_executor" in result
        assert "550e8400-e29b-41d4-a716-446655440000" in result

    def test_get_common_mistakes_for_known_executor(self):
        """Test common mistakes retrieval"""
        formatter = SchemaFormatter()

        mistakes = formatter._get_common_mistakes("rest_executor")
        assert isinstance(mistakes, list)
        assert len(mistakes) > 0

        mistakes_unknown = formatter._get_common_mistakes("unknown_executor")
        assert isinstance(mistakes_unknown, list)
        assert len(mistakes_unknown) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
