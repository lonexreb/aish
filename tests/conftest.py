"""Shared pytest fixtures and import-path setup.

Tests must never reach a real API. respx patches httpx; AsyncMock patches
asyncio subprocess. An autouse fixture wipes credentials so a stray real
call would fail closed instead of silently hitting prod.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the plugin importable as `mcp.<module>`.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _scrub_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip any production credentials from the test environment.

    This is the auto-use safety net referenced in pytest's pitfalls research:
    if a test ever accidentally bypasses respx or the subprocess mock, a real
    call would fail rather than spend money or mutate prod resources.
    """
    for var in ("TENSORDOCK_API_TOKEN", "AISH_LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AISH_LOG_LEVEL", "WARNING")


@pytest.fixture
def with_token(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "tdk_TEST_token_for_unit_tests_only"
    monkeypatch.setenv("TENSORDOCK_API_TOKEN", token)
    return token
