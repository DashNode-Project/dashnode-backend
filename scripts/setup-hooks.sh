#!/usr/bin/env bash
# Configure git to use project hooks directory (.githooks)
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit 2>/dev/null || true
echo "✅ Git hooks configured to .githooks directory."
