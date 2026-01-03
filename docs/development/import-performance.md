# Import Performance Best Practices

## Background

Python's import mechanism can cause performance issues:
- **Circular imports**: Module A imports B, and B imports A, causing modules to be loaded multiple times.
- **Eager imports**: Importing all dependencies at the module level, even if they are not needed.
- **Heavyweight dependencies**: Importing large libraries (e.g., litellm takes 2.4s, crewai takes 5.4s) slows down startup.

## Best Practices

### 1. Avoid Heavyweight Imports at Module Level

❌ **Bad Practice**:
```python
# cli/commands/tasks.py
import litellm  # 2.4 seconds! Even if LLM functionality is not needed
from crewai import Agent  # 5.4 seconds!

def list_tasks():
    # Only queries the database, no need for these libraries
    ...
```

✅ **Good Practice**:
```python
# cli/commands/tasks.py

def run_llm_task():
    # Import only when needed
    import litellm
    ...
```

### 2. Use Lazy Loading (`__getattr__`)

❌ **Bad Practice**:
```python
# package/__init__.py
from .heavy_module import HeavyClass  # Loaded immediately
from .another_heavy import AnotherClass
```

✅ **Good Practice**:
```python
# package/__init__.py
__all__ = ["HeavyClass", "AnotherClass"]

def __getattr__(name):
    """Load on demand"""
    if name == "HeavyClass":
        from .heavy_module import HeavyClass
        return HeavyClass
    elif name == "AnotherClass":
        from .another_heavy import AnotherClass
        return AnotherClass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### 3. Avoid Circular Imports

❌ **Bad Practice**:
```python
# module_a.py
from module_b import func_b

def func_a():
    return func_b()

# module_b.py
from module_a import func_a  # Circular!

def func_b():
    return func_a()
```

✅ **Good Practices**:
```python
# Option 1: Refactor code, extract shared logic into a third module
# shared.py
def shared_logic():
    ...

# module_a.py
from shared import shared_logic

# module_b.py
from shared import shared_logic

# Option 2: Use local imports
def func_b():
    from module_a import func_a  # Import inside the function
    return func_a()
```

### 4. Extension Registry Lazy Loading

For plugin systems, automatically load on first access:

```python
_registry = ExtensionRegistry()
_extensions_loaded = False

def get_registry():
    global _extensions_loaded
    if not _extensions_loaded:
        _extensions_loaded = True
        import apflow.extensions  # Automatically register all plugins
    return _registry
```

## Tools and Checks

### Local Checks

```bash
# Detect circular imports
make check-circular

# Check import performance
make check-performance

# Check heavyweight module imports
make check-heavy

# Run all checks
make check-imports
```

### Pre-commit Hooks

Install pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```

Automatically checks on every commit:
- Circular import detection
- Heavyweight module-level import detection

### CI/CD

GitHub Actions automatically checks on every PR:
- Circular imports
- CLI startup time (must be < 1.5 seconds)
- Heavyweight dependencies should not be loaded during CLI startup

### Python Built-in Tools

Use `-X importtime` to analyze import times:
```bash
python -X importtime -c "import apflow.cli.main" 2>&1 | grep apflow
```

### Professional Tools

1. **tuna** - Visualize import times
   ```bash
   pip install tuna
   python -X importtime -c "import apflow" 2> import.log
   tuna import.log
   ```

2. **pydeps** - Visualize dependency graphs
   ```bash
   pip install pydeps
   pydeps apflow --max-bacon=2 -o deps.png
   ```

3. **import-profiler**
   ```bash
   pip install import-profiler
   python -m import_profiler apflow.cli.main
   ```

## Performance Goals

- ✅ CLI startup: < 1.5 seconds
- ✅ Package import: < 0.5 seconds
- ✅ Zero circular imports
- ✅ Heavyweight dependencies loaded only when needed

## Monitoring

Run after every code change:
```bash
# Quick check
time python -c "import apflow.cli.main"

# Detailed analysis
python scripts/analyze_import_performance.py
```

## Common Mistakes and Fixes

### Mistake 1: Module-Level Import of TaskExecutor

```python
# ❌ Loads all extensions
from apflow.core.execution.task_executor import TaskExecutor

def some_query_function():
    # Only queries the database, no need for TaskExecutor
    ...
```

**Fix**: Move it to where it's actually needed
```python
def execute_task_function():
    from apflow.core.execution.task_executor import TaskExecutor
    executor = TaskExecutor()
    ...
```

### Mistake 2: Package `__init__.py` Eagerly Imports All Submodules

```python
# ❌ package/__init__.py
from .submodule_a import *
from .submodule_b import *
from .submodule_c import *  # Loads everything!
```

**Fix**: Use `__getattr__`
```python
# ✅ package/__init__.py
def __getattr__(name):
    if name == "ClassA":
        from .submodule_a import ClassA
        return ClassA
    ...
```

### Mistake 3: Extensions Auto-Registered on Import

```python
# ❌ task_executor.py
import apflow.extensions  # Loads all extensions on startup
```

**Fix**: Delay until actually needed
```python
# ✅ registry.py
def get_registry():
    if not _extensions_loaded:
        import apflow.extensions  # Load only on first access
    return _registry
```

## Case Study: apflow Optimization Journey

**Problem**: CLI startup took 7 seconds  
**Causes**:
1. `apflow.core.__init__.py` eagerly imported all modules
2. `task_executor.py` automatically imported `apflow.extensions`
3. Extensions automatically imported litellm (2.4s) and crewai (5.4s)

**Fixes**:
1. Changed all package `__init__.py` files to lazy loading
2. Removed auto-import of TaskExecutor
3. Load extensions in Registry only on first access
4. Import TaskExecutor on demand in CLI commands

## Reference Resources

- [PEP 562 - Module __getattr__](https://www.python.org/dev/peps/pep-0562/)
- [Python Import System](https://docs.python.org/3/reference/import.html)
- [Circular Imports in Python](https://realpython.com/python-circular-imports/)