# Import Performance Tools Usage Guide

## 🎯 Goal

Prevent future issues with slow imports and circular dependencies.

## 📦 Installed Tools

### 1. Circular Import Detection
```bash
# Detect all circular imports
make check-circular

# Or run directly
python scripts/detect_circular_imports.py
```

**Output example**:
```
✅ No circular imports detected!
```

### 2. Heavy Import Detection
```bash
# Check all Python files
make check-heavy

# Or check specific files
python scripts/check_heavy_imports.py src/apflow/cli/commands/*.py
```

**Will warn about these heavyweight libraries**:
- `litellm` (2.4s)
- `crewai` (5.4s)
- `torch`, `transformers`, `tensorflow`, `langchain`

### 3. Import Performance Analysis
```bash
# Full performance report
make check-performance

# Or use Python's built-in tool directly
python -X importtime -c "import apflow.cli.main" 2>&1 | grep apflow
```

### 4. One-Click Check All
```bash
make check-imports
```

## 🔧 Pre-commit Hooks

Automatically configured checks that run before every commit:

```bash
# Install (first time only)
pip install pre-commit
pre-commit install

# Now every git commit will automatically check:
# ✓ Circular imports
# ✓ Heavyweight module-level imports
# ✓ Code formatting (ruff)
```

## 🚀 CI/CD Automatic Checks

Every PR will automatically verify:
- ✓ Circular import detection
- ✓ CLI startup time < 1.5 seconds
- ✓ No heavyweight dependencies loaded at CLI startup

See `.github/workflows/import-performance.yml`

## 📚 Development Guidelines

### ❌ Avoid These Mistakes

1. **Module-level heavyweight imports**
```python
# ❌ BAD: In CLI files
import litellm  # Slows down startup!

def list_tasks():
    ...  # Doesn't even use litellm
```

2. **Package `__init__.py` Eager Imports**
```python
# ❌ BAD: package/__init__.py
from .heavy_module import HeavyClass  # Loads everything immediately!
```

3. **Automatically importing all Extensions**
```python
# ❌ BAD
import apflow.extensions  # Loads all executors at module level
```

### ✅ Correct Practices

1. **Import on Demand**
```python
# ✅ GOOD
def execute_llm_task():
    import litellm  # Import only when needed
    ...
```

2. **Lazy Loading for Packages**
```python
# ✅ GOOD: package/__init__.py
def __getattr__(name):
    if name == "HeavyClass":
        from .heavy_module import HeavyClass
        return HeavyClass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

3. **Registry Lazy Loading**
```python
# ✅ GOOD
def get_registry():
    global _extensions_loaded
    if not _extensions_loaded:
        import apflow.extensions  # Load only on first access
    return _registry
```

## 🔍 Recommended Professional Tools

### tuna - Visualize Import Time
```bash
pip install tuna
python -X importtime -c "import apflow" 2> import.log
tuna import.log  # Opens browser with visual chart
```

### pydeps - Dependency Graph
```bash
pip install pydeps graphviz
pydeps apflow --max-bacon=2 -o deps.png
open deps.png
```

### import-profiler
```bash
pip install import-profiler
python -m import_profiler apflow.cli.main
```

## 📊 Performance Benchmarks

Current metrics:
- ✅ CLI startup: **1.3 seconds** (target < 1.5 seconds)
- ✅ `import apflow.core`: **0.8 seconds**
- ✅ `import apflow.cli.main`: **0.7 seconds**
- ✅ Zero circular imports

**Historical comparison**:
- Before optimization: 7.0 seconds 😱
- After optimization: 1.3 seconds ✨
- **Improvement: 5.4×** 🚀

## 🛠️ Daily Usage

### Before Developing a New Feature
```bash
# Check current baseline
time python -c "import apflow.cli.main"
```

### After Finishing Development
```bash
# Run all checks
make check-imports

# Or individual checks
make check-circular
make check-performance
make check-heavy
```

### Git Commit
```bash
git add .
git commit -m "feat: new feature"
# Pre-commit hooks run checks automatically
```

### When Encountering Warnings
Read `docs/development/import-performance.md` for detailed fix solutions.

## 🎓 Learning Resources

- [docs/development/import-performance.md](../development/import-performance.md) - Complete best practices guide
- [PEP 562 - Module __getattr__](https://www.python.org/dev/peps/pep-0562/)
- [Python Import System](https://docs.python.org/3/reference/import.html)

## 💡 Remember

> "If it takes more than 1 second to run `--help`, it's too slow."

Import performance directly affects user experience. Stay vigilant and avoid:
1. Module-level heavyweight imports
2. Eager loading of all modules
3. Circular dependencies

Use these tools to continuously monitor! 🎯