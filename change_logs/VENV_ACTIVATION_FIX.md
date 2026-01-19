# Virtual Environment Activation Fix

## Problem

Previously, the virtual environment activation was attempted inside the Python script (`main.py`), which is too late - all imports have already been executed by that point.

## Solution

Virtual environment activation is now handled in bash scripts **before** Python runs.

## Changes Made

### 1. Removed from Python Script

**Removed from `src/orchestrator/main.py`:**
- `activate_venv()` function
- All venv activation logic
- `venv_path` from config summary

### 2. Added to Bash Scripts

**Updated all scripts to activate venv first:**
- `scripts/start_orchestrator.sh`
- `scripts/start_orchestrator_with_mapping.sh`
- `scripts/start_orchestrator_full.sh`

Each script now includes:
```bash
# Activate virtual environment if it exists
VENV_PATH="$ROOT/.venv"
if [ -d "$VENV_PATH" ]; then
    echo "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
else
    echo "Warning: Virtual environment not found at $VENV_PATH"
    echo "Create it with: cd $ROOT && uv venv .venv"
fi
```

### 3. Updated Configuration Files

**Removed `venv_path` parameter from all configs:**
- `configs/orchestrator/config.yaml`
- `configs/orchestrator/config_mapping.yaml`
- `configs/orchestrator/config_slam.yaml`
- `configs/orchestrator/config_full.yaml`
- `configs/examples/*.yaml`

**Updated `src/orchestrator/config_loader.py`:**
- Removed `venv_path` from `OrchestratorConfig` dataclass
- Removed venv_path loading logic

## Usage

### Automatic (Recommended)

Use the provided scripts which handle venv activation:

```bash
# Scripts automatically activate venv
./scripts/start_orchestrator.sh
./scripts/start_orchestrator_with_mapping.sh --slam
./scripts/start_orchestrator_full.sh
```

### Manual

If running Python directly, activate venv first:

```bash
# 1. Activate venv
source ~/dorabot_ws/.venv/bin/activate

# 2. Then run Python
python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml
```

## Creating Virtual Environment

If you don't have the virtual environment yet:

```bash
cd ~/dorabot_ws

# Create venv with uv
uv venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
uv pip install pyyaml click uvicorn fastapi rclpy numpy opencv-python

# Or from requirements file if you have one
uv pip install -r requirements.txt
```

## Verification

Check if venv is active:

```bash
# Should show path to .venv
which python3

# Should show path to .venv
echo $VIRTUAL_ENV

# Or run orchestrator - it will display venv info
python3 src/orchestrator/main.py
```

Output will include:
```
Virtual Environment: /home/frank/dorabot_ws/.venv
```

## Benefits of This Approach

✅ **Correct Order** - Venv activated before Python imports  
✅ **Clean Separation** - Shell handles environment, Python handles logic  
✅ **Standard Practice** - Follows Python best practices  
✅ **No Import Errors** - All dependencies available from start  
✅ **Simpler Config** - No venv_path in config files  

## Troubleshooting

### "No module named 'yaml'" or similar import errors

```bash
# Make sure venv is activated
source ~/dorabot_ws/.venv/bin/activate

# Install missing dependencies
uv pip install pyyaml

# Or install all dependencies
uv pip install -r requirements.txt
```

### Scripts don't activate venv

```bash
# Check if venv exists
ls -ld ~/dorabot_ws/.venv

# If not, create it
cd ~/dorabot_ws
uv venv .venv

# Install dependencies
source .venv/bin/activate
uv pip install pyyaml click uvicorn fastapi
```

### Running without scripts

```bash
# Always activate venv first
source ~/dorabot_ws/.venv/bin/activate

# Then run Python
python3 src/orchestrator/main.py
```

## Migration Notes

If you have existing configs with `venv_path`, they still work (the parameter is simply ignored). But you should:

1. Remove `venv_path:` line from your custom configs
2. Ensure venv is activated in your scripts/commands
3. Update any documentation referencing venv_path

## Summary

- **Before**: Python script tried to activate venv (too late!)
- **After**: Bash scripts activate venv before running Python (correct!)
- **Result**: Clean separation of concerns and proper dependency loading

---

**Fix Date**: January 18, 2026  
**Issue**: Virtual environment activation happened too late  
**Solution**: Move activation to bash scripts  
**Status**: ✅ Fixed and tested
