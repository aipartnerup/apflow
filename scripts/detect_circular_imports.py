#!/usr/bin/env python3.12
"""
Circular import detector for apflow

This script detects circular imports and generates reports.
Usage: python scripts/detect_circular_imports.py
"""

import sys
import ast
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple


class ImportAnalyzer(ast.NodeVisitor):
    """Analyze imports in a Python file"""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.imports: Set[str] = set()
    
    def visit_Import(self, node: ast.Import) -> None:
        """Handle: import module"""
        for alias in node.names:
            self.imports.add(alias.name.split('.')[0])
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle: from module import name"""
        if node.module:
            self.imports.add(node.module.split('.')[0])


def get_module_imports(file_path: Path, base_package: str = "apflow") -> Set[str]:
    """Get all imports from a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        # Convert file path to module name
        rel_path = file_path.relative_to(Path("src"))
        module_parts = list(rel_path.parts)
        if module_parts[-1] == "__init__.py":
            module_parts = module_parts[:-1]
        else:
            module_parts[-1] = module_parts[-1][:-3]  # Remove .py
        module_name = ".".join(module_parts)
        
        analyzer = ImportAnalyzer(module_name)
        analyzer.visit(tree)
        
        # Only return imports within the base package
        return {imp for imp in analyzer.imports if imp == base_package}
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}", file=sys.stderr)
        return set()


def build_dependency_graph(src_dir: Path) -> Dict[str, Set[str]]:
    """Build dependency graph for all modules"""
    graph: Dict[str, Set[str]] = defaultdict(set)
    
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        # Convert to module name
        rel_path = py_file.relative_to(src_dir)
        module_parts = list(rel_path.parts)
        if module_parts[-1] == "__init__.py":
            module_parts = module_parts[:-1]
        else:
            module_parts[-1] = module_parts[-1][:-3]
        
        if not module_parts:  # Skip if empty
            continue
            
        module_name = ".".join(module_parts)
        imports = get_module_imports(py_file)
        
        graph[module_name] = imports
    
    return graph


def find_circular_imports(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Find circular imports using DFS"""
    def dfs(node: str, path: List[str], visited: Set[str]) -> List[List[str]]:
        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            # Filter out self-references (A -> A)
            if len(set(cycle)) <= 1:
                return []
            return [cycle]
        
        if node in visited or node not in graph:
            return []
        
        visited.add(node)
        cycles = []
        
        for neighbor in graph[node]:
            # Skip self-references
            if neighbor == node:
                continue
            cycles.extend(dfs(neighbor, path + [node], visited))
        
        return cycles
    
    all_cycles = []
    visited = set()
    
    for node in graph:
        if node not in visited:
            cycles = dfs(node, [], visited)
            all_cycles.extend(cycles)
    
    # Deduplicate cycles
    unique_cycles = []
    seen = set()
    for cycle in all_cycles:
        # Normalize cycle (rotate to start with smallest element)
        normalized = tuple(cycle[cycle.index(min(cycle)):] + cycle[:cycle.index(min(cycle))])
        if normalized not in seen:
            seen.add(normalized)
            unique_cycles.append(cycle)
    
    return unique_cycles


def main():
    """Main function"""
    print("=" * 80)
    print("Circular Import Detection for apflow")
    print("=" * 80)
    
    src_dir = Path("src")
    if not src_dir.exists():
        print("Error: src/ directory not found")
        sys.exit(1)
    
    print("\n1. Building dependency graph...")
    graph = build_dependency_graph(src_dir)
    print(f"   Found {len(graph)} modules")
    
    print("\n2. Detecting circular imports...")
    cycles = find_circular_imports(graph)
    
    if cycles:
        print(f"\n⚠️  Found {len(cycles)} circular import chains:\n")
        for i, cycle in enumerate(cycles, 1):
            print(f"Cycle {i}:")
            for j, module in enumerate(cycle):
                if j < len(cycle) - 1:
                    print(f"  {module}")
                    print(f"    ↓")
                else:
                    print(f"  {module} (back to {cycle[0]})")
            print()
        
        print("=" * 80)
        print("FAILED: Circular imports detected!")
        print("=" * 80)
        sys.exit(1)
    else:
        print("\n✅ No circular imports detected!")
        print("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()
