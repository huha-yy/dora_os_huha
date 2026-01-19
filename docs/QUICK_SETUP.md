# Dorabot Workspace - Quick Setup

## Initialize Git Repository

Run the initialization script:

```bash
cd ~/dorabot_ws
./init_workspace_git.sh
```

This will:
1. ✅ Initialize git repository
2. ✅ Create .gitignore
3. ✅ Create initial commit
4. ✅ Show next steps

## Add Remote Repository

```bash
git remote add origin git@github.com:your-org/dorabot-workspace.git
git branch -M main
git push -u origin main
```

## Setup Submodules (Optional but Recommended)

Your source directories can be separate git repositories:

```bash
# Example: Add nav module as submodule
./add_submodule.sh git@github.com:your-org/dorabot-nav.git src/nav

# Example: Add configs as submodule
./add_submodule.sh git@github.com:your-org/dorabot-configs.git configs
```

## Detected Source Modules

After initialization, you'll see which directories under `src/` are already git repositories.

Common modules:
- `src/nav` - Navigation and mapping
- `src/ai_agent` - AI assistant
- `src/perception` - Vision and detection
- `src/orchestrator` - Service orchestration

## Complete Documentation

See **[docs/WORKSPACE_GIT_GUIDE.md](docs/WORKSPACE_GIT_GUIDE.md)** for complete guide on:
- Working with submodules
- Daily workflow
- Cloning workspace
- Best practices

## Alternative: Simple Single Repository

If you don't want submodules:

```bash
cd ~/dorabot_ws
./init_workspace_git.sh
# Just use it as a single repository - simpler but less modular
```

---

**For detailed information:** [docs/WORKSPACE_GIT_GUIDE.md](docs/WORKSPACE_GIT_GUIDE.md)
