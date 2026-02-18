"""E2E test configuration and fixtures."""

import shutil
from pathlib import Path

import pytest

LIB_ROOT = Path(__file__).resolve().parent.parent
CODE_ROOT = LIB_ROOT.parent.parent
CRM_DIR = CODE_ROOT / "examples" / "crm"
RESEARCH_DIR = CODE_ROOT / "examples" / "research-assistant"

# mpak caches extracted local bundles here; workspace dirs persist between runs
_MPAK_LOCAL_CACHE = Path.home() / ".mpak" / "cache" / "_local"


@pytest.fixture(autouse=True)
def _clean_mpak_workspaces():
    """Remove workspace dirs from mpak's local cache before each test.

    mpak run --local extracts bundles to ~/.mpak/cache/_local/<hash>/ and
    reuses the same directory across invocations. The Upjack server writes
    entity data to ./workspace relative to that extraction dir, so state
    leaks between tests. This fixture ensures a clean workspace each time.
    """
    if _MPAK_LOCAL_CACHE.exists():
        for cache_dir in _MPAK_LOCAL_CACHE.iterdir():
            workspace = cache_dir / "workspace"
            if workspace.is_dir():
                shutil.rmtree(workspace)
