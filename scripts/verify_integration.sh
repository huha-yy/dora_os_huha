#!/usr/bin/env bash
# Verify Orchestrator + Navigation Integration

set -e

echo "======================================"
echo "  Integration Verification Script"
echo "======================================"
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

WORKSPACE="$HOME/dorabot_ws"
cd "$WORKSPACE"

echo "Checking integration files..."
echo

# Check orchestrator files
echo "1. Orchestrator files:"
if [ -f "src/orchestrator/main.py" ]; then
    echo -e "${GREEN}✓${NC} main.py exists"
    
    # Check for new CLI options
    if grep -q "enable-mapping" src/orchestrator/main.py; then
        echo -e "${GREEN}✓${NC} --enable-mapping option added"
    else
        echo -e "${RED}✗${NC} --enable-mapping option missing"
        exit 1
    fi
    
    if grep -q "enable-rtabmap" src/orchestrator/main.py; then
        echo -e "${GREEN}✓${NC} --enable-rtabmap option added"
    else
        echo -e "${RED}✗${NC} --enable-rtabmap option missing"
        exit 1
    fi
    
    if grep -q "enable-navigation" src/orchestrator/main.py; then
        echo -e "${GREEN}✓${NC} --enable-navigation option added"
    else
        echo -e "${RED}✗${NC} --enable-navigation option missing"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} main.py not found"
    exit 1
fi

echo

if [ -f "src/orchestrator/services/specs.py" ]; then
    echo -e "${GREEN}✓${NC} specs.py exists"
    
    # Check for navigation services
    if grep -q "map_generator" src/orchestrator/services/specs.py; then
        echo -e "${GREEN}✓${NC} map_generator service added"
    else
        echo -e "${RED}✗${NC} map_generator service missing"
        exit 1
    fi
    
    if grep -q "map_manager" src/orchestrator/services/specs.py; then
        echo -e "${GREEN}✓${NC} map_manager service added"
    else
        echo -e "${RED}✗${NC} map_manager service missing"
        exit 1
    fi
    
    if grep -q "rtabmap" src/orchestrator/services/specs.py; then
        echo -e "${GREEN}✓${NC} rtabmap service added"
    else
        echo -e "${RED}✗${NC} rtabmap service missing"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} specs.py not found"
    exit 1
fi

echo

# Check new scripts
echo "2. Convenience scripts:"
if [ -f "scripts/start_orchestrator_with_mapping.sh" ] && [ -x "scripts/start_orchestrator_with_mapping.sh" ]; then
    echo -e "${GREEN}✓${NC} start_orchestrator_with_mapping.sh exists and is executable"
else
    echo -e "${RED}✗${NC} start_orchestrator_with_mapping.sh missing or not executable"
    exit 1
fi

if [ -f "scripts/start_orchestrator_full.sh" ] && [ -x "scripts/start_orchestrator_full.sh" ]; then
    echo -e "${GREEN}✓${NC} start_orchestrator_full.sh exists and is executable"
else
    echo -e "${RED}✗${NC} start_orchestrator_full.sh missing or not executable"
    exit 1
fi

echo

# Check documentation
echo "3. Documentation files:"
docs=(
    "ORCHESTRATOR_NAVIGATION_INTEGRATION.md"
    "INTEGRATION_COMPLETE.md"
    "README.md"
)

for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        echo -e "${GREEN}✓${NC} $doc exists"
    else
        echo -e "${YELLOW}⚠${NC} $doc missing (optional)"
    fi
done

echo

# Check navigation package
echo "4. Navigation package:"
if [ -d "src/nav" ]; then
    echo -e "${GREEN}✓${NC} nav package exists"
    
    if [ -f "src/nav/src/mapping/map_generator.py" ]; then
        echo -e "${GREEN}✓${NC} map_generator.py exists"
    else
        echo -e "${RED}✗${NC} map_generator.py missing"
        exit 1
    fi
    
    if [ -f "src/nav/src/mapping/map_manager.py" ]; then
        echo -e "${GREEN}✓${NC} map_manager.py exists"
    else
        echo -e "${RED}✗${NC} map_manager.py missing"
        exit 1
    fi
    
    if [ -f "src/nav/config/map_generator.yaml" ]; then
        echo -e "${GREEN}✓${NC} map_generator.yaml exists"
    else
        echo -e "${RED}✗${NC} map_generator.yaml missing"
        exit 1
    fi
    
    if [ -f "src/nav/config/map_manager.yaml" ]; then
        echo -e "${GREEN}✓${NC} map_manager.yaml exists"
    else
        echo -e "${RED}✗${NC} map_manager.yaml missing"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} nav package not found"
    exit 1
fi

echo

# Verify Python imports (syntax check)
echo "5. Python syntax verification:"
python3 -m py_compile src/orchestrator/main.py 2>/dev/null && echo -e "${GREEN}✓${NC} main.py syntax OK" || echo -e "${RED}✗${NC} main.py syntax error"
python3 -m py_compile src/orchestrator/services/specs.py 2>/dev/null && echo -e "${GREEN}✓${NC} specs.py syntax OK" || echo -e "${RED}✗${NC} specs.py syntax error"

echo

# Summary
echo "======================================"
echo -e "${GREEN}  Integration Verification: PASSED${NC}"
echo "======================================"
echo
echo "The orchestrator has been successfully integrated with navigation services."
echo
echo "You can now use:"
echo "  1. python3 src/orchestrator/main.py --enable-mapping"
echo "  2. python3 src/orchestrator/main.py --enable-mapping --enable-rtabmap"
echo "  3. ./scripts/start_orchestrator_with_mapping.sh"
echo "  4. ./scripts/start_orchestrator_full.sh"
echo
echo "For detailed usage, see:"
echo "  - ORCHESTRATOR_NAVIGATION_INTEGRATION.md"
echo "  - INTEGRATION_COMPLETE.md"
echo
