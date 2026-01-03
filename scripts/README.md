# Import Performance Tools

This directory contains tools to detect and prevent import performance issues.

## Quick Start

```bash
# Run all checks
make check-imports

# Or individual checks
make check-circular      # Detect circular imports
make check-performance   # Check import time
make check-heavy        # Detect heavy module-level imports
```

## Tools

### 1. `detect_circular_imports.py`
Detects circular import dependencies using AST analysis.

### 2. `check_heavy_imports.py`
Detects heavy libraries (litellm, crewai, torch, etc.) imported at module level.

### 3. `check_import_performance.sh`
Analyzes import performance using Python's `-X importtime`.

### 4. `quick_import_check.py`
Fast check for pre-commit hooks (< 2s).

## Automation

- **Pre-commit hooks**: Auto-run on `git commit`
- **CI/CD**: Auto-run on PR
- **Documentation**: See `../docs/development/IMPORT_TOOLS_SUMMARY.md`

## Learn More

- [Complete Guide](../docs/development/import-tools-guide.md)
- [Best Practices](../docs/development/import-performance.md)
- [Contributing](../docs/development/contributing.md)
