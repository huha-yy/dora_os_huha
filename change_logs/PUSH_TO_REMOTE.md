# Push Dorabot Workspace to Remote Repository

## Step 1: Create Remote Repository on GitHub/GitLab

### Option A: GitHub (Recommended)

1. **Go to GitHub:** https://github.com/new

2. **Create repository:**
   - Repository name: `dorabot-workspace` (or your preferred name)
   - Description: "Dorabot navigation and assistance robot workspace"
   - Visibility: 
     - ✅ **Private** (recommended for proprietary code)
     - or Public (if open source)
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)

3. **Click "Create repository"**

4. **Copy the SSH URL** (it will look like):
   ```
   git@github.com:your-username/dorabot-workspace.git
   ```

### Option B: GitLab

1. **Go to GitLab:** https://gitlab.com/projects/new

2. **Create project:**
   - Project name: `dorabot-workspace`
   - Visibility: Private or Public
   - **DO NOT** initialize with README

3. **Copy the SSH URL**

### Option C: Self-Hosted Git Server

Ask your admin for the repository URL.

## Step 2: Add Remote to Your Local Repository

```bash
cd ~/dorabot_ws

# Add remote (replace with your actual URL)
git remote add origin git@github.com:YOUR_USERNAME/dorabot-workspace.git

# Verify remote was added
git remote -v
```

You should see:
```
origin  git@github.com:YOUR_USERNAME/dorabot-workspace.git (fetch)
origin  git@github.com:YOUR_USERNAME/dorabot-workspace.git (push)
```

## Step 3: Push to Remote

```bash
cd ~/dorabot_ws

# Rename branch to main (if needed)
git branch -M main

# Push to remote
git push -u origin main
```

### If you get "Permission denied" error:

You need to set up SSH keys with GitHub/GitLab.

#### Setup SSH Keys for GitHub:

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your-email@example.com"

# Press Enter to accept default location
# Optionally set a passphrase

# Start SSH agent
eval "$(ssh-agent -s)"

# Add key to SSH agent
ssh-add ~/.ssh/id_ed25519

# Copy public key to clipboard
cat ~/.ssh/id_ed25519.pub
```

Then:
1. Go to GitHub → Settings → SSH and GPG keys
2. Click "New SSH key"
3. Paste your public key
4. Save

Test SSH connection:
```bash
ssh -T git@github.com
```

You should see: "Hi username! You've successfully authenticated..."

Now try pushing again:
```bash
cd ~/dorabot_ws
git push -u origin main
```

## Step 4: Verify Push

Go to your GitHub/GitLab repository URL in browser and verify files are there.

## Step 5: Setup Submodules (Optional but Recommended)

Now that your main workspace is on remote, you can add submodules for source directories.

### For each module under src/:

#### 1. Create remote repository for the module:

On GitHub, create repositories:
- `dorabot-nav` (for src/nav)
- `dorabot-ai-agent` (for src/ai_agent)
- `dorabot-orchestrator` (for src/orchestrator)
- `dorabot-perception` (for src/perception)

#### 2. Initialize and push each module:

```bash
# Example for nav module
cd ~/dorabot_ws/src/nav

# Check if already initialized
if [ ! -d ".git" ]; then
    git init
fi

# Add all files
git add .

# Commit
git commit -m "Initial commit: Navigation module"

# Add remote
git remote add origin git@github.com:YOUR_USERNAME/dorabot-nav.git

# Push
git branch -M main
git push -u origin main

# Go back to workspace
cd ~/dorabot_ws
```

#### 3. Add as submodule to main workspace:

```bash
cd ~/dorabot_ws

# Remove the directory (backup first if needed)
mv src/nav src/nav.backup

# Add as submodule
git submodule add git@github.com:YOUR_USERNAME/dorabot-nav.git src/nav

# Commit submodule addition
git add .gitmodules src/nav
git commit -m "Add nav submodule"
git push
```

#### 4. Repeat for other modules:

```bash
# For ai_agent
cd ~/dorabot_ws/src/ai_agent
git init
git add .
git commit -m "Initial commit: AI Agent module"
git remote add origin git@github.com:YOUR_USERNAME/dorabot-ai-agent.git
git push -u origin main

cd ~/dorabot_ws
./add_submodule.sh git@github.com:YOUR_USERNAME/dorabot-ai-agent.git src/ai_agent

# For orchestrator
cd ~/dorabot_ws/src/orchestrator
git init
git add .
git commit -m "Initial commit: Orchestrator module"
git remote add origin git@github.com:YOUR_USERNAME/dorabot-orchestrator.git
git push -u origin main

cd ~/dorabot_ws
./add_submodule.sh git@github.com:YOUR_USERNAME/dorabot-orchestrator.git src/orchestrator

# For perception
cd ~/dorabot_ws/src/perception
git init
git add .
git commit -m "Initial commit: Perception module"
git remote add origin git@github.com:YOUR_USERNAME/dorabot-perception.git
git push -u origin main

cd ~/dorabot_ws
./add_submodule.sh git@github.com:YOUR_USERNAME/dorabot-perception.git src/perception
```

### For configs directory (optional):

```bash
cd ~/dorabot_ws/configs
./init_git.sh
git remote add origin git@github.com:YOUR_USERNAME/dorabot-configs.git
git push -u origin main

cd ~/dorabot_ws
./add_submodule.sh git@github.com:YOUR_USERNAME/dorabot-configs.git configs
```

## Step 6: Final Push

After adding all submodules:

```bash
cd ~/dorabot_ws
git add .
git commit -m "Add all submodules"
git push
```

## Quick Reference Card

```bash
# Create repo on GitHub → Copy SSH URL

# In workspace
cd ~/dorabot_ws
git remote add origin git@github.com:USER/dorabot-workspace.git
git branch -M main
git push -u origin main

# Later updates
git add .
git commit -m "Your message"
git push
```

## Troubleshooting

### "Permission denied (publickey)"

Set up SSH keys - see above.

### "Repository not found"

Check the URL is correct:
```bash
git remote -v
```

Update if wrong:
```bash
git remote set-url origin git@github.com:CORRECT_USER/CORRECT_REPO.git
```

### "Updates were rejected"

If remote has changes you don't have:
```bash
git pull origin main --rebase
git push
```

### Use HTTPS instead of SSH

If SSH is problematic, use HTTPS:
```bash
git remote set-url origin https://github.com/YOUR_USERNAME/dorabot-workspace.git
```

You'll be prompted for username/password (or personal access token).

## Summary

1. ✅ Create remote repo on GitHub/GitLab
2. ✅ `git remote add origin <url>`
3. ✅ `git push -u origin main`
4. ✅ Optionally setup submodules for src/ directories
5. ✅ Push final changes

Your workspace is now backed up and version controlled! 🎉
