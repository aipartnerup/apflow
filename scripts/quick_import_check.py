#!/usr/bin/env python3.12
"""
Quick import performance check - runs before commit

This is a fast check suitable for pre-commit hooks.
"""

import sys
import time
from pathlib import Path


def check_cli_startup_time() -> bool:
    """Check if CLI startup is fast enough"""
    print("⏱️  Checking CLI startup time...", end=" ")
    
    start = time.time()
    try:
        import apflow.cli.main  # noqa: F401
    except Exception as e:
        print(f"\n❌ FAIL: Failed to import CLI: {e}")
        return False
    
    elapsed = time.time() - start
    threshold = 2.0  # More lenient for pre-commit
    
    if elapsed > threshold:
        print(f"\n❌ FAIL: {elapsed:.2f}s (threshold: {threshold}s)")
        print("   Run 'make check-performance' for details")
        return False
    
    print(f"✅ {elapsed:.2f}s")
    return True


def check_no_heavy_deps_at_startup() -> bool:
    """Ensure heavy dependencies aren't loaded at CLI startup"""
    print("🔍 Checking for heavy dependencies...", end=" ")
    
    heavy_deps = ['litellm', 'crewai', 'torch', 'transformers']
    loaded = [dep for dep in heavy_deps if dep in sys.modules]
    
    if loaded:
        print(f"\n❌ FAIL: Heavy dependencies loaded: {loaded}")
        print("   These should be lazy-loaded, not imported at module level")
        return False
    
    print("✅ Clean")
    return True


def main():
    """Run quick checks"""
    print("=" * 60)
    print("Quick Import Performance Check")
    print("=" * 60)
    
    # Clear any previous imports
    for key in list(sys.modules.keys()):
        if key.startswith('apflow'):
            del sys.modules[key]
    
    checks = [
        check_cli_startup_time,
        check_no_heavy_deps_at_startup,
    ]
    
    results = [check() for check in checks]
    
    print("=" * 60)
    if all(results):
        print("✅ All checks passed!")
        return 0
    else:
        print("❌ Some checks failed")
        print("\nFor detailed analysis, run:")
        print("  make check-imports")
        return 1


if __name__ == "__main__":
    sys.exit(main())
