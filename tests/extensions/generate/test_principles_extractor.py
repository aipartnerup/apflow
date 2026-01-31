"""
Tests for Principles Extractor

Tests principles extraction without code examples.
"""

import pytest
from apflow.extensions.generate.principles_extractor import PrinciplesExtractor


class TestPrinciplesExtractor:
    """Test suite for PrinciplesExtractor"""

    def test_extract_core_principles(self):
        """Test core principles extraction"""
        result = PrinciplesExtractor.extract_core_principles()

        assert isinstance(result, str)
        assert len(result) > 0

        assert "Task Tree Structure" in result
        assert "parent_id" in result
        assert "dependencies" in result
        assert "UUID" in result

    def test_core_principles_no_code_examples(self):
        """Test that core principles don't include code examples"""
        result = PrinciplesExtractor.extract_core_principles()

        assert "```" not in result
        assert "def " not in result
        assert "class " not in result
        assert "import " not in result

    def test_extract_generation_guidelines(self):
        """Test generation guidelines extraction"""
        result = PrinciplesExtractor.extract_generation_guidelines()

        assert isinstance(result, str)
        assert len(result) > 0

        assert "Step 1" in result
        assert "Step 2" in result
        assert "Analyze Requirement" in result
        assert "Design Tree Structure" in result

    def test_generation_guidelines_no_code_examples(self):
        """Test that generation guidelines don't include code examples"""
        result = PrinciplesExtractor.extract_generation_guidelines()

        assert "```" not in result
        assert "def " not in result
        assert "class " not in result

    def test_extract_common_patterns(self):
        """Test common patterns extraction"""
        result = PrinciplesExtractor.extract_common_patterns()

        assert isinstance(result, str)
        assert len(result) > 0

        assert "Pattern" in result
        assert "Sequential" in result
        assert "Parallel" in result
        assert "Fan-out" in result

    def test_common_patterns_describe_structure(self):
        """Test that common patterns describe structure clearly"""
        result = PrinciplesExtractor.extract_common_patterns()

        assert "parent_id" in result
        assert "dependencies" in result
        assert "root task" in result.lower()

    def test_extract_executor_selection_rules(self):
        """Test executor selection rules extraction"""
        result = PrinciplesExtractor.extract_executor_selection_rules()

        assert isinstance(result, str)
        assert len(result) > 0

        assert "scrape_executor" in result
        assert "rest_executor" in result
        assert "command_executor" in result

    def test_executor_selection_rules_clear_guidance(self):
        """Test executor selection provides clear usage guidance"""
        result = PrinciplesExtractor.extract_executor_selection_rules()

        assert "Web Content" in result
        assert "API" in result
        assert "Command" in result

    def test_build_complete_principles_section(self):
        """Test complete principles section builder"""
        result = PrinciplesExtractor.build_complete_principles_section()

        assert isinstance(result, str)
        assert len(result) > 0

        assert "Core Framework Principles" in result
        assert "Task Tree Generation Process" in result
        assert "Common Task Tree Patterns" in result
        assert "Executor Selection Rules" in result

    def test_complete_principles_comprehensive(self):
        """Test that complete principles include all sections"""
        result = PrinciplesExtractor.build_complete_principles_section()

        core = PrinciplesExtractor.extract_core_principles()
        guidelines = PrinciplesExtractor.extract_generation_guidelines()
        patterns = PrinciplesExtractor.extract_common_patterns()
        rules = PrinciplesExtractor.extract_executor_selection_rules()

        assert core in result
        assert guidelines in result
        assert patterns in result
        assert rules in result

    def test_principles_focus_on_concepts(self):
        """Test that principles focus on concepts, not implementation"""
        result = PrinciplesExtractor.build_complete_principles_section()

        assert "MUST" in result
        assert "Rule:" in result

        assert "```python" not in result
        assert "def execute" not in result
        assert "async def" not in result

    def test_principles_include_critical_rules(self):
        """Test that principles include critical rules"""
        result = PrinciplesExtractor.build_complete_principles_section()

        assert "Exactly ONE root task" in result
        assert "parent_id" in result
        assert "dependencies" in result
        assert "UUID" in result
        assert "schemas.method" in result

    def test_principles_explain_parent_id_vs_dependencies(self):
        """Test that principles clearly explain parent_id vs dependencies"""
        result = PrinciplesExtractor.build_complete_principles_section()

        assert "parent_id" in result
        assert "dependencies" in result
        assert "TREE STRUCTURE" in result or "tree structure" in result.lower()
        assert "EXECUTION ORDER" in result or "execution order" in result.lower()

    def test_principles_include_anti_patterns(self):
        """Test that principles include anti-patterns to avoid"""
        result = PrinciplesExtractor.build_complete_principles_section()

        assert "Anti-pattern" in result or "WRONG" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
