"""Check registry status"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Import extensions to trigger registration
import apflow.extensions  # noqa: F401

from apflow.core.extensions.registry import get_registry

registry = get_registry()
executors = registry.list_executors()

print(f"Total executors: {len(executors)}")
for executor in executors:
    print(f"  - {executor.id}: {executor.name}")
