.PHONY: help check-imports check-circular check-performance check-heavy test clean

help:
	@echo "Available commands:"
	@echo "  make check-imports     - Run all import checks"
	@echo "  make check-circular    - Detect circular imports"
	@echo "  make check-performance - Check import performance"
	@echo "  make check-heavy       - Check for heavy module-level imports"
	@echo "  make test              - Run tests"
	@echo "  make clean             - Clean cache files"

# Run all import checks
check-imports: check-circular check-performance check-heavy

# Detect circular imports
check-circular:
	@echo "Checking for circular imports..."
	@python scripts/detect_circular_imports.py

# Check import performance
check-performance:
	@echo "Checking import performance..."
	@bash scripts/check_import_performance.sh

# Check for heavy imports at module level
check-heavy:
	@echo "Checking for heavy module-level imports..."
	@find src -name "*.py" | xargs python scripts/check_heavy_imports.py

# Run tests
test:
	@pytest tests/ -v

# Clean cache files
clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cache cleaned!"
