"""
Generate Executor

This executor generates valid task tree JSON arrays from natural language
requirements using LLM. The generated tasks are compatible with
TaskCreator.create_task_tree_from_array().
"""

import json
import re
import uuid
from typing import Dict, Any, List, Optional, Set
from apflow.core.base import BaseTask
from apflow.core.extensions.decorators import executor_register
from apflow.logger import get_logger
from apflow.extensions.generate.llm_client import create_llm_client
from apflow.extensions.generate.schema_formatter import SchemaFormatter
from apflow.extensions.generate.principles_extractor import PrinciplesExtractor

logger = get_logger(__name__)


@executor_register()
class GenerateExecutor(BaseTask):
    """
    Executor for generating task trees from natural language requirements

    This executor uses LLM to generate valid task tree JSON arrays that can be
    used with TaskCreator.create_task_tree_from_array().

    Example usage:
        task = await task_manager.task_repository.create_task(
            name="generate_executor",
            user_id="user123",
            inputs={
                "requirement": "Fetch data from API, process it, and save to database",
                "user_id": "user123"
            }
        )
    """

    id = "generate_executor"
    name = "Generate Executor"
    description = "Generate task tree JSON arrays from natural language requirements using LLM"
    tags = ["generation", "llm", "task-tree", "automation"]
    examples = [
        "Generate task tree from requirement",
        "Create workflow from natural language",
        "Auto-generate task structure",
    ]

    cancelable: bool = False

    @property
    def type(self) -> str:
        """Extension type identifier"""
        return "generate"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate task tree JSON array from requirement

        Args:
            inputs: Dictionary containing:
                - requirement: Natural language requirement (required)
                - user_id: User ID for generated tasks (optional)
                - generation_mode: "single_shot" or "multi_phase" (optional, default "single_shot")
                - llm_provider: LLM provider ("openai" or "anthropic", optional)
                - model: Model name (optional)
                - temperature: LLM temperature (optional, default 0.7)
                - max_tokens: Maximum tokens (optional, default 4000)

        Returns:
            Dictionary with:
                - status: "completed" or "failed"
                - tasks: List of task dictionaries (if successful)
                - error: Error message (if failed)
        """
        try:
            requirement = inputs.get("requirement")
            if not requirement:
                return {
                    "status": "failed",
                    "error": "requirement is required in inputs",
                    "tasks": [],
                }

            user_id = self.user_id or inputs.get("user_id")
            generation_mode = inputs.get("generation_mode", "single_shot")
            llm_provider = inputs.get("llm_provider")
            model = inputs.get("model")
            temperature = inputs.get("temperature", 0.7)
            max_tokens = inputs.get("max_tokens", 4000)

            from apflow.core.utils.llm_key_context import get_llm_key

            api_key = inputs.get("api_key")
            if not api_key:
                api_key = get_llm_key(user_id=user_id, provider=llm_provider, context="auto")

            if generation_mode == "multi_phase":
                logger.info(f"Using multi-phase generation for: {requirement[:100]}...")
                try:
                    # Lazy import to avoid requiring crewai when not using multi-phase mode
                    from apflow.extensions.generate.multi_phase_crew import (
                        MultiPhaseGenerationCrew,
                    )

                    crew = MultiPhaseGenerationCrew(
                        llm_provider=llm_provider, model=model, api_key=api_key
                    )
                    result = await crew.generate(requirement, user_id)

                    if not result.get("success"):
                        return {
                            "status": "failed",
                            "error": result.get("error", "Multi-phase generation failed"),
                            "tasks": [],
                        }

                    tasks = result.get("tasks", [])
                except Exception as e:
                    logger.error(f"Multi-phase generation error: {e}", exc_info=True)
                    return {
                        "status": "failed",
                        "error": f"Multi-phase generation failed: {str(e)}",
                        "tasks": [],
                    }
            else:
                logger.info(f"Using single-shot generation for: {requirement[:100]}...")
                try:
                    llm_client = create_llm_client(
                        provider=llm_provider,
                        api_key=api_key,
                        model=model,
                    )
                except Exception as e:
                    logger.error(f"Failed to create LLM client: {e}")
                    return {
                        "status": "failed",
                        "error": f"Failed to create LLM client: {str(e)}",
                        "tasks": [],
                    }

                prompt = self._build_llm_prompt(requirement, user_id)

                try:
                    response = await llm_client.generate(
                        prompt, temperature=temperature, max_tokens=max_tokens
                    )
                except Exception as e:
                    logger.error(f"LLM generation error: {e}")
                    return {
                        "status": "failed",
                        "error": f"LLM generation failed: {str(e)}",
                        "tasks": [],
                    }

                try:
                    tasks = self._parse_llm_response(response)
                except Exception as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    return {
                        "status": "failed",
                        "error": f"Failed to parse LLM response: {str(e)}",
                        "tasks": [],
                    }

            tasks = self._post_process_tasks(tasks, user_id=user_id)

            validation_result = self._validate_tasks_array(tasks)
            if not validation_result["valid"]:
                logger.warning(f"Validation failed: {validation_result['error']}")

                fixed_tasks = self._attempt_auto_fix(tasks, validation_result["error"])
                if fixed_tasks:
                    tasks = fixed_tasks
                    revalidation = self._validate_tasks_array(tasks)
                    if revalidation["valid"]:
                        logger.info("Auto-fix succeeded, tasks now valid")
                    else:
                        return {
                            "status": "failed",
                            "error": f"Validation failed after auto-fix: {revalidation['error']}",
                            "tasks": tasks,
                        }
                else:
                    return {
                        "status": "failed",
                        "error": f"Validation failed: {validation_result['error']}",
                        "tasks": tasks,
                    }

            logger.info(f"Successfully generated {len(tasks)} tasks (mode: {generation_mode})")
            return {
                "status": "completed",
                "tasks": tasks,
                "count": len(tasks),
                "generation_mode": generation_mode,
            }

        except Exception as e:
            logger.error(f"Unexpected error in generate_executor: {e}", exc_info=True)
            return {"status": "failed", "error": f"Unexpected error: {str(e)}", "tasks": []}

    def _build_llm_prompt(self, requirement: str, user_id: Optional[str] = None) -> str:
        """
        Build intelligent LLM prompt with context tailored to the requirement

        Args:
            requirement: User's natural language requirement
            user_id: Optional user ID

        Returns:
            Complete prompt string optimized for the specific requirement
        """
        schema_formatter = SchemaFormatter()
        # Exclude generate_executor itself to prevent recursion
        # Current system does NOT support recursive task generation
        executors_info = schema_formatter.format_for_requirement(
            requirement, max_executors=15, include_examples=True, exclude_executors=["generate_executor"]
        )

        principles = PrinciplesExtractor.build_complete_principles_section()

        prompt_parts = [
            "You are an expert task tree generator for the apflow framework.",
            "Your goal is to understand the business requirement and generate a valid, practical task tree JSON array.",
            "",
            "🚫 CRITICAL LIMITATION: RECURSIVE GENERATION NOT SUPPORTED",
            "- generate_executor is NOT available in the executor list below",
            "- The system does NOT support recursive task generation (generate → execute → generate)",
            "- You MUST use concrete executors only (scrape_executor, rest_executor, system_info_executor, etc.)",
            "- Do NOT try to decompose simple tasks - use the appropriate executor directly",
            "",
            "=== PRIORITY 1: Available Executors (USE THESE SCHEMAS) ===",
            executors_info,
            "",
            "=== PRIORITY 2: Framework Principles (FOLLOW THESE RULES) ===",
            principles,
            "",
            "=== PRIORITY 3: Business Requirement (YOUR TASK) ===",
            requirement,
            "",
            "=== Output Requirements ===",
            "Generate a valid JSON array of task objects that:",
            "1. Fulfills the business requirement",
            "2. Uses ONLY executors listed in PRIORITY 1 section (CRITICAL: check executor names carefully)",
            "3. Follows ALL rules from PRIORITY 2 section",
            "4. Has complete, realistic input parameters matching executor schemas",
            "",
            "=== Executor Selection Guidelines (CRITICAL - READ CAREFULLY) ===",
            "",
            "⚠️ FUNDAMENTAL RULE: Use DIRECT executors for simple, single-purpose tasks",
            "DO NOT decompose simple tasks that can be done by one executor!",
            "",
            "🎯 DIRECT EXECUTION (Use these for simple tasks):",
            "",
            "□ For scraping/extracting website content → ALWAYS use 'scrape_executor' DIRECTLY",
            "  ✓ RIGHT: {\"method\": \"scrape_executor\", \"inputs\": {\"url\": \"https://...\"}}",
            "  ❌ WRONG: {\"method\": \"generate_executor\", \"inputs\": {\"requirement\": \"scrape https://...\"}}",
            "  ❌ WRONG: {\"method\": \"command_executor\", \"inputs\": {\"command\": \"curl https://...\"}}",
            "  Why: scrape_executor is purpose-built, safe, and always enabled",
            "",
            "□ For REST API calls → ALWAYS use 'rest_executor' DIRECTLY",
            "  ✓ RIGHT: {\"method\": \"rest_executor\", \"inputs\": {\"url\": \"https://api...\", \"method\": \"GET\"}}",
            "  ❌ WRONG: {\"method\": \"generate_executor\", \"inputs\": {\"requirement\": \"fetch from API...\"}}",
            "  Example: GET/POST/PUT/DELETE requests, webhook calls, API interactions",
            "",
            "□ For system monitoring → ALWAYS use 'system_info_executor' DIRECTLY",
            "  ✓ RIGHT: {\"method\": \"system_info_executor\", \"inputs\": {\"resource\": \"cpu\"}}",
            "  ❌ WRONG: {\"method\": \"generate_executor\", \"inputs\": {\"requirement\": \"check CPU...\"}}",
            "  Example: CPU, memory, disk, network usage",
            "",
            "□ For AI analysis with multiple agents → use 'crewai_executor' DIRECTLY",
            "  ✓ RIGHT: Define agents and tasks in crewai_executor inputs",
            "  ❌ WRONG: {\"method\": \"generate_executor\", \"inputs\": {\"requirement\": \"analyze with AI...\"}}",
            "  Example: Content analysis, report generation, research tasks",
            "",
            "🚫 RECURSIVE GENERATION: NOT SUPPORTED",
            "  ❌ generate_executor is NOT AVAILABLE (excluded to prevent recursion)",
            "  ❌ DO NOT try to use generate_executor in generated tasks",
            "  ✓ Use concrete executors directly: scrape_executor, rest_executor, crewai_executor, etc.",
            "  Why: Current system only supports single-pass generation (generate → execute)",
            "  Future: Recursive generation with evaluation/termination may be supported later",
            "",
            "🚫 WHEN TO NEVER USE command_executor:",
            "🚫 WHEN TO NEVER USE command_executor:",
            "  ❌ Web scraping → use scrape_executor instead",
            "  ❌ API calls → use rest_executor instead",
            "  ⚠️ command_executor is DISABLED BY DEFAULT (requires APFLOW_STDIO_ALLOW_COMMAND=1)",
            "  ⚠️ SECURITY RISK: Only use if user explicitly requests shell command execution",
            "",
            "□ For aggregating results from 2+ different executor types → root must be 'aggregate_results_executor'",
            "  Example: Combining results from scrape_executor and crewai_executor",
            "  Note: Multiple tasks of SAME executor can share parent without aggregator",
            "",
            "=== Validation Checklist (VERIFY BEFORE RETURNING) ===",
            "□ Single root task (no parent_id)",
            "□ All other tasks have parent_id",
            "□ All schemas.method values match available executors EXACTLY",
            "□ All inputs match executor schemas (check required fields)",
            "□ All UUIDs valid format (8-4-4-4-12)",
            "□ No circular dependencies",
            "□ All references valid",
            "",
            "=== IMPORTANT: CrewAI Executor Special Format ===",
            "When using 'crewai_executor', the inputs MUST contain 'works' field:",
            "  inputs: {",
            "    works: {",
            "      agents: {",
            "        agent_name: {",
            "          role: string,       // REQUIRED: Agent's role (e.g., 'Senior Data Analyst')",
            "          goal: string,       // REQUIRED: Agent's goal (e.g., 'Analyze data and provide insights')",
            "          backstory: string,  // REQUIRED: Agent's background (e.g., 'Expert with 10 years experience')",
            "          llm: string,        // REQUIRED: Model name (gpt-4, claude-3-opus, gpt-3.5-turbo, etc.)",
            "          tools: [strings]    // Optional tool names",
            "        }",
            "      },",
            "      tasks: {",
            "        task_name: {",
            "          description: string,     // What the task does",
            "          agent: string,          // Agent name (must be in agents)",
            "          prompt: string,         // Detailed prompt defining output format",
            "          expected_output: string // Description of expected format",
            "        }",
            "      }",
            "    }",
            "  }",
            "CRITICAL: All agents MUST have role, goal, backstory, and llm fields - all are required!",
            "",
            "=== CRITICAL: How to Reference Dependency Data in CrewAI Tasks ===",
            "⚠️ IMPORTANT: CrewAI template variable substitution has limitations with dependency data.",
            "",
            "When a crewai_executor task depends on another task, the dependency's result is automatically",
            "merged into the task's inputs by the framework. However, dependency results are stored using",
            "the DEPENDENCY TASK ID as the key, not semantic names like 'content' or 'data'.",
            "",
            "Framework Behavior:",
            "  1. Execute dependency task (e.g., 'scrape-website') → gets result",
            "  2. Store result in inputs using task ID: {'scrape-website-id-uuid': result}",
            "  3. Pass to crewai_executor → crew.kickoff(inputs={'scrape-website-id-uuid': result, ...})",
            "  4. CrewAI can only substitute variables that exist in inputs dictionary",
            "",
            "❌ WRONG - Using Template Variables for Dependencies:",
            "  DO NOT use template variables like {content}, {data}, {website_content} for dependency data!",
            "  Example of BROKEN task:",
            "    'description': 'Analyze this website content: {content}'",
            "    // This will FAIL because 'content' key doesn't exist - only the task ID key exists",
            "",
            "✓ CORRECT - Include Data Directly in Description:",
            "  DON'T use template variables for dependency data. Write generic descriptions:",
            "  Example:",
            "    Task 'analyze-content' depends on 'scrape-website':",
            "    {",
            "      'id': 'analyze-content',",
            "      'dependencies': [{'id': 'scrape-website', 'required': true}],",
            "      'schemas': {'method': 'crewai_executor'},",
            "      'inputs': {",
            "        'works': {",
            "          'agents': {",
            "            'analyst': {",
            "              'role': 'Content Analyst',",
            "              'goal': 'Analyze website content and provide insights',",
            "              'backstory': 'Expert in web content analysis with 10 years experience',",
            "              'llm': 'gpt-4'",
            "            }",
            "          },",
            "          'tasks': {",
            "            'analyze': {",
            "              'description': 'Analyze the scraped website content from the previous task',",
            "              'agent': 'analyst',",
            "              'prompt': 'You will receive website content from a previous task. Analyze it and return JSON with insights and recommendations: {\"insights\": [...], \"recommendations\": [...]}',",
            "              'expected_output': 'JSON with insights and recommendations'",
            "            }",
            "          }",
            "        }",
            "      }",
            "    }",
            "",
            "  Note: The dependency data is automatically available to the agent's context, but you cannot",
            "  reference it with template variables in the description. Write natural task descriptions",
            "  that explain what needs to be done WITHOUT referencing specific variable names.",
            "",
            "✓ ALTERNATIVE - Provide Static Data:",
            "  Template variables ONLY work for data you explicitly include in the 'inputs' field:",
            "    'inputs': {",
            "      'target_url': 'https://example.com',  // ← Can use {target_url} in description",
            "      'works': { ... }",
            "    }",
            "    Then you can use: 'description': 'Scrape content from {target_url}'",
            "",
            "The prompt field should specify output format: 'Return as JSON: {...}' or 'Return as text: ...'",
            "The crew's result is determined by the task prompts - not by executor schema.",
            "",
            "=== Example 1: Simple System Monitoring (Single Executor) ===",
            json.dumps(
                [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Check CPU Usage",
                        "schemas": {"method": "system_info_executor"},
                        "inputs": {"resource": "cpu"},
                    }
                ],
                indent=2,
            ),
            "",
            "=== Example 2: Parallel Data Collection with Aggregation ===",
            json.dumps(
                [
                    {
                        "id": "root-aggregate",
                        "name": "System Health Report",
                        "schemas": {"method": "aggregate_results_executor"},
                        "inputs": {},
                        "dependencies": [
                            {"id": "cpu-check", "required": True},
                            {"id": "memory-check", "required": True},
                            {"id": "disk-check", "required": True}
                        ],
                    },
                    {
                        "id": "cpu-check",
                        "name": "Check CPU",
                        "parent_id": "root-aggregate",
                        "schemas": {"method": "system_info_executor"},
                        "inputs": {"resource": "cpu"},
                    },
                    {
                        "id": "memory-check",
                        "name": "Check Memory",
                        "parent_id": "root-aggregate",
                        "schemas": {"method": "system_info_executor"},
                        "inputs": {"resource": "memory"},
                    },
                    {
                        "id": "disk-check",
                        "name": "Check Disk",
                        "parent_id": "root-aggregate",
                        "schemas": {"method": "system_info_executor"},
                        "inputs": {"resource": "disk"},
                    },
                ],
                indent=2,
            ),
            "",
            "=== Example 3: Sequential API Workflow (REST → Process → Notify) ===",
            json.dumps(
                [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Fetch Weather Data",
                        "schemas": {"method": "rest_executor"},
                        "inputs": {
                            "url": "https://api.weather.com/v1/current",
                            "method": "GET",
                            "params": {"location": "Beijing"}
                        },
                    },
                    {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "name": "Transform Data",
                        "schemas": {"method": "rest_executor"},
                        "parent_id": "550e8400-e29b-41d4-a716-446655440000",
                        "dependencies": [
                            {"id": "550e8400-e29b-41d4-a716-446655440000", "required": True}
                        ],
                        "inputs": {
                            "url": "https://api.internal.com/transform",
                            "method": "POST",
                            "headers": {"Content-Type": "application/json"}
                        },
                    },
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440002",
                        "name": "Send Notification",
                        "schemas": {"method": "rest_executor"},
                        "parent_id": "660e8400-e29b-41d4-a716-446655440001",
                        "dependencies": [
                            {"id": "660e8400-e29b-41d4-a716-446655440001", "required": True}
                        ],
                        "inputs": {
                            "url": "https://hooks.slack.com/services/XXX",
                            "method": "POST",
                            "data": {"text": "Weather update processed"}
                        },
                    },
                ],
                indent=2,
            ),
            "",
            "=== Example 4: Web Scraping Only (No AI Analysis) ===",
            json.dumps(
                [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Scrape Product Prices",
                        "schemas": {"method": "scrape_executor"},
                        "inputs": {
                            "url": "https://example.com/products",
                            "extract": "prices",
                            "selector": ".product-price"
                        },
                    }
                ],
                indent=2,
            ),
            "",
            "=== Example 5: CrewAI for Complex Multi-Agent Analysis ===",
            "Use crewai_executor ONLY when you need multiple AI agents collaborating:",
            json.dumps(
                [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Multi-Agent Market Research",
                        "schemas": {"method": "crewai_executor"},
                        "inputs": {
                            "works": {
                                "agents": {
                                    "researcher": {
                                        "role": "Market Researcher",
                                        "goal": "Gather and analyze market trends",
                                        "backstory": "Expert researcher with 15 years in market analysis",
                                        "llm": "gpt-4",
                                    },
                                    "writer": {
                                        "role": "Report Writer",
                                        "goal": "Create professional reports",
                                        "backstory": "Technical writer specialized in business reports",
                                        "llm": "gpt-4",
                                    },
                                },
                                "tasks": {
                                    "research": {
                                        "description": "Research market trends in electric vehicles",
                                        "agent": "researcher",
                                        "prompt": "Return JSON: {trends: [], market_size: string, growth_rate: number}",
                                        "expected_output": "JSON with market analysis",
                                    },
                                    "report": {
                                        "description": "Create executive summary report",
                                        "agent": "writer",
                                        "prompt": "Generate markdown report with sections: Executive Summary, Key Trends, Recommendations",
                                        "expected_output": "Markdown-formatted report",
                                    },
                                },
                            }
                        },
                    }
                ],
                indent=2,
            ),
            "",
            "=== Example 6: Scrape + Aggregate (NO AI) ===",
            "For simple data collection without AI analysis, use scrape + aggregate:",
            json.dumps(
                [
                    {
                        "id": "root-aggregate",
                        "name": "Competitor Price Comparison",
                        "schemas": {"method": "aggregate_results_executor"},
                        "inputs": {},
                        "dependencies": [
                            {"id": "site-a", "required": True},
                            {"id": "site-b", "required": True},
                            {"id": "site-c", "required": True}
                        ],
                    },
                    {
                        "id": "site-a",
                        "name": "Scrape Site A Prices",
                        "parent_id": "root-aggregate",
                        "schemas": {"method": "scrape_executor"},
                        "inputs": {"url": "https://competitor-a.com/product", "extract": "price"},
                    },
                    {
                        "id": "site-b",
                        "name": "Scrape Site B Prices",
                        "parent_id": "root-aggregate",
                        "schemas": {"method": "scrape_executor"},
                        "inputs": {"url": "https://competitor-b.com/product", "extract": "price"},
                    },
                    {
                        "id": "site-c",
                        "name": "Scrape Site C Prices",
                        "parent_id": "root-aggregate",
                        "schemas": {"method": "scrape_executor"},
                        "inputs": {"url": "https://competitor-c.com/product", "extract": "price"},
                    },
                ],
                indent=2,
            ),
            "",
            "IMPORTANT: Root aggregator task MUST have 'dependencies' field listing all direct child task IDs.",
            "This tells the aggregator which tasks' results to collect and merge into the final result.",
            "dependency's result is passed to the CrewAI agent for analysis.",
            "",
            "=== Output Format ===",
            "Return ONLY a valid JSON array. No markdown, no explanations.",
        ]

        if user_id:
            prompt_parts.append("")
            prompt_parts.append(f"Note: Use user_id='{user_id}' for all generated tasks.")

        prompt_parts.append("")
        prompt_parts.append("=== Generate Task Tree ===")
        prompt_parts.append("Now generate the task tree JSON array based on the requirement above.")

        return "\n".join(prompt_parts)

    def _attempt_json_repair(self, response: str) -> Optional[str]:
        """
        Attempt to repair truncated or malformed JSON

        This method tries to fix common issues with LLM-generated JSON:
        1. Truncated responses (incomplete objects/arrays)
        2. Missing closing brackets
        3. Trailing commas

        Args:
            response: Potentially malformed JSON string

        Returns:
            Repaired JSON string, or None if repair failed
        """
        try:
            # Strategy: Parse incrementally and keep only complete objects
            repaired = response.strip()

            # If it starts with '[', we expect a JSON array
            if repaired.startswith("["):
                # Try to extract complete objects from the array
                # Find all complete objects (those with matching braces)
                complete_objects = []
                depth = 0
                in_string = False
                escape_next = False
                current_obj_start = None

                for i, char in enumerate(repaired):
                    if escape_next:
                        escape_next = False
                        continue

                    if char == "\\":
                        escape_next = True
                        continue

                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue

                    if in_string:
                        continue

                    if char == "{":
                        if depth == 0:
                            current_obj_start = i
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0 and current_obj_start is not None:
                            # We have a complete object
                            obj_str = repaired[current_obj_start : i + 1]
                            try:
                                json.loads(obj_str)
                                complete_objects.append(obj_str)
                            except json.JSONDecodeError:
                                # Skip malformed objects
                                pass
                            current_obj_start = None

                if complete_objects:
                    # Build a valid JSON array from complete objects
                    repaired = "[" + ", ".join(complete_objects) + "]"
                    json.loads(repaired)  # Validate
                    return repaired

            # Fallback: Try simple bracket matching
            open_braces = response.count("{")
            close_braces = response.count("}")
            open_brackets = response.count("[")
            close_brackets = response.count("]")

            repaired = response
            if close_braces < open_braces:
                repaired += "}" * (open_braces - close_braces)
            if close_brackets < open_brackets:
                repaired += "]" * (open_brackets - close_brackets)

            json.loads(repaired)
            return repaired

        except Exception as e:
            logger.debug(f"JSON repair attempt failed: {e}")
            return None

    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM JSON response

        Args:
            response: LLM response text

        Returns:
            List of task dictionaries

        Raises:
            ValueError: If response cannot be parsed
        """
        # Try to extract JSON from response (might be wrapped in markdown code blocks)
        response = response.strip()

        # Remove markdown code blocks if present
        json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_match = re.search(r"(\[.*\])", response, re.DOTALL)
            if json_match:
                response = json_match.group(1)

        # Parse JSON
        try:
            tasks = json.loads(response)
        except json.JSONDecodeError as e:
            # Try to repair truncated JSON by attempting to parse partial content
            repaired_response = self._attempt_json_repair(response)
            if repaired_response:
                try:
                    tasks = json.loads(repaired_response)
                    logger.warning(
                        f"Repaired truncated JSON response. Original error: {e}"
                    )
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Failed to parse JSON from LLM response: {e}. Response: {response[:500]}"
                    )
            else:
                raise ValueError(
                    f"Failed to parse JSON from LLM response: {e}. Response: {response[:500]}"
                )

        # Validate it's a list
        if not isinstance(tasks, list):
            raise ValueError(f"LLM response is not a list, got {type(tasks)}")

        # Validate each task is a dict
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError(f"Task at index {i} is not a dictionary, got {type(task)}")

        return tasks

    def _post_process_tasks(
        self, tasks: List[Dict[str, Any]], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Post-process generated tasks to ensure correct format

        - Ensures all tasks have UUID format IDs
        - Ensures all tasks have correct user_id from BaseTask
        - Ensures all dependencies references use correct UUID IDs

        Args:
            tasks: List of task dictionaries from LLM
            user_id: User ID from BaseTask (self.user_id)

        Returns:
            Post-processed list of task dictionaries
        """
        # Get user_id from BaseTask if not provided
        if not user_id:
            user_id = self.user_id
            if user_id:
                logger.debug(f"Using user_id '{user_id}' from BaseTask.task.user_id")
            else:
                logger.debug(
                    "No user_id available from BaseTask.task.user_id (task.user_id is None)"
                )

        # UUID validation regex (UUID v4 format: 8-4-4-4-12)
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE
        )

        # Step 1: Build task ID mapping (name -> task) for reference lookup
        name_to_task: Dict[str, Dict[str, Any]] = {}
        id_to_task: Dict[str, Dict[str, Any]] = {}

        for task in tasks:
            task_name = task.get("name")
            task_id = task.get("id")
            if task_name:
                name_to_task[task_name] = task
            if task_id:
                id_to_task[task_id] = task

        # Step 2: Track ID mappings for updating references
        id_mapping: Dict[str, str] = {}  # old_id -> new_uuid

        # Step 3: Fix all task IDs to be UUIDs and ensure correct user_id
        for task in tasks:
            # Fix user_id: ALWAYS use BaseTask.user_id (self.user_id) to override any LLM-generated value
            # This ensures generated tasks use the correct user_id from the request context,
            # not hardcoded values like "api_user" or "user123" that LLM might generate

            # Determine the correct user_id to use (priority: parameter > self.user_id > None)
            correct_user_id = user_id or self.user_id

            if correct_user_id:
                logger.debug(
                    f"Using correct_user_id '{correct_user_id}' for task '{task.get('name')}' (parameter: {user_id}, self.user_id: {self.user_id})"
                )
                # Always override LLM-generated user_id with correct one from BaseTask context
                old_user_id = task.get("user_id")
                if old_user_id != correct_user_id:
                    task["user_id"] = correct_user_id
                    if old_user_id:
                        logger.debug(
                            f"Overrode LLM-generated user_id '{old_user_id}' with actual user_id '{correct_user_id}' for task '{task.get('name')}'"
                        )
            else:
                # No user_id available from BaseTask context, set to None
                # Don't keep LLM-generated values like "api_user" or "user123"
                if task.get("user_id"):
                    logger.warning(
                        f"Removed LLM-generated user_id '{task.get('user_id')}' for task '{task.get('name')}' "
                        f"(no user_id in context: parameter={user_id}, self.user_id={self.user_id}). "
                        f"This means the request had no JWT token or verify_token_func is not available."
                    )
                task["user_id"] = None

            # Fix task ID: ensure it's a valid UUID
            old_id = task.get("id")
            if old_id:
                # Check if it's a valid UUID
                if not uuid_pattern.match(old_id):
                    # Generate new UUID and track mapping
                    new_id = str(uuid.uuid4())
                    id_mapping[old_id] = new_id
                    task["id"] = new_id
                    logger.debug(
                        f"Generated new UUID for task '{task.get('name')}': {old_id} -> {new_id}"
                    )
                # If it's already a valid UUID, keep it
            else:
                # No ID provided, generate one
                new_id = str(uuid.uuid4())
                task["id"] = new_id
                logger.debug(f"Generated UUID for task '{task.get('name')}': {new_id}")

        # Step 4: Update all references (parent_id and dependencies) with correct UUIDs
        for task in tasks:
            # Update parent_id
            if "parent_id" in task and task["parent_id"]:
                parent_ref = task["parent_id"]
                # Check if parent_ref needs to be mapped
                if parent_ref in id_mapping:
                    task["parent_id"] = id_mapping[parent_ref]
                # If parent_ref is not a UUID, try to find the task by name and use its ID
                elif not uuid_pattern.match(parent_ref):
                    if parent_ref in name_to_task:
                        task["parent_id"] = name_to_task[parent_ref]["id"]
                        logger.debug(
                            f"Updated parent_id for task '{task.get('name')}': {parent_ref} -> {name_to_task[parent_ref]['id']}"
                        )
                    elif parent_ref in id_to_task:
                        # Parent ref exists but was mapped, use the mapped ID
                        mapped_id = id_mapping.get(parent_ref)
                        if mapped_id:
                            task["parent_id"] = mapped_id

                # Final validation: ensure parent_id is a valid UUID
                if task["parent_id"] and not uuid_pattern.match(task["parent_id"]):
                    logger.warning(
                        f"Task '{task.get('name')}' has invalid parent_id '{task['parent_id']}', removing it"
                    )
                    task.pop("parent_id", None)

            # Update dependencies - ensure all dependency IDs are correct UUIDs
            if "dependencies" in task and isinstance(task["dependencies"], list):
                updated_deps = []
                for dep in task["dependencies"]:
                    if isinstance(dep, dict):
                        dep_id = dep.get("id")
                        if dep_id:
                            # Check if dep_id needs to be mapped
                            if dep_id in id_mapping:
                                dep["id"] = id_mapping[dep_id]
                                updated_deps.append(dep)
                            # If dep_id is not a UUID, try to find the task by name and use its ID
                            elif not uuid_pattern.match(dep_id):
                                if dep_id in name_to_task:
                                    dep["id"] = name_to_task[dep_id]["id"]
                                    updated_deps.append(dep)
                                    logger.debug(
                                        f"Updated dependency id for task '{task.get('name')}': {dep_id} -> {name_to_task[dep_id]['id']}"
                                    )
                                elif dep_id in id_to_task:
                                    # Dep ref exists but was mapped, use the mapped ID
                                    mapped_id = id_mapping.get(dep_id)
                                    if mapped_id:
                                        dep["id"] = mapped_id
                                        updated_deps.append(dep)
                                else:
                                    # Invalid dependency reference, skip it
                                    logger.warning(
                                        f"Task '{task.get('name')}' has invalid dependency id '{dep_id}', skipping it"
                                    )
                            else:
                                # Valid UUID, keep it
                                updated_deps.append(dep)
                        else:
                            # No id in dependency, skip it
                            logger.warning(
                                f"Task '{task.get('name')}' has dependency without 'id' field, skipping it"
                            )
                    else:
                        # Invalid dependency format, skip it
                        logger.warning(
                            f"Task '{task.get('name')}' has invalid dependency format, skipping it"
                        )

                # Update dependencies list
                task["dependencies"] = updated_deps

        return tasks

    def _validate_tasks_array(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate generated tasks array against TaskCreator requirements

        Args:
            tasks: List of task dictionaries

        Returns:
            Dictionary with:
                - valid: bool
                - error: str (if invalid)
        """
        if not tasks:
            return {"valid": False, "error": "Tasks array is empty"}

        # Check all tasks have 'name' field
        for i, task in enumerate(tasks):
            if "name" not in task:
                return {"valid": False, "error": f"Task at index {i} is missing 'name' field"}
            if not task["name"]:
                return {"valid": False, "error": f"Task at index {i} has empty 'name' field"}

        # Check id consistency (either all have id or none do)
        tasks_with_id = sum(1 for task in tasks if "id" in task)
        tasks_without_id = len(tasks) - tasks_with_id

        if tasks_with_id > 0 and tasks_without_id > 0:
            return {
                "valid": False,
                "error": "Mixed mode not supported: either all tasks must have 'id', or all tasks must not have 'id'",
            }

        # Build identifier sets
        if tasks_with_id > 0:
            # Use id for references
            identifiers: Set[str] = {task["id"] for task in tasks if "id" in task}
            identifier_to_task = {task["id"]: task for task in tasks if "id" in task}
        else:
            # Use name for references
            identifiers = {task["name"] for task in tasks}
            identifier_to_task = {task["name"]: task for task in tasks}

        # Check for duplicate identifiers
        if len(identifiers) < len(tasks):
            return {"valid": False, "error": "Duplicate task identifiers found"}

        # Validate parent_id references
        for i, task in enumerate(tasks):
            parent_id = task.get("parent_id")
            if parent_id:
                if parent_id not in identifiers:
                    return {
                        "valid": False,
                        "error": f"Task '{task.get('name', i)}' has parent_id '{parent_id}' which is not in the tasks array",
                    }

        # Validate dependency references
        for i, task in enumerate(tasks):
            dependencies = task.get("dependencies")
            if dependencies:
                if not isinstance(dependencies, list):
                    return {
                        "valid": False,
                        "error": f"Task '{task.get('name', i)}' has invalid dependencies (must be a list)",
                    }
                for dep in dependencies:
                    if isinstance(dep, dict):
                        dep_ref = dep.get("id") or dep.get("name")
                        if dep_ref and dep_ref not in identifiers:
                            return {
                                "valid": False,
                                "error": f"Task '{task.get('name', i)}' has dependency '{dep_ref}' which is not in the tasks array",
                            }
                    elif isinstance(dep, str):
                        if dep not in identifiers:
                            return {
                                "valid": False,
                                "error": f"Task '{task.get('name', i)}' has dependency '{dep}' which is not in the tasks array",
                            }

        # Check for single root task
        root_tasks = [task for task in tasks if not task.get("parent_id")]
        if len(root_tasks) == 0:
            return {"valid": False, "error": "No root task found (task with no parent_id)"}
        if len(root_tasks) > 1:
            root_task_names = [task.get("name", "unknown") for task in root_tasks]
            return {
                "valid": False,
                "error": (
                    f"Multiple root tasks found: {root_task_names}. "
                    f"Only one root task is allowed. "
                    f"Fix: Set parent_id for all non-root tasks. "
                    f"For sequential tasks, set parent_id to the previous task. "
                    f"For tasks with dependencies, set parent_id to the first dependency. "
                    f"For parallel tasks, choose one as root and set others' parent_id to the root."
                ),
            }

        # Check for circular dependencies (simple check - all tasks reachable from root)
        if tasks_with_id > 0:
            root_id = root_tasks[0]["id"]
            reachable = {root_id}

            def collect_reachable(current_id: str):
                for task in tasks:
                    if task.get("parent_id") == current_id:
                        task_id = task["id"]
                        if task_id not in reachable:
                            reachable.add(task_id)
                            collect_reachable(task_id)

            collect_reachable(root_id)

            all_ids = {task["id"] for task in tasks}
            unreachable = all_ids - reachable
            if unreachable:
                return {
                    "valid": False,
                    "error": f"Tasks not reachable from root: {[identifier_to_task[id].get('name', id) for id in unreachable]}",
                }

        schema_validation = self._validate_schema_compliance(tasks)
        if not schema_validation["valid"]:
            return schema_validation

        root_pattern_validation = self._validate_root_task_pattern(tasks)
        if not root_pattern_validation["valid"]:
            return root_pattern_validation

        return {"valid": True, "error": None}

    def _validate_schema_compliance(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate that task inputs match executor schemas

        Args:
            tasks: List of task dictionaries

        Returns:
            Dictionary with valid flag and error message
        """
        from apflow.core.extensions.registry import get_registry

        registry = get_registry()

        for i, task in enumerate(tasks):
            task_name = task.get("name", f"task_{i}")
            schemas = task.get("schemas", {})
            executor_id = schemas.get("method")

            if not executor_id:
                return {"valid": False, "error": f"Task '{task_name}' missing schemas.method field"}

            # Special handling for crewai_executor: validate works parameter directly
            if executor_id == "crewai_executor":
                task_inputs = task.get("inputs", {})
                if "works" not in task_inputs:
                    return {
                        "valid": False,
                        "error": (
                            f"Task '{task_name}' using executor 'crewai_executor' "
                            f"is missing required field 'works'. "
                            f"Expected: inputs.works = {{\"agents\": {{...}}, \"tasks\": {{...}}}}"
                        ),
                    }
                works = task_inputs.get("works", {})
                if not isinstance(works, dict):
                    return {
                        "valid": False,
                        "error": (
                            f"Task '{task_name}' field 'works' must be object/dict, "
                            f"got {self._get_json_type(works)}"
                        ),
                    }
                if "agents" not in works or "tasks" not in works:
                    return {
                        "valid": False,
                        "error": (
                            f"Task '{task_name}' field 'works' must contain 'agents' and 'tasks' keys"
                        ),
                    }
                # Validate that agents and tasks are dicts
                if not isinstance(works.get("agents"), dict):
                    return {
                        "valid": False,
                        "error": f"Task '{task_name}' field 'works.agents' must be object/dict",
                    }
                if not isinstance(works.get("tasks"), dict):
                    return {
                        "valid": False,
                        "error": f"Task '{task_name}' field 'works.tasks' must be object/dict",
                    }
                # Validate each agent has role and goal
                agents = works.get("agents", {})
                for agent_name, agent_config in agents.items():
                    if not isinstance(agent_config, dict):
                        return {
                            "valid": False,
                            "error": f"Task '{task_name}' agent '{agent_name}' must be object/dict",
                        }
                    if "role" not in agent_config or "goal" not in agent_config:
                        return {
                            "valid": False,
                            "error": (
                                f"Task '{task_name}' agent '{agent_name}' must have 'role' and 'goal' fields"
                            ),
                        }
                # Validate each task has description and agent
                tasks_config = works.get("tasks", {})
                for task_key, task_config in tasks_config.items():
                    if not isinstance(task_config, dict):
                        return {
                            "valid": False,
                            "error": f"Task '{task_name}' crew task '{task_key}' must be object/dict",
                        }
                    if "description" not in task_config or "agent" not in task_config:
                        return {
                            "valid": False,
                            "error": (
                                f"Task '{task_name}' crew task '{task_key}' must have 'description' and 'agent' fields"
                            ),
                        }
                    agent_ref = task_config.get("agent")
                    if agent_ref not in agents:
                        return {
                            "valid": False,
                            "error": (
                                f"Task '{task_name}' crew task '{task_key}' references unknown agent '{agent_ref}'"
                            ),
                        }
                continue

            try:
                executor = registry.create_executor_instance(executor_id, inputs={})
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Task '{task_name}' uses unknown executor '{executor_id}': {str(e)}",
                }

            if not hasattr(executor, "get_input_schema"):
                continue

            try:
                schema = executor.get_input_schema()
            except Exception:
                continue

            if not schema or not isinstance(schema, dict):
                continue

            task_inputs = task.get("inputs", {})
            required_fields = schema.get("required", [])
            properties = schema.get("properties", {})

            for required_field in required_fields:
                if required_field not in task_inputs:
                    return {
                        "valid": False,
                        "error": (
                            f"Task '{task_name}' using executor '{executor_id}' "
                            f"is missing required field '{required_field}'"
                        ),
                    }

            for field_name, field_value in task_inputs.items():
                if field_name not in properties:
                    continue

                expected_type = properties[field_name].get("type")
                if not expected_type:
                    continue

                actual_type = self._get_json_type(field_value)
                if not self._is_compatible_type(actual_type, expected_type):
                    return {
                        "valid": False,
                        "error": (
                            f"Task '{task_name}' field '{field_name}' has type '{actual_type}' "
                            f"but executor '{executor_id}' expects type '{expected_type}'"
                        ),
                    }

        return {"valid": True, "error": None}

    def _get_json_type(self, value: Any) -> str:
        """Map Python type to JSON Schema type"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "unknown"

    def _is_compatible_type(self, actual: str, expected: str) -> bool:
        """Check if actual type is compatible with expected type"""
        if actual == expected:
            return True

        if expected == "number" and actual == "integer":
            return True

        if expected in ["string", "number", "integer", "boolean", "array", "object"]:
            return actual == expected

        return False

    def _validate_root_task_pattern(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate root task pattern: if 2+ executors, root should be aggregator
        """
        if len(tasks) < 2:
            return {"valid": True, "error": None}

        root_tasks = [task for task in tasks if not task.get("parent_id")]
        if len(root_tasks) != 1:
            return {"valid": True, "error": None}

        root_task = root_tasks[0]
        root_executor = root_task.get("schemas", {}).get("method", "")

        non_aggregator_executors = set()
        for task in tasks:
            executor_id = task.get("schemas", {}).get("method", "")
            if executor_id and "aggregate" not in executor_id.lower():
                non_aggregator_executors.add(executor_id)

        if len(non_aggregator_executors) >= 2:
            if "aggregate" not in root_executor.lower():
                return {
                    "valid": False,
                    "error": (
                        f"Task tree uses {len(non_aggregator_executors)} different executors "
                        f"but root task uses '{root_executor}'. "
                        f"When multiple executors are needed, root should use an aggregator executor "
                        f"(e.g., 'aggregate_results_executor') to collect results from child tasks."
                    ),
                }

        return {"valid": True, "error": None}

    def _attempt_auto_fix(
        self, tasks: List[Dict[str, Any]], error_message: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Attempt to automatically fix common validation errors

        Args:
            tasks: List of task dictionaries
            error_message: Validation error message

        Returns:
            Fixed tasks if successful, None if unable to fix
        """
        if "Multiple root tasks" in error_message:
            logger.info("Auto-fix: Multiple root tasks detected, attempting fix...")
            return self._fix_multiple_roots(tasks)

        if "parent_id" in error_message.lower() and "not in the tasks array" in error_message:
            logger.info("Auto-fix: Invalid parent_id references, attempting fix...")
            return self._fix_invalid_parent_ids(tasks)

        if "not reachable from root" in error_message:
            logger.info("Auto-fix: Unreachable tasks detected, attempting fix...")
            return self._fix_invalid_parent_ids(tasks)

        if "different executors" in error_message and "root should use an aggregator" in error_message:
            logger.info("Auto-fix: Multiple executors detected, converting root to aggregator...")
            return self._fix_root_executor_to_aggregator(tasks)

        logger.warning(f"No auto-fix available for error: {error_message}")
        return None

    def _fix_multiple_roots(self, tasks: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """
        Fix multiple root tasks by adding an aggregator root
        """
        try:
            root_tasks = [task for task in tasks if not task.get("parent_id")]

            if len(root_tasks) <= 1:
                return None

            logger.info(f"Found {len(root_tasks)} root tasks, creating aggregator root")

            aggregator_id = str(uuid.uuid4())
            aggregator_task = {
                "id": aggregator_id,
                "name": "Aggregate Results",
                "schemas": {"method": "aggregate_results_executor"},
                "inputs": {},
            }

            for root_task in root_tasks:
                root_task["parent_id"] = aggregator_id

            fixed_tasks = [aggregator_task] + tasks
            logger.info(f"Created aggregator root with ID: {aggregator_id}")

            return fixed_tasks

        except Exception as e:
            logger.error(f"Failed to fix multiple roots: {e}")
            return None

    def _fix_invalid_parent_ids(
        self, tasks: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fix invalid parent_id references by setting to first valid task or root
        """
        try:
            task_ids = {task.get("id") for task in tasks if task.get("id")}

            if not task_ids:
                return None

            root_tasks = [task for task in tasks if not task.get("parent_id")]
            root_id = root_tasks[0].get("id") if root_tasks else None

            fixed_count = 0
            for task in tasks:
                parent_id = task.get("parent_id")
                if parent_id and parent_id not in task_ids:
                    logger.warning(f"Task {task.get('name')} has invalid parent_id: {parent_id}")

                    dependencies = task.get("dependencies", [])
                    if dependencies:
                        first_dep_id = (
                            dependencies[0].get("id")
                            if isinstance(dependencies[0], dict)
                            else dependencies[0]
                        )
                        if first_dep_id in task_ids:
                            task["parent_id"] = first_dep_id
                            fixed_count += 1
                            logger.info(f"Fixed parent_id for {task.get('name')}: {first_dep_id}")
                            continue

                    if root_id and task.get("id") != root_id:
                        task["parent_id"] = root_id
                        fixed_count += 1
                        logger.info(f"Set parent_id to root for {task.get('name')}: {root_id}")
                    else:
                        task.pop("parent_id", None)
                        fixed_count += 1
                        logger.info(f"Removed invalid parent_id from {task.get('name')}")

            logger.info(f"Fixed {fixed_count} invalid parent_id references")
            return tasks if fixed_count > 0 else None

        except Exception as e:
            logger.error(f"Failed to fix invalid parent_ids: {e}")
            return None

    def _fix_root_executor_to_aggregator(
        self, tasks: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fix root task executor when multiple different executors are used.
        Converts root task to use an aggregator executor or inserts a new aggregator root.

        Args:
            tasks: List of task dictionaries

        Returns:
            Fixed tasks if successful, None if unable to fix
        """
        try:
            root_tasks = [task for task in tasks if not task.get("parent_id")]
            if len(root_tasks) != 1:
                return None

            root_task = root_tasks[0]
            root_executor = root_task.get("schemas", {}).get("method", "")

            # Check if root already uses aggregator
            if "aggregate" in root_executor.lower():
                return None

            # Count non-aggregator executors
            non_aggregator_executors = set()
            for task in tasks:
                executor_id = task.get("schemas", {}).get("method", "")
                if executor_id and "aggregate" not in executor_id.lower():
                    non_aggregator_executors.add(executor_id)

            # Only fix if we have 2+ different executors
            if len(non_aggregator_executors) < 2:
                return None

            logger.info(f"Detected {len(non_aggregator_executors)} different executors, "
                       f"converting root from '{root_executor}' to aggregator")

            # Strategy: Convert the root task to use aggregate_results_executor
            # and make all direct children of the root point to it
            root_task["schemas"]["method"] = "aggregate_results_executor"
            
            # Clear root task inputs if they are specific to the old executor
            # Keep only generic fields that aggregator can use
            old_inputs = root_task.get("inputs", {})
            root_task["inputs"] = {}
            
            # Preserve user_id if present
            if "user_id" in old_inputs:
                root_task["inputs"]["user_id"] = old_inputs["user_id"]

            # Add dependencies for all direct child tasks
            # aggregate_results_executor needs dependencies to know which tasks to aggregate
            root_id = root_task.get("id")
            child_tasks = [t for t in tasks if t.get("parent_id") == root_id]
            
            if child_tasks:
                root_task["dependencies"] = [
                    {"id": child["id"], "required": True}
                    for child in child_tasks
                ]
                logger.info(f"Added {len(child_tasks)} dependencies to root aggregator: "
                           f"{[c['id'] for c in child_tasks]}")

            logger.info(f"Converted root task '{root_task.get('name')}' to use 'aggregate_results_executor'")
            
            return tasks

        except Exception as e:
            logger.error(f"Failed to fix root executor: {e}")
            return None

    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo generated task tree"""
        requirement = inputs.get("requirement", "Demo requirement")
        user_id = inputs.get("user_id", "demo_user")

        # Return a simple demo task tree based on requirement
        demo_tasks = [
            {
                "id": "demo-task-1",
                "name": "demo_task_1",
                "user_id": user_id,
                "schemas": {"method": "system_info_executor"},
                "inputs": {"resource": "cpu"},
            },
            {
                "id": "demo-task-2",
                "name": "demo_task_2",
                "user_id": user_id,
                "schemas": {"method": "system_info_executor"},
                "inputs": {"resource": "memory"},
                "dependencies": [{"id": "demo-task-1", "required": True}],
            },
        ]

        return {
            "status": "completed",
            "tasks": demo_tasks,
            "requirement": requirement,
            "task_count": len(demo_tasks),
            "_demo_sleep": 1.5,  # Simulate LLM generation time (longer for realistic demo)
        }

    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "requirement": {
                    "type": "string",
                    "description": "Natural language requirement describing the task tree to generate",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID for generated tasks (optional)",
                },
                "generation_mode": {
                    "type": "string",
                    "enum": ["single_shot", "multi_phase"],
                    "description": "Generation mode: 'single_shot' (default, faster) or 'multi_phase' (more accurate)",
                    "default": "single_shot",
                },
                "llm_provider": {
                    "type": "string",
                    "enum": ["openai", "anthropic"],
                    "description": "LLM provider to use (defaults to OPENAI_API_KEY or APFLOW_LLM_PROVIDER env var)",
                },
                "model": {
                    "type": "string",
                    "description": "LLM model name (optional, uses provider default)",
                },
                "temperature": {
                    "type": "number",
                    "description": "LLM temperature (default: 0.7)",
                    "default": 0.7,
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens for LLM response (default: 4000)",
                    "default": 4000,
                },
            },
            "required": ["requirement"],
        }

    def get_output_schema(self) -> Dict[str, Any]:
        """Return output result schema"""
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["completed", "failed"],
                    "description": "Execution status",
                },
                "tasks": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Generated task array (only present on success)",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of generated tasks (only present on success)",
                },
                "error": {
                    "type": "string",
                    "description": "Error message (only present on failure)",
                },
            },
            "required": ["status"],
        }
