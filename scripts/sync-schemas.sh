#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$REPO_ROOT/website/public/schemas"
rm -rf "$TARGET"
mkdir -p "$TARGET/v1"
cp "$REPO_ROOT/schemas/v1/"*.schema.json "$TARGET/v1/"
echo "Synced schemas to website/public/schemas/v1/"
