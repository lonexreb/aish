"""Round-trip smoke tests: every public MCP tool can be invoked with a fully
mocked transport and returns a syntactically-valid envelope.

Catches what unit tests miss: a tool that imports cleanly but fails on first
call due to an argv typo, a wrong helper invocation, or a bad envelope shape.
Boosts coverage on the long tail of CRUD tools that the targeted security
tests don't exercise.
"""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx


# ── TensorDock ───────────────────────────────────────────────────────────────
@pytest.fixture
def td(with_token):  # noqa: ARG001
    import importlib

    import aish_mcp.tensordock_mcp_server as srv

    importlib.reload(srv)
    return srv


@pytest.mark.asyncio
@respx.mock
async def test_td_list_instances_envelope(td):
    respx.get("https://dashboard.tensordock.com/api/v2/instances").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    out = json.loads(await td.list_instances())
    assert out["ok"] is True


@pytest.mark.asyncio
@respx.mock
async def test_td_list_hostnodes_envelope(td):
    respx.get(re.compile(r"https://dashboard\.tensordock\.com/api/v2/hostnodes.*")).mock(
        return_value=httpx.Response(200, json={"data": {"hostnodes": []}})
    )
    out = json.loads(await td.list_hostnodes())
    assert out["ok"] is True


@pytest.mark.asyncio
@respx.mock
async def test_td_get_instance_with_uuid(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    respx.get(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}").mock(
        return_value=httpx.Response(200, json={"id": uuid, "status": "running"})
    )
    out = json.loads(await td.get_instance(uuid))
    assert out["ok"] is True


@pytest.mark.asyncio
@respx.mock
async def test_td_start_stop_delete_smoke(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    for verb in ("start", "stop"):
        respx.post(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}/{verb}").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
    respx.delete(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    assert json.loads(await td.start_instance(uuid))["ok"] is True
    assert json.loads(await td.stop_instance(uuid))["ok"] is True
    assert json.loads(await td.delete_instance(uuid))["ok"] is True


@pytest.mark.asyncio
@respx.mock
async def test_td_modify_instance_smoke(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    respx.put(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}/modify").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    out = json.loads(await td.modify_instance(uuid, vcpus=8, ram_gb=64))
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_td_modify_instance_rejects_partial_gpu_args(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    out = json.loads(await td.modify_instance(uuid, gpu_model="h100-sxm5-80gb"))
    assert out["ok"] is False
    assert "gpu_count must be provided together" in out["message"]


@pytest.mark.asyncio
@respx.mock
async def test_td_get_ssh_command_with_port_forward(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    respx.get(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}").mock(
        return_value=httpx.Response(
            200,
            json={
                "ipAddress": "1.2.3.4",
                "portForwards": [{"internal_port": 22, "external_port": 22022}],
            },
        )
    )
    out = json.loads(await td.get_ssh_command(uuid))
    assert out["ok"] is True
    assert "ssh -p 22022 root@1.2.3.4" in out["data"]


@pytest.mark.asyncio
@respx.mock
async def test_td_get_ssh_command_dedicated_ip_fallback(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    respx.get(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}").mock(
        return_value=httpx.Response(
            200,
            json={"ipAddress": "1.2.3.4", "portForwards": [], "dedicated_ip": True},
        )
    )
    out = json.loads(await td.get_ssh_command(uuid))
    assert "ssh root@1.2.3.4" in out["data"]


@pytest.mark.asyncio
@respx.mock
async def test_td_classify_404_returns_not_found(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    respx.get(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    out = json.loads(await td.get_instance(uuid))
    assert out["status"] == "not_found"


@pytest.mark.asyncio
@respx.mock
async def test_td_classify_409_returns_conflict(td):
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    respx.post(f"https://dashboard.tensordock.com/api/v2/instances/{uuid}/start").mock(
        return_value=httpx.Response(409, json={"error": "already running"})
    )
    out = json.loads(await td.start_instance(uuid))
    assert out["status"] == "conflict"


@pytest.mark.asyncio
@respx.mock
async def test_td_classify_429_returns_rate_limited(td):
    respx.get("https://dashboard.tensordock.com/api/v2/instances").mock(
        return_value=httpx.Response(429, text="too many")
    )
    out = json.loads(await td.list_instances())
    assert out["status"] == "rate_limited"


@pytest.mark.asyncio
@respx.mock
async def test_td_network_error_returns_envelope(td):
    respx.get("https://dashboard.tensordock.com/api/v2/instances").mock(
        side_effect=httpx.ConnectError("dns failed")
    )
    out = json.loads(await td.list_instances())
    assert out["status"] == "network_error"


@pytest.mark.asyncio
@respx.mock
async def test_td_validation_uuid_short_circuit(td):
    # Validation must fail before any HTTP traffic
    out = json.loads(await td.start_instance("not-a-uuid"))
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_td_deploy_validates_ssh_key_size(td):
    out = json.loads(
        await td.deploy_instance(
            name="t", gpu_model="h100-sxm5-80gb", ssh_key="A" * 17000
        )
    )
    assert out["status"] == "invalid_argument"
    assert "ssh_key" in out["message"]


@pytest.mark.asyncio
async def test_td_deploy_validates_cloud_init(td):
    out = json.loads(
        await td.deploy_instance(
            name="t",
            gpu_model="h100-sxm5-80gb",
            cloud_init_commands=["echo ok", 42],  # type: ignore[list-item]
        )
    )
    assert out["status"] == "invalid_argument"


# ── Modal ─────────────────────────────────────────────────────────────────────
@pytest.fixture
def md():
    import importlib

    import aish_mcp.modal_mcp_server as srv

    importlib.reload(srv)
    return srv


def _proc(rc: int = 0, out: bytes = b"", err: bytes = b""):
    p = MagicMock()
    p.returncode = rc
    p.communicate = AsyncMock(return_value=(out, err))
    p.kill = MagicMock()
    p.wait = AsyncMock()
    return p


@pytest.mark.asyncio
async def test_md_list_apps_show_stopped(md, tmp_path):
    p = _proc(0, b"app1\napp2\n")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=p)
    ):
        out = json.loads(await md.list_apps(show_stopped=True))
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_md_volume_lifecycle_smoke(md):
    p = _proc(0, b"ok")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=p)
    ):
        for fn, args in (
            (md.list_volumes, ()),
            (md.create_volume, ("my-vol",)),
            (md.volume_ls, ("my-vol", "/")),
            (md.delete_volume, ("my-vol",)),
            (md.list_secrets, ()),
            (md.list_environments, ()),
            (md.list_containers, ()),
            (md.check_config, ()),
        ):
            out = json.loads(await fn(*args))
            assert out["ok"] is True, f"{fn.__name__} failed: {out}"


@pytest.mark.asyncio
async def test_md_volume_put_get_with_real_paths(md, tmp_path):
    src = tmp_path / "data.txt"
    src.write_text("hello")
    p = _proc(0, b"uploaded")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=p)
    ):
        out = json.loads(await md.volume_put("vol", str(src), "/remote.txt"))
        assert out["ok"] is True
        out = json.loads(await md.volume_get("vol", "/remote.txt", str(tmp_path / "out.txt")))
        assert out["ok"] is True


