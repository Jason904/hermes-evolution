#!/bin/bash
# Hermes Evolution — daily update script
# Called by cron at midnight. Generates fresh HTML and pushes to GitHub Pages.
set -euo pipefail

REPO_DIR="/Users/jiangsheng/workspace/hermes-evolution"
cd "$REPO_DIR"

# Generate fresh data and HTML
echo "[$(date -Iseconds)] Generating evolution data..."
/usr/bin/python3 generate.py

# Stage changes
git add -A

# Only commit if there are changes
if git diff --cached --quiet; then
    echo "[$(date -Iseconds)] No changes to commit — skipping push."
    exit 0
fi

git commit -m "📊 Daily evolution update — $(date +%Y-%m-%d)"

# Pull first in case of remote changes (rare), then push
git pull --rebase origin main 2>/dev/null || true
git push origin main

echo "[$(date -Iseconds)] ✅ Pushed to GitHub Pages: https://jason904.github.io/hermes-evolution/"
