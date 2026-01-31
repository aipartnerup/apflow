"""
Multi-Phase Task Tree Generation using CrewAI

Implements 4-phase generation approach:
1. Requirement Analysis - Understand goal and identify executors
2. Structure Design - Design tree with correct parent_id relationships
3. Input Generation - Fill inputs matching schemas
4. Quality Review - Validate and auto-fix issues
"""

import json
from typing import Dict, Any, List, Optional
from apflow.logger import get_logger
from apflow.extensions.generate.schema_formatter import SchemaFormatter
from apflow.extensions.generate.principles_extractor import PrinciplesExtractor

logger = get_logger(__name__)


class MultiPhaseGenerationCrew:
    """Multi-phase task tree generation using CrewAI"""

    def __init__(
        self,
        llm_provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.llm_provider = llm_provider
        self.model = model
        self.api_key = api_key
        self.schema_formatter = SchemaFormatter()

    def _import_crewai(self):
        """Lazy import crewai to avoid slow module-level imports"""
        from crewai import Agent, Task, Crew, Process
        return Agent, Task, Crew, Process

    async def generate(self, requirement: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate task tree using 4-phase approach

        Args:
            requirement: User's natural language requirement
            user_id: Optional user ID

        Returns:
            Dictionary with generated tasks or error
        """
        try:
            executors_info = self.schema_formatter.format_for_requirement(
                requirement, max_executors=15, include_examples=True
            )

            principles = PrinciplesExtractor.build_complete_principles_section()

            phase1_result = await self._phase1_analyze_requirement(
                requirement, executors_info, principles
            )

            if not phase1_result.get("success"):
                return {"success": False, "error": f"Phase 1 failed: {phase1_result.get('error')}"}

            analysis = phase1_result.get("analysis", {})

            phase2_result = await self._phase2_design_structure(
                requirement, analysis, executors_info, principles
            )

            if not phase2_result.get("success"):
                return {"success": False, "error": f"Phase 2 failed: {phase2_result.get('error')}"}

            structure = phase2_result.get("structure", [])

            phase3_result = await self._phase3_generate_inputs(
                requirement, structure, executors_info
            )

            if not phase3_result.get("success"):
                return {"success": False, "error": f"Phase 3 failed: {phase3_result.get('error')}"}

            tasks_with_inputs = phase3_result.get("tasks", [])

            phase4_result = await self._phase4_review_and_validate(
                tasks_with_inputs, requirement, principles
            )

            if not phase4_result.get("success"):
                return {"success": False, "error": f"Phase 4 failed: {phase4_result.get('error')}"}

            final_tasks = phase4_result.get("tasks", [])

            if user_id:
                for task in final_tasks:
                    task["user_id"] = user_id

            return {
                "success": True,
                "tasks": final_tasks,
                "phases": {
                    "analysis": analysis,
                    "structure_count": len(structure),
                    "final_count": len(final_tasks),
                },
            }

        except Exception as e:
            logger.error(f"Multi-phase generation failed: {e}", exc_info=True)
            return {"success": False, "error": f"Generation failed: {str(e)}"}

    async def _phase1_analyze_requirement(
        self, requirement: str, executors_info: str, principles: str
    ) -> Dict[str, Any]:
        """
        Phase 1: Analyze requirement and identify needed executors
        """
        Agent, Task, Crew, Process = self._import_crewai()
        try:
            agent = Agent(
                role="Requirement Analyzer",
                goal="Analyze user requirements and identify needed executors",
                backstory=(
                    "You are an expert at understanding business requirements "
                    "and mapping them to technical executors. You identify which "
                    "executors are needed and determine if an aggregator root is required."
                ),
                verbose=False,
                allow_delegation=False,
            )

            task = Task(
                description=f"""
Analyze this requirement and identify which executors are needed:

REQUIREMENT: {requirement}

AVAILABLE EXECUTORS:
{executors_info[:2000]}

Provide your analysis as JSON:
{{
    "goal": "what the user wants to achieve",
    "steps": ["step 1", "step 2", ...],
    "executors_needed": ["executor_id1", "executor_id2", ...],
    "needs_aggregator": true/false (true if 2+ executors needed),
    "execution_pattern": "sequential/parallel/fan-out"
}}

Return ONLY valid JSON, no markdown, no explanations.
                """,
                agent=agent,
                expected_output="JSON analysis of requirement",
            )

            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

            result = crew.kickoff()
            result_str = str(result)

            json_match = self._extract_json(result_str)
            if not json_match:
                return {"success": False, "error": "Failed to parse analysis JSON"}

            analysis = json.loads(json_match)
            return {"success": True, "analysis": analysis}

        except Exception as e:
            logger.error(f"Phase 1 failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _phase2_design_structure(
        self, requirement: str, analysis: Dict[str, Any], executors_info: str, principles: str
    ) -> Dict[str, Any]:
        """
        Phase 2: Design tree structure with correct parent_id relationships
        """
        Agent, Task, Crew, Process = self._import_crewai()
        try:
            agent = Agent(
                role="Structure Designer",
                goal="Design correct task tree structure with proper parent_id relationships",
                backstory=(
                    "You are an expert at designing task tree structures. "
                    "You ensure single root, correct parent_id for all non-root tasks, "
                    "and proper dependency chains."
                ),
                verbose=False,
                allow_delegation=False,
            )

            needs_aggregator = analysis.get("needs_aggregator", False)
            executors_needed = analysis.get("executors_needed", [])

            task = Task(
                description=f"""
Design task tree structure for this requirement:

REQUIREMENT: {requirement}

ANALYSIS:
{json.dumps(analysis, indent=2)}

FRAMEWORK RULES:
{principles[:1500]}

Design the structure as JSON array (WITHOUT inputs yet):
[
  {{
    "id": "uuid-1",
    "name": "Task Name",
    "schemas": {{"method": "executor_id"}},
    "parent_id": null (for root only),
    "dependencies": [...]
  }},
  ...
]

CRITICAL RULES:
1. Generate valid UUIDs for each task (format: 8-4-4-4-12)
2. Exactly ONE root task (no parent_id)
3. All other tasks MUST have parent_id
4. If {len(executors_needed)} executors needed and needs_aggregator={needs_aggregator}:
   - Root should be aggregate_results_executor if available
   - Actual work tasks should be children
5. Set dependencies for execution order
6. If task has dependencies, parent_id = first dependency ID

Return ONLY valid JSON array, no markdown.
                """,
                agent=agent,
                expected_output="JSON array of task structure",
            )

            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

            result = crew.kickoff()
            result_str = str(result)

            json_match = self._extract_json(result_str)
            if not json_match:
                return {"success": False, "error": "Failed to parse structure JSON"}

            structure = json.loads(json_match)

            if not isinstance(structure, list):
                return {"success": False, "error": "Structure must be JSON array"}

            return {"success": True, "structure": structure}

        except Exception as e:
            logger.error(f"Phase 2 failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _phase3_generate_inputs(
        self, requirement: str, structure: List[Dict[str, Any]], executors_info: str
    ) -> Dict[str, Any]:
        """
        Phase 3: Fill inputs for each task matching executor schemas
        """
        Agent, Task, Crew, Process = self._import_crewai()
        try:
            agent = Agent(
                role="Schema Validator",
                goal="Fill task inputs matching executor schemas exactly",
                backstory=(
                    "You are an expert at matching task inputs to executor schemas. "
                    "You ensure all required fields are present and types are correct."
                ),
                verbose=False,
                allow_delegation=False,
            )

            task = Task(
                description=f"""
Fill inputs for each task matching executor schemas:

REQUIREMENT: {requirement}

TASK STRUCTURE:
{json.dumps(structure, indent=2)}

EXECUTOR SCHEMAS:
{executors_info[:3000]}

For each task:
1. Find the executor's input schema
2. Fill ALL required fields
3. Use realistic values based on requirement
4. Ensure types match schema

Return complete tasks with inputs as JSON array:
[
  {{
    "id": "...",
    "name": "...",
    "schemas": {{"method": "..."}},
    "parent_id": "..." (if not root),
    "dependencies": [...],
    "inputs": {{
      "field1": "value1",
      "field2": "value2"
    }}
  }},
  ...
]

Return ONLY valid JSON array, no markdown.
                """,
                agent=agent,
                expected_output="JSON array with complete inputs",
            )

            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

            result = crew.kickoff()
            result_str = str(result)

            json_match = self._extract_json(result_str)
            if not json_match:
                return {"success": False, "error": "Failed to parse inputs JSON"}

            tasks_with_inputs = json.loads(json_match)

            if not isinstance(tasks_with_inputs, list):
                return {"success": False, "error": "Tasks must be JSON array"}

            return {"success": True, "tasks": tasks_with_inputs}

        except Exception as e:
            logger.error(f"Phase 3 failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _phase4_review_and_validate(
        self, tasks: List[Dict[str, Any]], requirement: str, principles: str
    ) -> Dict[str, Any]:
        """
        Phase 4: Final validation and auto-fix issues
        """
        Agent, Task, Crew, Process = self._import_crewai()
        try:
            agent = Agent(
                role="Quality Reviewer",
                goal="Validate task tree and fix any issues",
                backstory=(
                    "You are an expert at validating task trees. "
                    "You check for structural issues, UUID format, schema compliance, "
                    "and fix problems automatically."
                ),
                verbose=False,
                allow_delegation=False,
            )

            task = Task(
                description=f"""
Review and validate this task tree:

TASKS:
{json.dumps(tasks, indent=2)}

FRAMEWORK RULES:
{principles[:1500]}

VALIDATION CHECKLIST:
□ All UUIDs valid format (8-4-4-4-12)
□ Exactly one root task (no parent_id)
□ All other tasks have parent_id
□ All parent_id references exist
□ All dependency references exist
□ No circular dependencies
□ All schemas.method are valid executor IDs

If you find issues, FIX THEM automatically:
- Invalid UUIDs → generate new valid UUIDs
- Multiple roots → convert to single root with aggregator
- Missing parent_id → set to appropriate parent
- Invalid references → remove or fix

Return validated and fixed tasks as JSON array.
Return ONLY valid JSON array, no markdown, no explanations.
                """,
                agent=agent,
                expected_output="Validated JSON array",
            )

            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

            result = crew.kickoff()
            result_str = str(result)

            json_match = self._extract_json(result_str)
            if not json_match:
                logger.warning("Phase 4 couldn't parse JSON, using original tasks")
                return {"success": True, "tasks": tasks}

            validated_tasks = json.loads(json_match)

            if not isinstance(validated_tasks, list):
                logger.warning("Phase 4 result not array, using original tasks")
                return {"success": True, "tasks": tasks}

            return {"success": True, "tasks": validated_tasks}

        except Exception as e:
            logger.warning(f"Phase 4 failed, using original tasks: {e}")
            return {"success": True, "tasks": tasks}

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text that may contain markdown"""
        import re

        text = text.strip()

        json_match = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        if text.startswith("[") or text.startswith("{"):
            return text

        json_match = re.search(r"([\{\[].*[\}\]])", text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        return None


__all__ = ["MultiPhaseGenerationCrew"]
