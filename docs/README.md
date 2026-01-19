# Dorabot Documentation

User guides and reference documentation for the Dorabot navigation system.

## Quick Start

- **[QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)** ⭐ - **Start here!** Getting started with Dorabot
  - Installation and setup
  - Basic operations
  - Common tasks
  - Quick commands

## User Guides

### Mapping & Navigation
- **[MAPPING_QUICKSTART.md](MAPPING_QUICKSTART.md)** - How to create and save maps
  - SLAM mapping with RTAB-Map
  - Custom map generation
  - Map management

### Configuration
- **[CONFIG_BASED_ORCHESTRATOR.md](CONFIG_BASED_ORCHESTRATOR.md)** - Configuration system guide
  - YAML configuration files
  - Preset configurations
  - Creating custom configs
  - Configuration reference

- **[CONFIGS_REPOSITORY_GUIDE.md](CONFIGS_REPOSITORY_GUIDE.md)** - Managing configurations
  - Configs as git repository
  - Version control
  - Environment-specific configs
  - Team workflows

### Integration
- **[ORCHESTRATOR_NAVIGATION_INTEGRATION.md](ORCHESTRATOR_NAVIGATION_INTEGRATION.md)** - Service integration
  - How services work together
  - Service management
  - Troubleshooting

### Version Control
- **[WORKSPACE_GIT_GUIDE.md](WORKSPACE_GIT_GUIDE.md)** - Git repository management
  - Workspace as git repository
  - Submodules for src/ directories
  - Daily workflow
  - Best practices

## Module Documentation

### Navigation Package
- **[../src/nav/README.md](../src/nav/README.md)** - Navigation package overview
- **[../src/nav/src/mapping/README.md](../src/nav/src/mapping/README.md)** - Mapping API reference

### Configuration Files
- **[../configs/README.md](../configs/README.md)** - Configuration repository documentation

## Development

### Change Logs
- **[../change_logs/README.md](../change_logs/README.md)** - Development history and technical summaries

## Quick Reference

```bash
# Start basic operation
./scripts/start_orchestrator.sh

# Start with mapping
./scripts/start_orchestrator_with_mapping.sh --slam

# Save a map
ros2 service call /map_manager/save_map std_srvs/srv/Trigger

# View in RViz
rviz2 -d src/nav/config/mapping.rviz
```

## Documentation Structure

```
docs/
├── README.md                              # This file
├── QUICK_START_GUIDE.md                   # Getting started ⭐
├── MAPPING_QUICKSTART.md                  # Mapping guide
├── CONFIG_BASED_ORCHESTRATOR.md           # Config system
├── CONFIGS_REPOSITORY_GUIDE.md            # Config management
└── ORCHESTRATOR_NAVIGATION_INTEGRATION.md # Integration guide
```

## By Topic

### I want to...

| Goal | See |
|------|-----|
| Get started quickly | [QUICK_START_GUIDE.md](QUICK_START_GUIDE.md) |
| Create a map | [MAPPING_QUICKSTART.md](MAPPING_QUICKSTART.md) |
| Understand configs | [CONFIG_BASED_ORCHESTRATOR.md](CONFIG_BASED_ORCHESTRATOR.md) |
| Manage config repo | [CONFIGS_REPOSITORY_GUIDE.md](CONFIGS_REPOSITORY_GUIDE.md) |
| Understand integration | [ORCHESTRATOR_NAVIGATION_INTEGRATION.md](ORCHESTRATOR_NAVIGATION_INTEGRATION.md) |
| API reference | [../src/nav/src/mapping/README.md](../src/nav/src/mapping/README.md) |
| Change history | [../change_logs/README.md](../change_logs/README.md) |

## Help & Support

- Check the relevant guide above
- See examples in `../configs/examples/`
- Review change logs for implementation details
- Run validation: `./scripts/validate_configs.sh`

## Contributing

When adding new features, please:
1. Update relevant documentation
2. Add examples if applicable
3. Create changelog entry in `../change_logs/`
4. Update this index if needed
