"""Build MCPB bundles for Upjack examples.

Key adaptation from the standard MCPB build: upjack is a local package
(not on PyPI), so we build a wheel first and vendor it into deps/.

Upjack manifests use manifest_version 0.4 but include Upjack-specific
fields (`title`, no `author`). The build step patches these to conform
to the MCPB spec (`author` required, no `title`) so that `mcpb pack`
accepts them.
"""

import json
import shutil
import subprocess
from pathlib import Path

from .conftest import LIB_ROOT

# Default author for MCPB manifests built from Upjack examples
_DEFAULT_AUTHOR = {
    "name": "NimbleBrain Inc",
    "email": "hello@nimblebrain.ai",
}


def _patch_manifest_for_mcpb(build_dir: Path) -> None:
    """Patch an Upjack manifest to be MCPB-compatible.

    - Ensures manifest_version is "0.4"
    - Adds author if missing
    - Removes `title` (not in MCPB spec; Upjack uses it as display fallback)
    """
    manifest_path = build_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    manifest["manifest_version"] = "0.4"
    manifest.setdefault("author", _DEFAULT_AUTHOR)
    manifest.pop("title", None)

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def build_upjack_bundle(example_dir: Path, output_dir: Path, bundle_name: str) -> Path:
    """Build an MCPB bundle from an Upjack example directory.

    Steps:
    1. Build upjack wheel via `uv build --wheel`
    2. Copy example to a temp build directory
    3. Patch manifest for MCPB compatibility
    4. Vendor upjack[mcp] + transitive deps into deps/
    5. Pack with `mcpb pack`

    Returns the path to the built .mcpb file.
    """
    # 1. Build the upjack wheel
    result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(output_dir / "wheels")],
        capture_output=True,
        text=True,
        cwd=LIB_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Wheel build failed:\n{result.stderr}")

    # Find the built wheel
    wheels = list((output_dir / "wheels").glob("upjack-*.whl"))
    if not wheels:
        raise RuntimeError("No wheel found after build")
    wheel_path = wheels[0]

    # 2. Copy example to build directory
    build_dir = output_dir / "build"
    shutil.copytree(
        example_dir,
        build_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "workspace", ".venv"),
    )

    # 3. Patch manifest for MCPB compatibility
    _patch_manifest_for_mcpb(build_dir)

    # 4. Vendor deps: install the wheel with [mcp] extra
    deps_dir = build_dir / "deps"
    result = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--target",
            str(deps_dir),
            f"{wheel_path}[mcp]",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Dependency vendoring failed:\n{result.stderr}")

    # 5. Pack the bundle
    bundle_path = output_dir / f"{bundle_name}.mcpb"
    result = subprocess.run(
        ["mcpb", "pack", str(build_dir), str(bundle_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mcpb pack failed:\n{result.stderr}")

    if not bundle_path.exists():
        raise RuntimeError(f"Bundle not found at {bundle_path}")

    return bundle_path
