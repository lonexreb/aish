#!/usr/bin/env python3
"""TensorDock MCP server — GPU VM management for Claude Code.

Hardened per ANTHROPIC-PLUGIN.md (STOP-SHIP checklist + MCP security spec):

- All inputs validated at the tool boundary (validators in `_validation.py`).
- Bearer tokens redacted from every error path (`_redact.py`).
- HTTPS enforced; SSRF guarded by accepting only the production base URL.
- Hard timeouts on every httpx call.
- Errors returned as structured `{status, code, message}` JSON, never `repr(exc)`.

Setup:
  1. Get an API token: https://dashboard.tensordock.com/developers
  2. export TENSORDOCK_API_TOKEN="tdk_..."  (or set in ~/.claude/settings.json env)
  3. The aish plugin auto-launches this via .mcp.json on Claude Code start.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from mcp._logging import get_logger
from mcp._redact import redact, redact_dict
from mcp._validation import (
    ValidationError,
    validate_choice,
    validate_gpu_model,
    validate_int_range,
    validate_resource_name,
    validate_uuid,
)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "https://dashboard.tensordock.com/api/v2"
GET_TIMEOUT = float(os.environ.get("AISH_HTTP_GET_TIMEOUT", "30"))
POST_TIMEOUT = float(os.environ.get("AISH_HTTP_POST_TIMEOUT", "60"))

log = get_logger("aish.tensordock")

mcp = FastMCP(
    "aish-tensordock",
    instructions=(
        "TensorDock GPU cloud control plane. "
        "Use these tools to browse available GPU offerings (list_locations, list_hostnodes), "
        "deploy and manage VM instances (deploy_instance, start/stop/modify/delete_instance), "
        "and retrieve SSH connection details. All inputs are validated; bearer tokens are "
        "never echoed in error responses."
    ),
)


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _api_token() -> str:
    token = os.environ.get("TENSORDOCK_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TENSORDOCK_API_TOKEN is not set. "
            "Get a token at https://dashboard.tensordock.com/developers, "
            "then add it to ~/.claude/settings.json env block."
        )
    return token


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _err(status: str, code: int | None, message: str, *, hint: str | None = None) -> str:
    """Build a JSON error envelope with redaction applied to every text field."""
    payload: dict[str, Any] = {
        "ok": False,
        "status": status,
        "code": code,
        "message": redact(message),
    }
    if hint:
        payload["hint"] = redact(hint)
    return json.dumps(payload, indent=2)


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, indent=2)


def _classify(exc: httpx.HTTPStatusError) -> str:
    """Map an httpx status error to our error envelope.

    Per ERR-01..05: distinguish 4xx (caller fault) from 5xx (transient/server),
    surface the API's own error message when present, redact sensitive fields.
    """
    code = exc.response.status_code
    try:
        body = exc.response.json()
    except (ValueError, json.JSONDecodeError):
        body = None

    api_msg = ""
    if isinstance(body, dict):
        # Common shapes: {"error": "..."} or {"errors": [{"detail": "..."}]}
        api_msg = (
            body.get("error")
            or body.get("message")
            or (body.get("errors", [{}])[0].get("detail") if isinstance(body.get("errors"), list) else "")
            or ""
        )

    if code == 401:
        status = "unauthorized"
        hint = "Check TENSORDOCK_API_TOKEN. Token may be invalid, revoked, or missing."
    elif code == 403:
        status = "forbidden"
        hint = "Token lacks permission for this operation."
    elif code == 404:
        status = "not_found"
        hint = "Resource does not exist or you don't have access to it."
    elif code == 409:
        status = "conflict"
        hint = "Resource is in an incompatible state (e.g. instance must be stopped before modify)."
    elif code == 422:
        status = "invalid_argument"
        hint = "TensorDock rejected the request payload. Check field names and value ranges."
    elif code == 429:
        status = "rate_limited"
        hint = "Slow down and retry after a brief delay."
    elif 500 <= code < 600:
        status = "upstream_error"
        hint = "TensorDock returned a server error. Retry after a brief delay."
    else:
        status = "http_error"
        hint = None

    msg = api_msg or f"HTTP {code} from TensorDock"
    return _err(status, code, msg, hint=hint)


async def _get(path: str, params: dict | None = None) -> str:
    try:
        async with httpx.AsyncClient(timeout=GET_TIMEOUT, follow_redirects=False) as client:
            resp = await client.get(f"{BASE_URL}{path}", headers=_headers(), params=params)
            resp.raise_for_status()
            return _ok(resp.json())
    except httpx.HTTPStatusError as exc:
        log.warning("GET %s -> %d", path, exc.response.status_code)
        return _classify(exc)
    except httpx.RequestError as exc:
        log.warning("GET %s network error: %s", path, type(exc).__name__)
        return _err("network_error", None, f"Network error talking to TensorDock: {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001 — broad catch, redaction-safe
        log.exception("Unexpected error on GET %s", path)
        return _err("internal_error", None, f"Unexpected error: {type(exc).__name__}")


async def _post(path: str, body: dict | None = None) -> str:
    try:
        async with httpx.AsyncClient(timeout=POST_TIMEOUT, follow_redirects=False) as client:
            resp = await client.post(f"{BASE_URL}{path}", headers=_headers(), json=body)
            resp.raise_for_status()
            return _ok(resp.json())
    except httpx.HTTPStatusError as exc:
        log.warning("POST %s -> %d", path, exc.response.status_code)
        return _classify(exc)
    except httpx.RequestError as exc:
        log.warning("POST %s network error: %s", path, type(exc).__name__)
        return _err("network_error", None, f"Network error talking to TensorDock: {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Unexpected error on POST %s", path)
        return _err("internal_error", None, f"Unexpected error: {type(exc).__name__}")


async def _put(path: str, body: dict | None = None) -> str:
    try:
        async with httpx.AsyncClient(timeout=GET_TIMEOUT, follow_redirects=False) as client:
            resp = await client.put(f"{BASE_URL}{path}", headers=_headers(), json=body)
            resp.raise_for_status()
            return _ok(resp.json())
    except httpx.HTTPStatusError as exc:
        return _classify(exc)
    except httpx.RequestError as exc:
        return _err("network_error", None, f"Network error: {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Unexpected error on PUT %s", path)
        return _err("internal_error", None, f"Unexpected error: {type(exc).__name__}")


async def _delete(path: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=GET_TIMEOUT, follow_redirects=False) as client:
            resp = await client.delete(f"{BASE_URL}{path}", headers=_headers())
            resp.raise_for_status()
            return _ok(resp.json())
    except httpx.HTTPStatusError as exc:
        return _classify(exc)
    except httpx.RequestError as exc:
        return _err("network_error", None, f"Network error: {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Unexpected error on DELETE %s", path)
        return _err("internal_error", None, f"Unexpected error: {type(exc).__name__}")


def _validation_error(exc: ValidationError) -> str:
    return _err("invalid_argument", 400, str(exc))


# ── Tools: Discovery ──────────────────────────────────────────────────────────
@mcp.tool()
async def list_locations(gpu_type: str | None = None) -> str:
    """List available deployment locations with GPU types, pricing, and max resources.

    Args:
        gpu_type: Optional substring filter on GPU display name (e.g. "4090", "h100").
                  Limited to 64 chars; alnum, dot, dash, underscore only.

    Returns:
        JSON envelope `{ok, data: [{id, city, country, tier, gpus: [...]}]}`.
    """
    try:
        if gpu_type is not None:
            validate_gpu_model(gpu_type, "gpu_type")
    except ValidationError as e:
        return _validation_error(e)

    raw = await _get("/locations")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not parsed.get("ok"):
        return raw

    locations = parsed["data"].get("data", {}).get("locations", [])
    if gpu_type:
        gtl = gpu_type.lower()
        locations = [
            {**loc, "gpus": [
                g for g in loc.get("gpus", [])
                if gtl in g.get("displayName", "").lower() or gtl in g.get("v0Name", "").lower()
            ]}
            for loc in locations
        ]
        locations = [loc for loc in locations if loc["gpus"]]

    summary = [
        {
            "id": loc.get("id"),
            "city": loc.get("city"),
            "state": loc.get("stateprovince"),
            "country": loc.get("country"),
            "tier": loc.get("tier"),
            "gpus": [
                {
                    "name": g.get("displayName"),
                    "v0Name": g.get("v0Name"),
                    "max_count": g.get("max_count"),
                    "price_per_hr": g.get("price_per_hr"),
                    "max_vcpus": g.get("resources", {}).get("max_vcpus"),
                    "max_ram_gb": g.get("resources", {}).get("max_ram_gb"),
                    "dedicated_ip": g.get("network_features", {}).get("dedicated_ip_available"),
                }
                for g in loc.get("gpus", [])
            ],
        }
        for loc in locations
    ]
    return _ok(summary)


@mcp.tool()
async def list_hostnodes(
    gpu: str | None = None,
    min_ram_gb: int | None = None,
    min_vcpu: int | None = None,
) -> str:
    """List available hostnodes (capped at 20) with detailed resources and pricing.

    Args:
        gpu: GPU v0Name (e.g. "h100-sxm5-80gb").
        min_ram_gb: 0..2048.
        min_vcpu: 0..256.

    Returns:
        JSON envelope `{ok, data: [...]}` capped to 20 entries for context safety.
    """
    try:
        if gpu is not None:
            validate_gpu_model(gpu, "gpu")
        if min_ram_gb is not None:
            validate_int_range(min_ram_gb, "min_ram_gb", minimum=0, maximum=2048)
        if min_vcpu is not None:
            validate_int_range(min_vcpu, "min_vcpu", minimum=0, maximum=256)
    except ValidationError as e:
        return _validation_error(e)

    params: dict[str, Any] = {}
    if gpu:
        params["gpu"] = gpu
    if min_ram_gb is not None:
        params["minRamGb"] = min_ram_gb
    if min_vcpu is not None:
        params["minVcpu"] = min_vcpu

    raw = await _get("/hostnodes", params=params or None)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not parsed.get("ok"):
        return raw

    hostnodes = parsed["data"].get("data", {}).get("hostnodes", [])[:20]
    summary = [
        {
            "id": hn.get("id"),
            "uptime_pct": hn.get("uptime_percentage"),
            "gpus": hn.get("available_resources", {}).get("gpus", []),
            "vcpus_available": hn.get("available_resources", {}).get("vcpu_count"),
            "ram_gb_available": hn.get("available_resources", {}).get("ram_gb"),
            "storage_gb_available": hn.get("available_resources", {}).get("storage_gb"),
            "has_public_ip": hn.get("available_resources", {}).get("has_public_ip_available"),
            "pricing": hn.get("pricing"),
            "location": redact_dict(hn.get("location", {}) or {}),
        }
        for hn in hostnodes
    ]
    return _ok(summary)


# ── Tools: Instance Management ────────────────────────────────────────────────
@mcp.tool()
async def list_instances() -> str:
    """List all your TensorDock VM instances with status and config.

    Returns:
        JSON envelope `{ok, data}` containing the raw API response.
    """
    return await _get("/instances")


@mcp.tool()
async def get_instance(instance_id: str) -> str:
    """Get detailed info for one instance.

    Args:
        instance_id: UUID of the instance.

    Returns:
        JSON envelope with IP, port forwards, resources, and hourly rate.
    """
    try:
        validate_uuid(instance_id, "instance_id")
    except ValidationError as e:
        return _validation_error(e)
    return await _get(f"/instances/{instance_id}")


@mcp.tool()
async def deploy_instance(
    name: str,
    gpu_model: str,
    gpu_count: int = 1,
    vcpus: int = 4,
    ram_gb: int = 16,
    storage_gb: int = 200,
    location_id: str | None = None,
    image: str = "ubuntu2404",
    ssh_key: str = "",
    use_dedicated_ip: bool = False,
    cloud_init_commands: list[str] | None = None,
) -> str:
    """Deploy a new GPU VM instance on TensorDock.

    Args:
        name: Instance name (1-64 chars, alnum + `_.-`).
        gpu_model: GPU v0Name (use list_locations to discover available values).
        gpu_count: 1..16.
        vcpus: 2..256, must be even.
        ram_gb: 2..2048.
        storage_gb: 100..10000, multiples of 50 only.
        location_id: Optional location UUID (use list_locations to discover).
        image: "ubuntu2404" or "windows10".
        ssh_key: Public SSH key (raw string, max 16 KB).
        use_dedicated_ip: Request a dedicated public IP.
        cloud_init_commands: Optional list of strings to run on first boot.

    Returns:
        JSON envelope with new instance id, name, and status.
    """
    try:
        validate_resource_name(name, "name")
        validate_gpu_model(gpu_model, "gpu_model")
        validate_int_range(gpu_count, "gpu_count", minimum=1, maximum=16)
        validate_int_range(vcpus, "vcpus", minimum=2, maximum=256)
        if vcpus % 2 != 0:
            raise ValidationError("vcpus must be even")
        validate_int_range(ram_gb, "ram_gb", minimum=2, maximum=2048)
        validate_int_range(storage_gb, "storage_gb", minimum=100, maximum=10000)
        if storage_gb % 50 != 0:
            raise ValidationError("storage_gb must be a multiple of 50")
        validate_choice(image, ("ubuntu2404", "windows10"), "image")
        if location_id is not None:
            validate_uuid(location_id, "location_id")
        if ssh_key and len(ssh_key) > 16384:
            raise ValidationError("ssh_key exceeds 16KB")
        if cloud_init_commands is not None:
            if not isinstance(cloud_init_commands, list) or len(cloud_init_commands) > 64:
                raise ValidationError("cloud_init_commands must be a list of <=64 entries")
            for i, c in enumerate(cloud_init_commands):
                if not isinstance(c, str) or len(c) > 4096:
                    raise ValidationError(f"cloud_init_commands[{i}] must be a string <=4KB")
    except ValidationError as e:
        return _validation_error(e)

    body: dict[str, Any] = {
        "data": {
            "type": "virtualmachine",
            "attributes": {
                "name": name,
                "type": "virtualmachine",
                "image": image,
                "resources": {
                    "vcpu_count": vcpus,
                    "ram_gb": ram_gb,
                    "storage_gb": storage_gb,
                    "gpus": {gpu_model: {"count": gpu_count}},
                },
            },
        }
    }
    attrs = body["data"]["attributes"]
    if location_id:
        attrs["location_id"] = location_id
    if ssh_key:
        attrs["ssh_key"] = ssh_key
    if use_dedicated_ip:
        attrs["useDedicatedIp"] = True
    if cloud_init_commands:
        attrs["cloud_init"] = {"runcmd": cloud_init_commands, "package_update": True}

    return await _post("/instances", body)


@mcp.tool()
async def start_instance(instance_id: str) -> str:
    """Start a stopped TensorDock instance.

    Args:
        instance_id: UUID of the instance.
    """
    try:
        validate_uuid(instance_id, "instance_id")
    except ValidationError as e:
        return _validation_error(e)
    return await _post(f"/instances/{instance_id}/start")


@mcp.tool()
async def stop_instance(instance_id: str) -> str:
    """Stop a running instance. Storage is still billed.

    Args:
        instance_id: UUID of the instance.
    """
    try:
        validate_uuid(instance_id, "instance_id")
    except ValidationError as e:
        return _validation_error(e)
    return await _post(f"/instances/{instance_id}/stop")


@mcp.tool()
async def delete_instance(instance_id: str) -> str:
    """Permanently delete an instance. CANNOT BE UNDONE.

    Args:
        instance_id: UUID of the instance.
    """
    try:
        validate_uuid(instance_id, "instance_id")
    except ValidationError as e:
        return _validation_error(e)
    return await _delete(f"/instances/{instance_id}")


@mcp.tool()
async def modify_instance(
    instance_id: str,
    vcpus: int | None = None,
    ram_gb: int | None = None,
    storage_gb: int | None = None,
    gpu_model: str | None = None,
    gpu_count: int | None = None,
) -> str:
    """Modify resources of a stopped instance. Instance must be stopped first.

    Args:
        instance_id: UUID of the instance.
        vcpus: 2..256, even.
        ram_gb: 2..2048.
        storage_gb: 100..10000, multiples of 50, can only INCREASE.
        gpu_model: New GPU v0Name (requires gpu_count).
        gpu_count: 1..16 (requires gpu_model).
    """
    try:
        validate_uuid(instance_id, "instance_id")
        if vcpus is not None:
            validate_int_range(vcpus, "vcpus", minimum=2, maximum=256)
            if vcpus % 2 != 0:
                raise ValidationError("vcpus must be even")
        if ram_gb is not None:
            validate_int_range(ram_gb, "ram_gb", minimum=2, maximum=2048)
        if storage_gb is not None:
            validate_int_range(storage_gb, "storage_gb", minimum=100, maximum=10000)
            if storage_gb % 50 != 0:
                raise ValidationError("storage_gb must be a multiple of 50")
        if (gpu_model is None) != (gpu_count is None):
            raise ValidationError("gpu_model and gpu_count must be provided together")
        if gpu_model is not None and gpu_count is not None:
            validate_gpu_model(gpu_model, "gpu_model")
            validate_int_range(gpu_count, "gpu_count", minimum=1, maximum=16)
    except ValidationError as e:
        return _validation_error(e)

    body: dict[str, Any] = {}
    if vcpus is not None:
        body["cpuCores"] = vcpus
    if ram_gb is not None:
        body["ramGb"] = ram_gb
    if storage_gb is not None:
        body["diskGb"] = storage_gb
    if gpu_model and gpu_count:
        body["gpus"] = {"gpuV0Name": gpu_model, "count": gpu_count}

    return await _put(f"/instances/{instance_id}/modify", body)


@mcp.tool()
async def get_ssh_command(instance_id: str) -> str:
    """Get the SSH connection string for an instance.

    Args:
        instance_id: UUID of the instance.

    Returns:
        Plain `ssh ...` string, or guidance if no SSH port is configured.
    """
    try:
        validate_uuid(instance_id, "instance_id")
    except ValidationError as e:
        return _validation_error(e)

    raw = await _get(f"/instances/{instance_id}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not parsed.get("ok"):
        return raw

    data = parsed["data"]
    ip = data.get("ipAddress") or data.get("ip") or "UNKNOWN"
    port_forwards = data.get("portForwards", []) or []
    ssh_port = next(
        (pf.get("external_port") for pf in port_forwards if pf.get("internal_port") == 22),
        None,
    )

    if ssh_port:
        return _ok(f"ssh -p {ssh_port} root@{ip}")
    if data.get("useDedicatedIp") or data.get("dedicated_ip"):
        return _ok(f"ssh root@{ip}")
    return _ok(
        f"Instance IP: {ip}. No internal:22 port forward found. "
        "If you provisioned with a dedicated IP, try: ssh root@<ip>."
    )


# ── Entry point ──────────────────────────────────────────────────────────────
def main() -> None:
    log.info("Starting aish-tensordock MCP server (base=%s)", BASE_URL)
    mcp.run()


if __name__ == "__main__":
    main()
