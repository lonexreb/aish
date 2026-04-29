"""Modal MCP server tests — subprocess mocked end-to-end."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def server():
    import importlib

    import aish_mcp.modal_mcp_server as srv

    importlib.reload(srv)
    return srv


def _fake_proc(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


@pytest.mark.asyncio
async def test_list_apps_happy_path(server):
    fake = _fake_proc(0, b"app  | live\n")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/local/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake)
    ):
        out = json.loads(await server.list_apps())
    assert out["ok"] is True
    assert "app" in out["data"]["output"]


@pytest.mark.asyncio
async def test_modal_cli_missing_returns_typed_error(server):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value=None):
        out = json.loads(await server.list_apps())
    assert out["ok"] is False
    assert out["status"] == "modal_cli_missing"


@pytest.mark.asyncio
async def test_create_secret_validates_keys(server):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/local/bin/modal"):
        out = json.loads(
            await server.create_secret(
                name="hf",
                key_values={"lower_key": "value"},  # POSIX env names must be UPPER
            )
        )
    assert out["ok"] is False
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_deploy_app_rejects_path_traversal(server):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/local/bin/modal"):
        out = json.loads(await server.deploy_app(file_path="../../etc/passwd"))
    assert out["ok"] is False
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_shell_validates_gpu_choice(server):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/local/bin/modal"):
        out = json.loads(await server.shell(gpu="X9999"))
    assert out["ok"] is False
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_subprocess_failure_returns_typed_error(server):
    fake = _fake_proc(1, b"", b"Not authenticated. Run modal setup.")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/local/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake)
    ):
        out = json.loads(await server.list_apps())
    assert out["ok"] is False
    assert out["status"] == "subprocess_failed"
    assert "Not authenticated" in out["message"]


@pytest.mark.asyncio
async def test_timeout_kills_and_returns_typed_error(server):
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=__import__("asyncio").TimeoutError())
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/local/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)
    ):
        out = json.loads(await server.list_apps())
    assert out["ok"] is False
    assert out["status"] == "timeout"
    proc.kill.assert_called_once()
    proc.wait.assert_awaited()


@pytest.mark.asyncio
async def test_open_dashboard_no_subprocess(server):
    out = json.loads(await server.open_dashboard())
    assert out["ok"] is True
    assert "apps" in out["data"]
