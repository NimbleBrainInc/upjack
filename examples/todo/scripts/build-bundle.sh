#!/usr/bin/env bash
set -euo pipefail

# Build an MCPB bundle for the Todo Upjack app.
# Usage: ./scripts/build-bundle.sh [version]

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-}"
LIB_DIR="$DIR/../../lib"

cd "$DIR"

# Read name from manifest
NAME=$(jq -r '.name' manifest.json)
if [ -z "$NAME" ] || [ "$NAME" = "null" ]; then
  echo "Error: could not read name from manifest.json" >&2
  exit 1
fi

# Determine version: argument > manifest > fallback
if [ -z "$VERSION" ]; then
  VERSION=$(jq -r '.version' manifest.json)
fi
if [ -z "$VERSION" ] || [ "$VERSION" = "null" ]; then
  echo "Error: no version provided and none found in manifest.json" >&2
  exit 1
fi

# Detect OS and arch for the output filename
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  ARCH="amd64" ;;
  aarch64) ARCH="arm64" ;;
  arm64)   ARCH="arm64" ;;
esac

SAFE_NAME=$(echo "$NAME" | sed 's|^@||; s|/|-|g')
OUTPUT="${SAFE_NAME}-${VERSION}-${OS}-${ARCH}.mcpb"

echo "Building bundle: $OUTPUT"
echo "  name:    $NAME"
echo "  version: $VERSION"
echo "  os:      $OS"
echo "  arch:    $ARCH"

# Vendor Python dependencies from the local upjack library
echo ""
echo "Vendoring Python dependencies into deps/..."
rm -rf deps/
uv pip install --target ./deps --only-binary :all: "$LIB_DIR[mcp]" 2>/dev/null || \
uv pip install --target ./deps "$LIB_DIR[mcp]"

echo "Vendored packages:"
ls deps/ | head -20 || true
du -sh deps/

# Pack the bundle
echo ""
echo "Packing bundle..."
mcpb pack . "$OUTPUT"

echo ""
echo "Bundle built: $OUTPUT"
ls -lh "$OUTPUT"
