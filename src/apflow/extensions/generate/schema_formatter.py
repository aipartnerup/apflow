"""
Schema Formatter

Formats executor schemas into LLM-friendly documentation with examples.
Prioritizes runtime schemas over static documentation for accuracy.
"""

from typing import Dict, Any, List, Optional
from apflow.core.extensions.registry import get_registry
from apflow.logger import get_logger

logger = get_logger(__name__)


class SchemaFormatter:
    """Formats executor schemas for LLM consumption"""

    def __init__(self):
        self.registry = get_registry()

    def format_for_requirement(
        self, requirement: str, max_executors: int = 15, include_examples: bool = True
    ) -> str:
        """
        Format executor schemas relevant to the requirement

        Args:
            requirement: User's natural language requirement
            max_executors: Maximum number of executors to include
            include_examples: Whether to include usage examples

        Returns:
            Formatted string with executor schemas and examples
        """
        # Get all executors
        all_executors = self.registry.list_executors()

        # Filter by relevance
        relevant_executors = self._filter_relevant_executors(
            requirement, all_executors, max_executors
        )

        # Format each executor
        formatted_sections = []
        for executor in relevant_executors:
            formatted = self._format_single_executor(executor, include_examples=include_examples)
            if formatted:
                formatted_sections.append(formatted)

        if not formatted_sections:
            return "No relevant executors found."

        # Build final output
        output = [
            "=== Available Executors (Relevant to Your Requirement) ===",
            "",
            f"Found {len(formatted_sections)} relevant executors:",
            "",
        ]
        output.extend(formatted_sections)

        return "\n".join(output)

    def _filter_relevant_executors(
        self, requirement: str, executors: List[Any], max_count: int
    ) -> List[Any]:
        """
        Filter executors by relevance to requirement using keyword matching

        Args:
            requirement: User's requirement
            executors: List of executor extensions
            max_count: Maximum executors to return

        Returns:
            List of relevant executors sorted by relevance score
        """
        requirement_lower = requirement.lower()

        # Extract keywords from requirement
        keywords = self._extract_keywords(requirement_lower)

        # Score each executor
        scored_executors = []
        for executor in executors:
            score = self._calculate_relevance_score(executor, keywords, requirement_lower)
            scored_executors.append((score, executor))

        # Sort by score (descending) and take top N
        scored_executors.sort(key=lambda x: x[0], reverse=True)
        return [exec for _, exec in scored_executors[:max_count]]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from requirement text"""
        # Common task-related keywords
        keyword_sets = {
            "api": [
                "api",
                "rest",
                "http",
                "request",
                "fetch",
                "get",
                "post",
                "put",
                "delete",
                "endpoint",
            ],
            "command": ["command", "execute", "run", "script", "shell", "bash", "process"],
            "scrape": [
                "scrape",
                "scraping",
                "website",
                "webpage",
                "web",
                "content",
                "extract",
                "parse",
                "html",
            ],
            "database": ["database", "db", "sql", "query", "store", "save", "insert", "update"],
            "file": ["file", "read", "write", "download", "upload", "csv", "json", "xml"],
            "crewai": ["crewai", "crew", "agent", "llm", "ai", "analyze", "generate", "chat"],
            "system": ["system", "info", "cpu", "memory", "disk", "monitor"],
            "docker": ["docker", "container", "image", "containerize"],
            "ssh": ["ssh", "remote", "server", "connect"],
            "mcp": ["mcp", "protocol", "tool", "context"],
            "grpc": ["grpc", "service", "rpc"],
            "websocket": ["websocket", "ws", "realtime", "stream"],
            "batch": ["batch", "multiple", "parallel", "concurrent"],
            "generate": ["generate", "create", "build", "workflow", "task tree"],
        }

        found_keywords = []
        for category, keywords in keyword_sets.items():
            if any(kw in text for kw in keywords):
                found_keywords.append(category)

        return found_keywords

    def _calculate_relevance_score(
        self, executor: Any, keywords: List[str], requirement: str
    ) -> float:
        """
        Calculate relevance score for executor based on keywords

        Returns:
            Float score (higher = more relevant)
        """
        score = 0.0

        # Get executor metadata
        executor_id = getattr(executor, "id", "").lower()
        executor_name = getattr(executor, "name", "").lower()
        executor_desc = getattr(executor, "description", "").lower()
        executor_tags = [tag.lower() for tag in getattr(executor, "tags", [])]

        # Check keyword matches
        for keyword in keywords:
            if keyword in executor_id:
                score += 10.0
            if keyword in executor_name:
                score += 5.0
            if keyword in executor_desc:
                score += 3.0
            if keyword in executor_tags:
                score += 7.0

        # Direct requirement substring matching (bonus)
        requirement_words = set(requirement.split())
        executor_words = set(executor_id.split("_") + executor_name.split())
        common_words = requirement_words & executor_words
        score += len(common_words) * 2.0

        # Priority executors (commonly used)
        priority_executors = [
            "rest_executor",
            "command_executor",
            "scrape_executor",
            "crewai_executor",
            "system_info_executor",
            "generate_executor",
        ]
        if executor_id in priority_executors:
            score += 5.0

        return score

    def _format_single_executor(self, executor: Any, include_examples: bool = True) -> str:
        """
        Format a single executor with schema and examples

        Args:
            executor: Executor extension instance
            include_examples: Whether to include usage examples

        Returns:
            Formatted string for this executor
        """
        try:
            executor_id = getattr(executor, "id", "unknown")
            executor_name = getattr(executor, "name", "Unknown")
            executor_desc = getattr(executor, "description", "")
            executor_tags = getattr(executor, "tags", [])

            lines = [
                f"### Executor: {executor_id}",
                f"**Name**: {executor_name}",
                f"**Description**: {executor_desc[:300]}",
            ]

            if executor_tags:
                lines.append(f"**Tags**: {', '.join(executor_tags)}")

            lines.append("")

            # Get input schema
            schema = self._get_executor_schema(executor_id)
            if schema:
                lines.append("**Input Schema**:")
                lines.append("```json")
                lines.append(self._format_schema_properties(schema))
                lines.append("```")
                lines.append("")

            # Add common mistakes section
            mistakes = self._get_common_mistakes(executor_id)
            if mistakes:
                lines.append("**⚠️ Common Mistakes**:")
                for mistake in mistakes:
                    lines.append(f"  - {mistake}")
                lines.append("")

            # Add example if requested
            if include_examples:
                example = self._generate_example_for_executor(executor_id, schema)
                if example:
                    lines.append("**Example Task**:")
                    lines.append("```json")
                    lines.append(example)
                    lines.append("```")
                    lines.append("")

            lines.append("---")
            lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Error formatting executor {getattr(executor, 'id', 'unknown')}: {e}")
            return ""

    def _get_executor_schema(self, executor_id: str) -> Optional[Dict[str, Any]]:
        """Get input schema for executor from registry"""
        try:
            executor = self.registry.create_executor_instance(executor_id, inputs={})
            if executor and hasattr(executor, "get_input_schema"):
                return executor.get_input_schema()
        except Exception as e:
            logger.debug(f"Could not get schema for {executor_id}: {e}")
        return None

    def _format_schema_properties(self, schema: Dict[str, Any]) -> str:
        """Format schema properties as readable JSON"""
        if not schema or not isinstance(schema, dict):
            return "{}"

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if not properties:
            return "{}"

        formatted_props = {}
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "any")
            prop_desc = prop_info.get("description", "")
            is_required = prop_name in required

            formatted_props[prop_name] = {
                "type": prop_type,
                "description": prop_desc,
                "required": is_required,
            }

        # Convert to pretty JSON string
        import json

        return json.dumps(formatted_props, indent=2)

    def _generate_example_for_executor(
        self, executor_id: str, schema: Optional[Dict[str, Any]]
    ) -> str:
        """Generate realistic example task for executor"""
        import json

        # Predefined examples for common executors
        examples = {
            "rest_executor": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Fetch User Data",
                "schemas": {"method": "rest_executor"},
                "inputs": {
                    "url": "https://api.example.com/users/123",
                    "method": "GET",
                    "headers": {"Accept": "application/json"},
                },
            },
            "command_executor": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Run Data Processing Script",
                "schemas": {"method": "command_executor"},
                "inputs": {
                    "command": "python process_data.py --input data.json --output results.json"
                },
            },
            "aggregate_results_executor": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Extract Website Content",
                "schemas": {"method": "aggregate_results_executor"},
                "inputs": {"url": "https://example.com", "extract_main_text": True},
            },
            "system_info_executor": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Get CPU Information",
                "schemas": {"method": "system_info_executor"},
                "inputs": {"resource": "cpu"},
            },
            "crewai_executor": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Analyze Data with AI Crew",
                "schemas": {"method": "crewai_executor"},
                "inputs": {
                    "works": {
                        "agents": {
                            "analyst": {
                                "role": "Data Analyst",
                                "goal": "Analyze data comprehensively and provide insights",
                                "llm": "gpt-4",
                            }
                        },
                        "tasks": {
                            "analyze": {
                                "description": "Analyze the provided data",
                                "agent": "analyst",
                                "prompt": "Analyze the data and return results as JSON: {insights: string, patterns: [], recommendations: []}",
                                "expected_output": "JSON object with insights, patterns, and recommendations",
                            }
                        },
                    }
                },
            },
        }

        if executor_id in examples:
            return json.dumps(examples[executor_id], indent=2)

        # Generate generic example from schema
        if not schema:
            return json.dumps(
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Example Task",
                    "schemas": {"method": executor_id},
                    "inputs": {},
                },
                indent=2,
            )

        # Build inputs from schema
        properties = schema.get("properties", {})
        example_inputs = {}

        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "string")
            if prop_type == "string":
                example_inputs[prop_name] = "example_value"
            elif prop_type == "number" or prop_type == "integer":
                example_inputs[prop_name] = 123
            elif prop_type == "boolean":
                example_inputs[prop_name] = True
            elif prop_type == "object":
                example_inputs[prop_name] = {}
            elif prop_type == "array":
                example_inputs[prop_name] = []

        return json.dumps(
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": f"Example {executor_id.replace('_', ' ').title()}",
                "schemas": {"method": executor_id},
                "inputs": example_inputs,
            },
            indent=2,
        )

    def _get_common_mistakes(self, executor_id: str) -> List[str]:
        """Get common mistakes for specific executor"""
        mistakes_db = {
            "rest_executor": [
                "Forgetting to set 'method' field (GET, POST, etc.)",
                "Missing required headers for authenticated endpoints",
                "Using http:// instead of https:// for production APIs",
            ],
            "command_executor": [
                "Not providing full command with arguments",
                "Forgetting to specify working directory for relative paths",
                "Not handling command failures or checking exit codes",
            ],
            "aggregate_results_executor": [
                "Using rest_executor instead of aggregate_results_executor for web content",
                "Not setting extract_main_text=true for text extraction",
                "Forgetting to handle dynamic JavaScript-rendered content",
            ],
            "crewai_executor": [
                "Not matching task 'agent' field to defined agent roles",
                "Missing 'goal' field in agent definitions",
                "Not setting proper task dependencies for sequential work",
            ],
        }

        return mistakes_db.get(executor_id, [])


__all__ = ["SchemaFormatter"]
