# Configs Repository Quick Reference

## Directory Structure

```
configs/
├── orchestrator/    # Orchestrator configurations
├── nav/            # Navigation module configs  
├── examples/       # Example configurations
└── environments/   # Environment-specific (optional)
```

## Common Commands

### Setup Virtual Environment
```bash
cd ~/dorabot_ws
uv venv .venv
source .venv/bin/activate
uv pip install pyyaml click uvicorn fastapi
```

### Initialize Git
```bash
cd ~/dorabot_ws/configs
./init_git.sh
```

### Add Remote
```bash
git remote add origin <repo-url>
git push -u origin main
```

### Use Config (with scripts - venv auto-activated)
```bash
cd ~/dorabot_ws
./scripts/start_orchestrator.sh -c configs/orchestrator/config_slam.yaml
```

### Use Config (direct Python - activate venv first)
```bash
cd ~/dorabot_ws
source .venv/bin/activate
python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml
```

### List Configs
```bash
python3 src/orchestrator/main.py --list-configs
```

### Validate
```bash
./scripts/validate_configs.sh
```

### Create New Config
```bash
cd configs/orchestrator
cp config.yaml config_custom.yaml
nano config_custom.yaml
```

### Commit Changes
```bash
cd configs
git add .
git commit -m "Your message"
git push
```

### Pull Updates
```bash
cd configs
git pull
```

## Available Configs

| File | Use Case |
|------|----------|
| `orchestrator/config.yaml` | Basic operation |
| `orchestrator/config_mapping.yaml` | With mapping |
| `orchestrator/config_slam.yaml` | With SLAM |
| `orchestrator/config_full.yaml` | Full navigation |
| `examples/dev_environment.yaml` | Development |
| `examples/production.yaml` | Production |
| `examples/testing.yaml` | Testing |

## Quick Scripts

```bash
# Default
./scripts/start_orchestrator.sh

# With mapping
./scripts/start_orchestrator_with_mapping.sh

# With SLAM
./scripts/start_orchestrator_with_mapping.sh --slam

# Full suite
./scripts/start_orchestrator_full.sh
```

## Sensitive Files (Auto-Ignored)

- `**/secrets.yaml`
- `**/credentials.yaml`
- `**/*.secret.yaml`
- `*.local.yaml`
- `.env`

## Environment Variables

```bash
# For sensitive data
export API_KEY="your-key"
export DB_PASSWORD="your-password"

# In config
api_key: "${API_KEY}"
```

## Validation

```bash
# All configs
./scripts/validate_configs.sh

# Single config
python3 -c "import yaml; print(yaml.safe_load(open('configs/orchestrator/config.yaml')))"
```

## Team Workflow

```bash
# Pull latest
cd configs && git pull

# Make changes
nano orchestrator/config_slam.yaml

# Test
cd .. && python3 src/orchestrator/main.py -c configs/orchestrator/config_slam.yaml

# Commit
cd configs && git add . && git commit -m "Update" && git push
```

## Help

- Full guide: `configs/README.md`
- Management: `CONFIGS_REPOSITORY_GUIDE.md`
- Quick start: `QUICK_START_GUIDE.md`
