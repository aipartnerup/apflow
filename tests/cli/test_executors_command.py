"""
Test CLI command for listing available executors
"""

import os
import subprocess


def test_cli_executors_list_basic():
    """Test 'apflow executors list' CLI command works"""
    env = os.environ.copy()
    
    result = subprocess.run(
        ["apflow", "executors", "list"],
        capture_output=True,
        text=True,
        env=env,
    )
    
    # Verify command succeeded
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    
    output = result.stdout
    
    # Verify output contains expected text
    assert "Available Executors" in output
    
    print("\n✅ CLI Test (Basic):")
    print(output[:300])


def test_cli_executors_list_with_restrictions():
    """Test 'apflow executors list' CLI command with APFLOW_EXTENSIONS=stdio"""
    # Run CLI command with restrictions
    env = os.environ.copy()
    env["APFLOW_EXTENSIONS"] = "stdio"
    
    result = subprocess.run(
        ["apflow", "executors", "list"],
        capture_output=True,
        text=True,
        env=env,
    )
    
    # Verify command succeeded
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    
    output = result.stdout
    
    # Verify output contains expected text
    assert "Available Executors" in output
    assert "Access restricted" in output
    
    print("\n✅ CLI Test (With Restrictions - stdio only):")
    print(output)


def test_cli_executors_list_json_format():
    """Test 'apflow executors list --format json' CLI command"""
    import json
    
    env = os.environ.copy()
    env["APFLOW_EXTENSIONS"] = "stdio,http"
    
    result = subprocess.run(
        ["apflow", "executors", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
    )
    
    # Verify command succeeded
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    
    # Extract JSON from output (robust to extra text)
    import re
    match = re.search(r'({.*})', result.stdout, re.DOTALL)
    assert match, f"No JSON found in output: {result.stdout}"
    data = json.loads(match.group(1))
    
    # Verify structure
    assert "executors" in data
    assert "count" in data
    assert "restricted" in data
    assert data["restricted"] is True
    
    print("\n✅ CLI Test (JSON Format):")
    print(f"   Total executors: {data['count']}")
    print(f"   Restricted: {data['restricted']}")


def test_cli_executors_list_ids_format():
    """Test 'apflow executors list --format ids' CLI command"""
    env = os.environ.copy()
    env["APFLOW_EXTENSIONS"] = "stdio"
    
    result = subprocess.run(
        ["apflow", "executors", "list", "--format", "ids"],
        capture_output=True,
        text=True,
        env=env,
    )
    
    # Verify command succeeded
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    
    output = result.stdout.strip()
    
    # Should not contain table headers or descriptions
    assert "Available Executors" not in output
    assert "Description" not in output
    
    print("\n✅ CLI Test (IDs Format):")
    print(f"Output length: {len(output)} chars")


def test_cli_executors_default_command():
    """Test 'apflow executors' (default to list)"""
    env = os.environ.copy()
    
    result = subprocess.run(
        ["apflow", "executors"],
        capture_output=True,
        text=True,
        env=env,
    )
    
    # Verify command succeeded
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    
    output = result.stdout
    
    # Should behave same as 'list' command
    assert "Available Executors" in output
    
    print("\n✅ CLI Test (Default Command):")
    print("   Command 'apflow executors' defaults to 'list' ✓")
