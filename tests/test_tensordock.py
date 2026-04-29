"""TensorDock MCP server tests — respx-mocked httpx, no real network."""

from __future__ import annotations

import json

import httpx
import pytest
import respx


@pytest.fixture
def server(with_token):  # noqa: ARG001 — fixture sets env, just needs to run
    """Import the server module after env is primed."""
    import importlib

    import aish_mcp.tensordock_mcp_server as srv

    importlib.reload(srv)
    return srv


@pytest.mark.asyncio
@respx.mock
async def test_list_locations_filters_by_gpu(server):
    body = {
        "data": {
            "locations": [
                {
                    "id": "loc-1",
                    "city": "Reykjavik",
                    "stateprovince": "Capital",
                    "country": "Iceland",
                    "tier": "tier3",
                    "gpus": [
                        {"displayName": "RTX 4090", "v0Name": "geforcertx4090-pcie-24gb"},
                        {"displayName": "H100", "v0Name": "h100-sxm5-80gb"},
                    ],
                }
            ]
        }
    }
    respx.get("https://dashboard.tensordock.com/api/v2/locations").mock(
        return_value=httpx.Response(200, json=body)
    )

    out = json.loads(await server.list_locations(gpu_type="h100"))
    assert out["ok"] is True
    assert len(out["data"]) == 1
    assert all(g["name"] == "H100" for g in out["data"][0]["gpus"])


@pytest.mark.asyncio
@respx.mock
async def test_get_instance_rejects_non_uuid(server):
    out = json.loads(await server.get_instance("not-a-uuid"))
    assert out["ok"] is False
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
@respx.mock
async def test_classify_401_returns_unauthorized(server):
    respx.get("https://dashboard.tensordock.com/api/v2/instances").mock(
        return_value=httpx.Response(401, json={"error": "Bearer abc123 invalid"})
    )
    out = json.loads(await server.list_instances())
    assert out["ok"] is False
    assert out["status"] == "unauthorized"
    # bearer must be redacted from the surfaced message
    assert "abc123" not in out["message"]


@pytest.mark.asyncio
@respx.mock
async def test_classify_5xx_returns_upstream_error(server):
    respx.get("https://dashboard.tensordock.com/api/v2/instances").mock(
        return_value=httpx.Response(503, text="upstream temporarily unavailable")
    )
    out = json.loads(await server.list_instances())
    assert out["status"] == "upstream_error"


@pytest.mark.asyncio
@respx.mock
async def test_deploy_instance_validation_blocks_bad_storage(server):
    out = json.loads(
        await server.deploy_instance(
            name="test",
            gpu_model="h100-sxm5-80gb",
            storage_gb=137,  # not a multiple of 50
        )
    )
    assert out["ok"] is False
    assert out["status"] == "invalid_argument"
    assert "multiple of 50" in out["message"]


@pytest.mark.asyncio
@respx.mock
async def test_deploy_instance_validation_blocks_bad_image(server):
    out = json.loads(
        await server.deploy_instance(
            name="test",
            gpu_model="h100-sxm5-80gb",
            image="windows11",  # not in the choice tuple
        )
    )
    assert out["ok"] is False
    assert out["status"] == "invalid_argument"


@pytest.mark.asyncio
@respx.mock
async def test_deploy_instance_happy_path(server):
    respx.post("https://dashboard.tensordock.com/api/v2/instances").mock(
        return_value=httpx.Response(200, json={"data": {"id": "inst-1", "name": "x"}})
    )
    out = json.loads(
        await server.deploy_instance(
            name="my-job",
            gpu_model="h100-sxm5-80gb",
            gpu_count=1,
            vcpus=8,
            ram_gb=64,
            storage_gb=200,
        )
    )
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_missing_token_surfaces_actionable_error(server, monkeypatch):
    # Strip the token the fixture set; expect actionable configuration_error
    # with the setup hint, NOT a generic internal_error.
    monkeypatch.delenv("TENSORDOCK_API_TOKEN", raising=False)
    out = json.loads(await server.list_instances())
    assert out["ok"] is False
    assert out["status"] == "configuration_error"
    assert "TENSORDOCK_API_TOKEN" in out["message"]
    assert "dashboard.tensordock.com/developers" in out["message"]