@pytest.mark.asyncio
async def test_md_volume_put_rejects_missing_local(md):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"):
        out = json.loads(await md.volume_put("vol", "/no/such/file.bin"))
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_md_create_secret_argv_includes_kvs(md):
    p = _proc(0, b"created")
    captured: list = []

    async def fake_exec(*args, **kwargs):  # noqa: ARG001
        captured.extend(args)
        return p

    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=fake_exec
    ):
        out = json.loads(await md.create_secret("hf", {"HF_TOKEN": "v1", "WANDB_KEY": "v2"}))
    assert out["ok"] is True
    # Verify list-form argv (no shell)
    assert "HF_TOKEN=v1" in captured
    assert "WANDB_KEY=v2" in captured


@pytest.mark.asyncio
async def test_md_create_secret_rejects_oversized_value(md):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"):
        out = json.loads(await md.create_secret("hf", {"HF_TOKEN": "x" * 5000}))
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_md_shell_no_cmd_returns_interactive_hint(md):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"):
        out = json.loads(await md.shell(gpu="A100"))
    assert out["ok"] is True
    assert out["data"]["interactive_required"] is True


@pytest.mark.asyncio
async def test_md_shell_validates_memory(md):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"):
        out = json.loads(await md.shell(memory=10))  # below min 128
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_md_shell_validates_cpu(md):
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"):
        out = json.loads(await md.shell(cpu=99.0))
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
async def test_md_open_dashboard_static(md):
    out = json.loads(await md.open_dashboard())
    assert out["ok"] is True
    assert out["data"]["apps"].startswith("https://")


@pytest.mark.asyncio
async def test_md_app_logs_smoke(md):
    p = _proc(0, b"app listing")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=p)
    ):
        out = json.loads(await md.app_logs("my-app"))
    assert out["ok"] is True
    assert "modal.com/apps/my-app" in out["data"]["dashboard_url"]


@pytest.mark.asyncio
async def test_md_stop_app_smoke(md):
    p = _proc(0, b"stopped")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=p)
    ):
        out = json.loads(await md.stop_app("my-app"))
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_md_deploy_app_with_real_file(md, tmp_path):
    src = tmp_path / "app.py"
    src.write_text("# fake modal app")
    p = _proc(0, b"deployed at https://modal.com/apps/foo")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=p)
    ):
        out = json.loads(await md.deploy_app(str(src), name="foo"))
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_md_run_app_with_args(md, tmp_path):
    src = tmp_path / "app.py"
    src.write_text("# fake")
    p = _proc(0, b"ran")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"), patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=p)
    ):
        out = json.loads(await md.run_app(str(src), function_name="train", args=["--epochs", "3"]))
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_md_run_app_rejects_oversized_arg(md, tmp_path):
    src = tmp_path / "app.py"
    src.write_text("# fake")
    with patch("aish_mcp.modal_mcp_server.shutil.which", return_value="/usr/bin/modal"):
        out = json.loads(await md.run_app(str(src), args=["x" * 600]))
    assert out["status"] == "invalid_argument"
