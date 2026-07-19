#!/usr/bin/env python
"""
Test script for working_directory_guard_ru.py
"""
import os
import sys
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path.cwd()))

from modules.working_directory_guard_ru import check_working_directory, dispatch

def test_guard_in_correct_dir():
    """Test the guard when running in the correct directory."""
    print("=" * 70)
    print("TEST 1: Working Directory Guard - In Correct Directory")
    print("=" * 70)
    
    result = check_working_directory()
    print(f"Result: {result}")
    print(f"Status (ok): {result.get('ok')}")
    print(f"Message: {result.get('message')}")
    print(f"Current directory: {result.get('current_directory')}")
    print(f"Project root: {result.get('project_root')}")
    
    assert result.get('ok') == True, "Should pass in correct directory"
    assert "Команда запущена из корня проекта LocalAgent" in result.get('message', '')
    
    print("✓ Test 1 PASSED")
    print()

def test_guard_dispatch():
    """Test the dispatch function."""
    print("=" * 70)
    print("TEST 2: Working Directory Guard - Dispatch Command")
    print("=" * 70)
    
    # Test with Russian command
    result = dispatch("проверь рабочую папку")
    print(f"Result for 'проверь рабочую папку': {result}")
    print(f"Mode: {result.get('mode')}")
    
    assert result.get('mode') == 'command', "Should return command mode"
    assert result.get('result', {}).get('ok') == True, "Should be OK"
    
    print("✓ Test 2 PASSED")
    print()

def test_guard_indicators():
    """Test the individual project root indicators."""
    print("=" * 70)
    print("TEST 3: Working Directory Guard - Project Root Indicators")
    print("=" * 70)
    
    from modules.working_directory_guard_ru import get_project_root_indicators
    
    indicators = get_project_root_indicators()
    print(f"Indicators: {indicators}")
    
    # All should be True in correct directory
    assert indicators["localcomet_control_panel_exists"] == True
    assert indicators["modules_directory_exists"] == True
    assert indicators["agents_md_exists"] == True
    
    print("✓ Test 3 PASSED")
    print()

def test_status_function():
    """Test the get_status function."""
    print("=" * 70)
    print("TEST 4: Working Directory Guard - Status Function")
    print("=" * 70)
    
    from modules.working_directory_guard_ru import get_status
    
    status = get_status()
    print(f"Status: {status}")
    
    assert status.get("module") == "working_directory_guard_ru"
    assert status.get("version") == "v6.65b"
    assert status.get("status") == "ready"
    
    print("✓ Test 4 PASSED")
    print()

if __name__ == "__main__":
    print("Testing Working Directory Guard v6.65b")
    print(f"Current directory: {os.getcwd()}")
    print()
    
    test_guard_in_correct_dir()
    test_guard_dispatch()
    test_guard_indicators()
    test_status_function()
    
    print("=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)
