"""Tests for lightrag_baseline.py to ensure cross-machine reproducibility."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import module at the top level to avoid numpy reload issues
from amendaq.compare.lightrag_baseline import available


def test_no_hardcoded_macos_path():
    """Verify no hardcoded /Users/ path in lightrag_baseline.py."""
    source_file = Path(__file__).parent.parent / "src" / "amendaq" / "compare" / "lightrag_baseline.py"
    content = source_file.read_text(encoding="utf-8")
    
    # Check that no hardcoded macOS path exists
    assert "/Users/" not in content, "Found hardcoded /Users/ path in lightrag_baseline.py"
    assert 'LIGHTRAG_ROOT = Path("/Users/' not in content, "Found LIGHTRAG_ROOT hardcoded to /Users/ path"


def test_available_without_lightrag_or_env():
    """When lightrag is unavailable and AMENDAQ_LIGHTRAG_ROOT is unset, available() returns (False, msg) with actionable hint."""
    # Save original state
    original_env = os.environ.get("AMENDAQ_LIGHTRAG_ROOT")
    original_modules = {k: v for k, v in sys.modules.items() if k.startswith("lightrag")}
    
    # Remove AMENDAQ_LIGHTRAG_ROOT if set
    if "AMENDAQ_LIGHTRAG_ROOT" in os.environ:
        del os.environ["AMENDAQ_LIGHTRAG_ROOT"]
    
    # Temporarily hide lightrag modules
    for mod in list(sys.modules.keys()):
        if mod.startswith("lightrag"):
            del sys.modules[mod]
    
    try:
        # Patch __import__ to make lightrag imports fail
        import builtins
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == "lightrag" or name.startswith("lightrag."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)
        
        with patch.object(builtins, "__import__", mock_import):
            ok, msg = available()
            assert not ok, "available() should return False when lightrag is unavailable"
            assert "not installed" in msg.lower() or "import" in msg.lower(), \
                f"Error message should mention installation/import: {msg}"
            # Check for actionable hints
            assert any(hint in msg for hint in ["lightrag-hku", "AMENDAQ_LIGHTRAG_ROOT", "uv sync", "pip install"]), \
                f"Error message should provide actionable hint: {msg}"
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["AMENDAQ_LIGHTRAG_ROOT"] = original_env
        elif "AMENDAQ_LIGHTRAG_ROOT" in os.environ:
            del os.environ["AMENDAQ_LIGHTRAG_ROOT"]
        
        # Restore modules
        sys.modules.update(original_modules)


def test_available_with_nonexistent_env_path():
    """When AMENDAQ_LIGHTRAG_ROOT points to a non-existent path, available() returns (False, msg)."""
    original_env = os.environ.get("AMENDAQ_LIGHTRAG_ROOT")
    nonexistent_path = "/nonexistent/path/to/lightrag"
    os.environ["AMENDAQ_LIGHTRAG_ROOT"] = nonexistent_path
    
    try:
        ok, msg = available()
        assert not ok, "available() should return False for non-existent AMENDAQ_LIGHTRAG_ROOT"
        assert nonexistent_path in msg, f"Error message should mention the invalid path: {msg}"
        assert "does not exist" in msg.lower(), f"Error message should state the path doesn't exist: {msg}"
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["AMENDAQ_LIGHTRAG_ROOT"] = original_env
        elif "AMENDAQ_LIGHTRAG_ROOT" in os.environ:
            del os.environ["AMENDAQ_LIGHTRAG_ROOT"]


def test_available_with_valid_env_path():
    """When AMENDAQ_LIGHTRAG_ROOT points to a temp directory containing dummy lightrag/__init__.py, available() succeeds."""
    original_env = os.environ.get("AMENDAQ_LIGHTRAG_ROOT")
    original_path = sys.path.copy()
    original_modules = {k: v for k, v in sys.modules.items() if k.startswith("lightrag")}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy lightrag package
        lightrag_dir = Path(tmpdir) / "lightrag"
        lightrag_dir.mkdir()
        (lightrag_dir / "__init__.py").write_text("# Dummy lightrag module for testing\n")
        
        os.environ["AMENDAQ_LIGHTRAG_ROOT"] = tmpdir
        
        try:
            # Clear any cached lightrag import
            for mod in list(sys.modules.keys()):
                if mod.startswith("lightrag"):
                    del sys.modules[mod]
            
            ok, msg = available()
            assert ok, f"available() should return True when AMENDAQ_LIGHTRAG_ROOT is valid: {msg}"
            assert msg == "", f"Success message should be empty: {msg}"
            assert tmpdir in sys.path, "AMENDAQ_LIGHTRAG_ROOT should be added to sys.path"
        finally:
            # Clean up environment
            if original_env is not None:
                os.environ["AMENDAQ_LIGHTRAG_ROOT"] = original_env
            elif "AMENDAQ_LIGHTRAG_ROOT" in os.environ:
                del os.environ["AMENDAQ_LIGHTRAG_ROOT"]
            
            # Clean up sys.path - remove our tmpdir
            while tmpdir in sys.path:
                sys.path.remove(tmpdir)
            
            # Restore original lightrag modules
            for mod in list(sys.modules.keys()):
                if mod.startswith("lightrag"):
                    del sys.modules[mod]
            sys.modules.update(original_modules)


def test_available_with_empty_env_var():
    """When AMENDAQ_LIGHTRAG_ROOT is set but empty/whitespace, it should be ignored."""
    original_env = os.environ.get("AMENDAQ_LIGHTRAG_ROOT")
    os.environ["AMENDAQ_LIGHTRAG_ROOT"] = "   "  # Whitespace only
    
    try:
        # Should not try to validate empty path, should proceed to import attempt
        ok, msg = available()
        # If lightrag is installed via pip (from the extra), this will return True
        # Either way, should not mention the whitespace path in error
        if not ok:
            assert "   " not in msg, "Error message should not mention the whitespace path"
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["AMENDAQ_LIGHTRAG_ROOT"] = original_env
        elif "AMENDAQ_LIGHTRAG_ROOT" in os.environ:
            del os.environ["AMENDAQ_LIGHTRAG_ROOT"]


def test_available_idempotent():
    """Calling available() multiple times should be idempotent."""
    original_env = os.environ.get("AMENDAQ_LIGHTRAG_ROOT")
    original_path = sys.path.copy()
    original_modules = {k: v for k, v in sys.modules.items() if k.startswith("lightrag")}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy lightrag package
        lightrag_dir = Path(tmpdir) / "lightrag"
        lightrag_dir.mkdir()
        (lightrag_dir / "__init__.py").write_text("# Dummy lightrag module for testing\n")
        
        os.environ["AMENDAQ_LIGHTRAG_ROOT"] = tmpdir
        
        try:
            # Clear any cached lightrag import
            for mod in list(sys.modules.keys()):
                if mod.startswith("lightrag"):
                    del sys.modules[mod]
            
            # Call multiple times
            ok1, msg1 = available()
            ok2, msg2 = available()
            ok3, msg3 = available()
            
            assert ok1 == ok2 == ok3, "available() should return consistent results"
            assert msg1 == msg2 == msg3, "available() should return consistent messages"
            
            # sys.path should not accumulate duplicates
            path_count = sys.path.count(tmpdir)
            assert path_count == 1, f"AMENDAQ_LIGHTRAG_ROOT should appear in sys.path exactly once, found {path_count} times"
        finally:
            # Clean up environment
            if original_env is not None:
                os.environ["AMENDAQ_LIGHTRAG_ROOT"] = original_env
            elif "AMENDAQ_LIGHTRAG_ROOT" in os.environ:
                del os.environ["AMENDAQ_LIGHTRAG_ROOT"]
            
            # Clean up sys.path - remove our tmpdir
            while tmpdir in sys.path:
                sys.path.remove(tmpdir)
            
            # Restore original lightrag modules
            for mod in list(sys.modules.keys()):
                if mod.startswith("lightrag"):
                    del sys.modules[mod]
            sys.modules.update(original_modules)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
