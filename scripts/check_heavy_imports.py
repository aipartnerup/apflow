#!/usr/bin/env python3.12
"""
Check for heavy imports at module level

This script detects imports of heavy dependencies (litellm, crewai, torch, etc.)
at module level, which can slow down CLI startup.

Usage: python scripts/check_heavy_imports.py [files...]
"""

import sys
import ast
from pathlib import Path
from typing import List, Tuple, Set


# Heavy dependencies that should be lazy-loaded
HEAVY_DEPENDENCIES = {
    "litellm": "LLM library (2.4s import time)",
    "crewai": "CrewAI framework (5.4s import time)",
    "torch": "PyTorch (slow import)",
    "transformers": "HuggingFace transformers (slow import)",
    "tensorflow": "TensorFlow (slow import)",
    "langchain": "LangChain (slow import)",
}

# Allowed locations for heavy imports (won't trigger warnings)
ALLOWED_HEAVY_IMPORT_PATTERNS = [
    "src/apflow/extensions/llm/llm_executor.py",  # LLM executor needs litellm
    "src/apflow/extensions/crewai/",  # CrewAI extension needs crewai
    "test_",  # Test files
    "conftest.py",  # Pytest config
]


class HeavyImportDetector(ast.NodeVisitor):
    """Detect heavy imports at module level"""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[Tuple[int, str, str]] = []
        self.in_function = 0
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track when we're inside a function"""
        self.in_function += 1
        self.generic_visit(node)
        self.in_function -= 1
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track when we're inside an async function"""
        self.in_function += 1
        self.generic_visit(node)
        self.in_function -= 1
    
    def visit_Import(self, node: ast.Import) -> None:
        """Check: import module"""
        if self.in_function == 0:  # Module level
            for alias in node.names:
                module_name = alias.name.split('.')[0]
                if module_name in HEAVY_DEPENDENCIES:
                    self.violations.append((
                        node.lineno,
                        module_name,
                        HEAVY_DEPENDENCIES[module_name]
                    ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check: from module import name"""
        if self.in_function == 0 and node.module:  # Module level
            module_name = node.module.split('.')[0]
            if module_name in HEAVY_DEPENDENCIES:
                self.violations.append((
                    node.lineno,
                    module_name,
                    HEAVY_DEPENDENCIES[module_name]
                ))
        self.generic_visit(node)


def is_allowed_location(file_path: str) -> bool:
    """Check if file is in allowed location for heavy imports"""
    for pattern in ALLOWED_HEAVY_IMPORT_PATTERNS:
        if pattern in file_path:
            return True
    return False


def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Check a single file for heavy imports"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        detector = HeavyImportDetector(str(file_path))
        detector.visit(tree)
        return detector.violations
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error checking {file_path}: {e}", file=sys.stderr)
        return []


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_heavy_imports.py [files...]")
        sys.exit(0)
    
    files = [Path(f) for f in sys.argv[1:] if f.endswith('.py')]
    
    if not files:
        print("No Python files to check")
        sys.exit(0)
    
    all_violations = []
    
    for file_path in files:
        if not file_path.exists():
            continue
        
        # Skip allowed locations
        if is_allowed_location(str(file_path)):
            continue
        
        violations = check_file(file_path)
        if violations:
            all_violations.append((file_path, violations))
    
    if all_violations:
        print("=" * 80)
        print("⚠️  Heavy Module-Level Imports Detected")
        print("=" * 80)
        print("\nThese imports slow down CLI startup. Consider lazy loading:\n")
        
        for file_path, violations in all_violations:
            print(f"📁 {file_path}")
            for lineno, module, description in violations:
                print(f"  Line {lineno}: import {module} ({description})")
                print(f"    💡 Fix: Move import inside function or use lazy loading")
            print()
        
        print("=" * 80)
        print("Recommendation: Use lazy imports for heavy dependencies")
        print("Example:")
        print("  def my_function():")
        print("      import litellm  # Import only when needed")
        print("      ...")
        print("=" * 80)
        sys.exit(1)
    else:
        print("✅ No heavy module-level imports detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
