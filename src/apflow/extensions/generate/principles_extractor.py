"""
Principles Extractor

Extracts framework principles and guidelines from documentation
WITHOUT including outdated code examples. Focuses on concepts only.
"""

from pathlib import Path
from apflow.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_DOCS_DIR = _PROJECT_ROOT / "docs"


class PrinciplesExtractor:
    """Extracts core principles from documentation, excluding code examples"""

    @staticmethod
    def extract_core_principles() -> str:
        """
        Extract core framework principles without code examples

        Returns:
            String containing framework concepts and principles only
        """
        principles = [
            "=== Core Framework Principles ===",
            "",
            "1. **Task Tree Structure**:",
            "   - Every task has an 'id' field (UUID format: 8-4-4-4-12)",
            "   - Exactly ONE root task (no parent_id, no dependencies)",
            "   - All other tasks MUST have parent_id to form single tree",
            "   - Task references use 'id' field (UUIDs)",
            "",
            "2. **parent_id vs dependencies** (CRITICAL):",
            "   - parent_id: TREE STRUCTURE (organizational hierarchy)",
            "   - dependencies: EXECUTION ORDER (when to run)",
            "   - They serve DIFFERENT purposes - both may be needed",
            "   - Rule: If task has dependencies, set parent_id = first dependency ID",
            "   - Example: Task B depends on Task A → B.parent_id = A.id AND B.dependencies = [{id: A.id}]",
            "",
            "3. **Task Identification**:",
            "   - Task 'name': Descriptive human-readable name (e.g., 'Fetch User Data')",
            "   - Task 'schemas.method': Executor ID (e.g., 'rest_executor', 'command_executor')",
            "   - These are DIFFERENT fields - don't confuse them",
            "",
            "4. **Executor Matching**:",
            "   - schemas.method MUST match an available executor ID exactly",
            "   - Input parameters MUST match executor's input schema",
            "   - Check schema before generating inputs",
            "",
            "5. **Tree Validation Rules**:",
            "   - Single root task (no parent_id)",
            "   - All other tasks have parent_id",
            "   - No circular dependencies",
            "   - All parent_id/dependency references must exist",
            "   - All tasks reachable from root via parent_id chain",
            "",
            "6. **Root Task Aggregator Pattern** (CRITICAL FOR MULTI-EXECUTOR WORKFLOWS):",
            "   - If task tree uses 2+ DIFFERENT executors, root MUST use 'aggregate_results_executor'",
            "   - This ensures final results are collected in the root task",
            "   - Child tasks do the actual work, root task aggregates results",
            "   - Example: Scrape + Analyze → root must be aggregate_results_executor",
            "   - Single executor workflows don't need aggregator",
            "",
        ]

        return "\n".join(principles)

    @staticmethod
    def extract_generation_guidelines() -> str:
        """
        Extract step-by-step task generation guidelines

        Returns:
            String containing generation process guidelines
        """
        guidelines = [
            "=== Task Tree Generation Process ===",
            "",
            "**Step 1: Analyze Requirement**",
            "- What is the business goal?",
            "- What steps are needed?",
            "- What data flows between steps?",
            "",
            "**Step 2: Design Tree Structure**",
            "- Identify root task (starting point)",
            "- Map business steps to executors",
            "- Determine execution order (dependencies)",
            "- Set parent_id for ALL non-root tasks:",
            "  * Sequential tasks (A → B → C): each parent_id = previous task",
            "  * Tasks with multiple deps: parent_id = first dependency",
            "  * Parallel tasks: choose one as root, others as children",
            "",
            "**Step 3: Select Executors**",
            "- Match each step to appropriate executor",
            "- Set schemas.method = executor ID",
            "- Verify executor exists in available list",
            "",
            "**Step 4: Configure Inputs**",
            "- Check executor input schema",
            "- Provide all required fields",
            "- Use realistic, complete values",
            "- For commands: full command with arguments",
            "- For APIs: complete URLs and proper HTTP methods",
            "",
            "**Step 5: Validate Structure**",
            "- Verify single root task",
            "- Verify all non-root tasks have parent_id",
            "- Verify all references valid",
            "- Verify no circular dependencies",
            "- Verify schemas.method matches available executors",
            "- Verify inputs match schemas",
            "",
        ]

        return "\n".join(guidelines)

    @staticmethod
    def extract_common_patterns() -> str:
        """
        Extract common task tree patterns

        Returns:
            String describing common patterns without code
        """
        patterns = [
            "=== Common Task Tree Patterns ===",
            "",
            "**Pattern 1: Sequential Chain** (A → B → C)",
            "- Root task: A (no parent_id)",
            "- Task B: parent_id = A.id, dependencies = [{id: A.id}]",
            "- Task C: parent_id = B.id, dependencies = [{id: B.id}]",
            "",
            "**Pattern 2: Parallel Tasks** (A || B || C)",
            "- Choose one as root (e.g., A with no parent_id)",
            "- Others: parent_id = A.id (no dependencies)",
            "- All execute in parallel after root starts",
            "",
            "**Pattern 3: Fan-out then Aggregate** (A → [B, C] → D)",
            "- Root: A (no parent_id)",
            "- B and C: parent_id = A.id, dependencies = [{id: A.id}]",
            "- D: parent_id = B.id, dependencies = [{id: B.id}, {id: C.id}]",
            "- D waits for both B and C to complete",
            "",
            "**Pattern 4: Multi-step with Dependencies**",
            "- Always set parent_id for tree structure",
            "- Use dependencies for execution order",
            "- If task depends on multiple tasks, parent_id = first dependency",
            "",
            "**Pattern 5: Multi-Executor Workflow** (CRITICAL - Most Common Real-World Scenario)",
            "- When using 2+ different executors:",
            "  1. Root task MUST use 'aggregate_results_executor'",
            "  2. Child tasks do the actual work with their specific executors",
            "  3. Root task collects and returns all child results",
            "- Example: Web analysis workflow",
            "  * Root: aggregate_results_executor (no parent_id) ← FINAL RESULTS HERE",
            "  * Child 1: scrape_executor (parent_id = root)",
            "  * Child 2: crewai_executor (parent_id = root, depends on Child 1)",
            "- This ensures final results are in the root task, not scattered in children",
            "",
            "**Anti-pattern: Multiple Roots**",
            "- WRONG: Two tasks with no parent_id",
            "- FIX: Choose one as root, set others' parent_id = root.id",
            "",
            "**Anti-pattern: Non-Aggregator Root with Multiple Executors**",
            "- WRONG: Root uses scrape_executor but tree also has crewai_executor",
            "- FIX: Change root to aggregate_results_executor",
            "- WHY: Root must collect results from all different executors",
            "",
        ]

        return "\n".join(patterns)

    @staticmethod
    def extract_executor_selection_rules() -> str:
        """
        Extract rules for choosing correct executors

        Returns:
            String with executor selection guidance
        """
        rules = [
            "=== Executor Selection Rules ===",
            "",
            "**Web Content Extraction** (CRITICAL):",
            "- Use 'scrape_executor' for extracting website content, metadata, main text",
            "- Use 'rest_executor' ONLY for raw HTTP APIs (JSON endpoints)",
            "- Use 'command_executor' ONLY for shell commands unrelated to web",
            "",
            "**API Calls**:",
            "- Use 'rest_executor' for HTTP/REST APIs",
            "- Supports GET, POST, PUT, DELETE, PATCH",
            "- Handles authentication, headers, request bodies",
            "",
            "**Command Execution**:",
            "- Use 'command_executor' for shell commands",
            "- Provide full command with all arguments",
            "- Specify working directory if needed",
            "",
            "**System Information**:",
            "- Use 'system_info_executor' for CPU, memory, disk info",
            "- Lightweight alternative to full command execution",
            "",
            "**AI/LLM Tasks**:",
            "- Use 'crewai_executor' for AI agent crews (multi-step LLM workflows)",
            "  Required: inputs.works = {\"agents\": {...}, \"tasks\": {...}}",
            "  Each task prompt defines output format (JSON, text, etc.)",
            "  Example: prompt: 'Return analysis as JSON: {insights: string, score: number}'",
            "- Use 'llm_executor' for direct LLM calls",
            "",
            "**Task Generation**:",
            "- Use 'generate_executor' to generate task trees from requirements",
            "- Recursive workflow generation",
            "",
            "**Result Aggregation** (REQUIRED for multi-executor workflows):",
            "- Use 'aggregate_results_executor' as root task when:",
            "  * Workflow uses 2+ different executor types",
            "  * Need to collect results from multiple child tasks",
            "  * Want final results in root task (recommended pattern)",
            "  * CRITICAL: Root aggregator MUST have 'dependencies' field listing all direct child task IDs",
            "  * Example: {'dependencies': [{'id': 'child1', 'required': true}, {'id': 'child2', 'required': true}]}",
            "- Inputs: Empty (aggregator uses dependencies to collect child results)",
            "- Output: Combined results from all dependency tasks",
            "",
        ]

        return "\n".join(rules)

    @staticmethod
    def build_complete_principles_section() -> str:
        """
        Build complete principles section for LLM prompt

        Returns:
            Complete formatted principles string
        """
        sections = [
            PrinciplesExtractor.extract_core_principles(),
            "",
            PrinciplesExtractor.extract_generation_guidelines(),
            "",
            PrinciplesExtractor.extract_common_patterns(),
            "",
            PrinciplesExtractor.extract_executor_selection_rules(),
        ]

        return "\n".join(sections)


__all__ = ["PrinciplesExtractor"]
