"""
Documentation Loader

This module loads and formats framework documentation for LLM context
when generating task trees.
"""

import os
from pathlib import Path
from typing import Optional
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Get the project root directory (assuming this file is in src/aipartnerupflow/extensions/generate/)
# Go up from this file: generate/ -> extensions/ -> aipartnerupflow/ -> src/ -> project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_DOCS_DIR = _PROJECT_ROOT / "docs"


def _read_doc_file(relative_path: str) -> str:
    """
    Read a documentation file
    
    Args:
        relative_path: Path relative to docs/ directory
        
    Returns:
        File contents as string, or empty string if file not found
    """
    file_path = _DOCS_DIR / relative_path
    try:
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding='utf-8')
        else:
            logger.warning(f"Documentation file not found: {file_path}")
            return ""
    except Exception as e:
        logger.error(f"Error reading documentation file {file_path}: {e}")
        return ""


def load_task_orchestration_docs() -> str:
    """
    Load task orchestration guide
    
    Returns:
        Task orchestration documentation content
    """
    return _read_doc_file("guides/task-orchestration.md")


def load_task_examples() -> str:
    """
    Load task tree examples
    
    Returns:
        Task tree examples documentation content
    """
    return _read_doc_file("examples/task-tree.md")


def load_executor_docs() -> str:
    """
    Load custom tasks guide
    
    Returns:
        Custom tasks documentation content
    """
    return _read_doc_file("guides/custom-tasks.md")


def load_concepts() -> str:
    """
    Load core concepts documentation
    
    Returns:
        Core concepts documentation content
    """
    return _read_doc_file("getting-started/concepts.md")


def load_all_docs() -> str:
    """
    Load all relevant documentation for LLM context
    
    Returns:
        Combined documentation content
    """
    sections = []
    
    # Core concepts
    concepts = load_concepts()
    if concepts:
        sections.append("=== Core Concepts ===")
        sections.append(concepts)
        sections.append("")
    
    # Task orchestration
    orchestration = load_task_orchestration_docs()
    if orchestration:
        sections.append("=== Task Orchestration Guide ===")
        sections.append(orchestration)
        sections.append("")
    
    # Task examples
    examples = load_task_examples()
    if examples:
        sections.append("=== Task Tree Examples ===")
        sections.append(examples)
        sections.append("")
    
    # Custom tasks
    custom_tasks = load_executor_docs()
    if custom_tasks:
        sections.append("=== Custom Tasks Guide ===")
        sections.append(custom_tasks)
        sections.append("")
    
    return "\n".join(sections)


__all__ = [
    "load_task_orchestration_docs",
    "load_task_examples",
    "load_executor_docs",
    "load_concepts",
    "load_all_docs",
]

