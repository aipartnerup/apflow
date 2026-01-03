#!/bin/bash
# Check import performance using Python's built-in -X importtime

set -e

echo "=================================================="
echo "Import Performance Check"
echo "=================================================="

# Test 1: CLI import time
echo -e "\n1. CLI Import Time:"
python3.12 -X importtime -c "import apflow.cli.main" 2>&1 | grep -E "apflow\.(cli|core|extensions)" | tail -20

# Test 2: Core import time
echo -e "\n2. Core Import Time:"
python3.12 -X importtime -c "import apflow.core" 2>&1 | grep -E "apflow\.core" | tail -20

# Test 3: Check if litellm is imported at CLI startup
echo -e "\n3. Checking for heavy dependencies at CLI startup:"
python3.12 -c "
import sys
import apflow.cli.main

heavy_deps = ['litellm', 'crewai', 'torch', 'transformers']
loaded = [dep for dep in heavy_deps if dep in sys.modules]

if loaded:
    print(f'⚠️  WARNING: Heavy dependencies loaded: {loaded}')
    exit(1)
else:
    print('✅ No heavy dependencies at CLI startup')
"

echo -e "\n=================================================="
echo "Performance check complete!"
echo "=================================================="
