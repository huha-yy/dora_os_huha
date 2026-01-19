#!/usr/bin/env bash
# Validate orchestrator configuration files

set -e

WORKSPACE="$HOME/dorabot_ws"
cd "$WORKSPACE"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "  Configuration Validation"
echo "======================================"
echo

CONFIG_DIR="configs/orchestrator"
CONFIGS=(
    "config.yaml"
    "config_mapping.yaml"
    "config_slam.yaml"
    "config_full.yaml"
)

errors=0

# Check if config_loader.py exists
if [ ! -f "src/orchestrator/config_loader.py" ]; then
    echo -e "${RED}✗${NC} config_loader.py not found"
    exit 1
fi
echo -e "${GREEN}✓${NC} config_loader.py exists"

# Validate each config file
for config in "${CONFIGS[@]}"; do
    config_path="$CONFIG_DIR/$config"
    
    if [ ! -f "$config_path" ]; then
        echo -e "${RED}✗${NC} $config not found"
        ((errors++))
        continue
    fi
    
    # Check YAML syntax
    if python3 -c "import yaml; yaml.safe_load(open('$config_path'))" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $config - valid YAML syntax"
    else
        echo -e "${RED}✗${NC} $config - invalid YAML syntax"
        ((errors++))
        continue
    fi
    
    # Check required keys
    python3 << EOF
import yaml
import sys

required_keys = ['language', 'orchestrator_port', 'venv_path', 'services']
required_service_keys = ['ai_agent', 'realsense_camera', 'perception']

try:
    with open('$config_path') as f:
        config = yaml.safe_load(f)
    
    # Check top-level keys
    for key in required_keys:
        if key not in config:
            print(f"Missing required key: {key}")
            sys.exit(1)
    
    # Check services
    services = config.get('services', {})
    for key in required_service_keys:
        if key not in services:
            print(f"Missing required service key: {key}")
            sys.exit(1)
    
    sys.exit(0)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF
    
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} Required keys present"
    else
        echo -e "  ${RED}✗${NC} Missing required keys"
        ((errors++))
    fi
done

echo

# Test config loading
echo "Testing config loader module:"
if python3 -c "from orchestrator.config_loader import load_config, list_available_configs; print(f'Found {len(list_available_configs())} configs')" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Config loader module works"
else
    echo -e "${RED}✗${NC} Config loader module failed"
    echo "Note: This may be due to missing dependencies (pyyaml)"
    ((errors++))
fi

echo

# Summary
if [ $errors -eq 0 ]; then
    echo -e "${GREEN}======================================"
    echo "  All Validations Passed ✓"
    echo "======================================${NC}"
    echo
    echo "Available configurations:"
    for config in "${CONFIGS[@]}"; do
        echo "  - $config"
    done
    echo
    echo "Test with:"
    echo "  python3 src/orchestrator/main.py --list-configs"
    echo "  python3 src/orchestrator/main.py -c src/orchestrator/config.yaml"
else
    echo -e "${RED}======================================"
    echo "  Validation Failed"
    echo "  Errors: $errors"
    echo "======================================${NC}"
    exit 1
fi
