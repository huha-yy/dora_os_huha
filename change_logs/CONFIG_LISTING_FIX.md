# Configuration Listing Fix

**Date:** January 18, 2026  
**Issue:** `--list-configs` option not displaying available configuration files  
**Status:** ✅ Fixed

---

## Problem

When running the orchestrator with the `--list-configs` flag, no configuration files were displayed:

```bash
(.venv) frank@daneenon-tp:~/dorabot_ws$ python src/orchestrator/main.py --list-configs

Available configuration files:

Use with: python src/orchestrator/main.py -c src/orchestrator/<config_file>
```

The configuration files existed in `configs/orchestrator/` but were not being found by the `list_available_configs()` function.

---

## Root Cause

The issue was in `src/orchestrator/config_loader.py` in the `list_available_configs()` function. 

**Path Resolution Problem:**
- When `main.py` manipulates `sys.path` by adding the `src` directory, it affects how Python resolves the `__file__` attribute in imported modules
- The original code used `Path(__file__).parent.parent.parent` to navigate from `config_loader.py` up to the workspace root
- Without using `.resolve()`, the path remained relative and didn't resolve correctly in all execution contexts

**Original problematic code:**
```python
def list_available_configs() -> list[str]:
    """List all available configuration files."""
    # Look in configs directory first
    workspace_root = Path(__file__).parent.parent.parent  # ❌ Not resolved
    configs_dir = workspace_root / "configs" / "orchestrator"
    
    if configs_dir.exists():  # ❌ Returns False due to unresolved path
        configs = list(configs_dir.glob("config*.yaml"))
        return [f"configs/orchestrator/{c.name}" for c in sorted(configs)]
    
    # Fall back to old location
    script_dir = Path(__file__).parent
    configs = list(script_dir.glob("config*.yaml"))
    return [f"src/orchestrator/{c.name}" for c in sorted(configs)]
```

---

## Solution

### 1. Fixed Path Resolution in `config_loader.py`

**Updated `list_available_configs()` function:**
```python
def list_available_configs() -> list[str]:
    """List all available configuration files."""
    # Get absolute path and work from there
    script_dir = Path(__file__).parent.resolve()  # ✅ Resolve to absolute path
    
    # Look in configs directory first (new location)
    # Navigate up from src/orchestrator to workspace root
    workspace_root = script_dir.parent.parent
    configs_dir = workspace_root / "configs" / "orchestrator"
    
    if configs_dir.exists() and configs_dir.is_dir():  # ✅ Check it's a directory
        configs = list(configs_dir.glob("config*.yaml"))
        if configs:  # ✅ Only return if we found configs
            return [f"configs/orchestrator/{c.name}" for c in sorted(configs)]
    
    # Fall back to old location
    configs = list(script_dir.glob("config*.yaml"))
    return [f"src/orchestrator/{c.name}" for c in sorted(configs)]
```

**Key improvements:**
- ✅ Added `.resolve()` to get absolute path
- ✅ Added `is_dir()` check to ensure the path is a directory
- ✅ Added check to only return if configs were found

**Updated `get_default_config_path()` function:**
```python
def get_default_config_path() -> str:
    """Get the default configuration file path."""
    # Get absolute path and work from there
    script_dir = Path(__file__).parent.resolve()  # ✅ Resolve to absolute path
    
    # Try new location: configs/orchestrator/config.yaml
    # Navigate up from src/orchestrator to workspace root
    workspace_root = script_dir.parent.parent
    new_config = workspace_root / "configs" / "orchestrator" / "config.yaml"
    
    if new_config.exists():
        return str(new_config)
    
    # Fall back to old location for backward compatibility
    old_config = script_dir / "config.yaml"
    
    if old_config.exists():
        return str(old_config)
    
    raise FileNotFoundError(
        "No default configuration file found. "
        "Expected: configs/orchestrator/config.yaml or src/orchestrator/config.yaml"
    )
```

### 2. Updated Usage Instructions in `main.py`

**Before:**
```python
print("\nUse with: python src/orchestrator/main.py -c src/orchestrator/<config_file>")
```

**After:**
```python
print("\nUse with: python src/orchestrator/main.py -c <config_file>")
print("Example: python src/orchestrator/main.py -c configs/orchestrator/config_full.yaml")
```

### 3. Updated Documentation and Help Text

Updated all references to configuration paths:
- Docstring examples in `main.py`
- `--config` option help text
- All paths now correctly reference `configs/orchestrator/` instead of `src/orchestrator/`

---

## Verification

After the fix:

```bash
(.venv) frank@daneenon-tp:~/dorabot_ws$ python src/orchestrator/main.py --list-configs

Available configuration files:
  - configs/orchestrator/config.yaml
  - configs/orchestrator/config_full.yaml
  - configs/orchestrator/config_mapping.yaml
  - configs/orchestrator/config_slam.yaml

Use with: python src/orchestrator/main.py -c <config_file>
Example: python src/orchestrator/main.py -c configs/orchestrator/config_full.yaml
```

✅ All configuration files are now correctly listed!

---

## Files Modified

1. **`src/orchestrator/config_loader.py`**
   - Fixed `list_available_configs()` with `.resolve()` and additional checks
   - Fixed `get_default_config_path()` with `.resolve()`

2. **`src/orchestrator/main.py`**
   - Updated usage message in `--list-configs` output
   - Updated docstring examples with correct paths
   - Updated `--config` option help text

---

## Technical Notes

### Why `.resolve()` Matters

The `.resolve()` method:
- Converts relative paths to absolute paths
- Resolves symlinks
- Makes path operations consistent across different execution contexts
- Essential when `sys.path` is manipulated before imports

### Execution Context Differences

**Running from workspace root:**
```bash
python src/orchestrator/main.py  # sys.path manipulation affects imports
```

**Direct testing:**
```bash
python3 -c "from orchestrator.config_loader import list_available_configs"  # Different context
```

The fix ensures consistent behavior in both contexts.

---

## Best Practices Applied

1. ✅ **Always resolve paths** when navigating the filesystem
2. ✅ **Check directory existence** before listing files
3. ✅ **Provide clear usage examples** in help text
4. ✅ **Keep documentation in sync** with code changes
5. ✅ **Test in actual execution context** not just isolated tests

---

## Related Files

- `src/orchestrator/config_loader.py` - Configuration loading utilities
- `src/orchestrator/main.py` - Orchestrator entry point
- `configs/orchestrator/*.yaml` - Configuration files
- `change_logs/CONFIG_REFACTOR_COMPLETE.md` - Original config refactor
- `change_logs/CONFIGS_REPO_COMPLETE.md` - Configs repository setup

---

## Summary

This fix ensures that the orchestrator's `--list-configs` option correctly discovers and displays all available configuration files, regardless of how the script is invoked. The key was properly resolving absolute paths when working with dynamically imported modules that manipulate `sys.path`.
