#!/usr/bin/env python3
"""Modal MCP server — serverless GPU app management for Claude Code.

Hardened per ANTHROPIC-PLUGIN.md (STOP-SHIP checklist + MCP security spec):

- All inputs validated at the tool boundary (validators in `_validation.py`).
- Subprocess uses `asyncio.create_subprocess_exec` with list-form argv only.
- Modal binary located via `shutil.which("modal")`, never via shell expansion.
- Hard timeouts on every subprocess; on TimeoutError the process is killed and
  awaited to prevent zombies.
- Errors returned as structured `{status, code, message}` JSON, secrets redacted.

Setup:
  1. pip install modal
  2. modal setup   # one-time browser auth, writes ~/.modal/config.yaml
  3. The aish plugin auto-launches this via .mcp.json on Claude Code start.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import Any

from mcp.server.fastmcp import FastMCP

from aish_mcp._logging import get_logger
from aish_mcp._redact import redact
from aish_mcp._validation import (
    ValidationError,
    validate_choice,
    validate_env_key,
    validate_int_range,
    validate_resource_name,
    validate_safe_path,
)

def _bounded_timeout(env_key: str, default: float, minimum: float = 1.0, maximum: float = 3600.0) -> float:
    """Same semantics as the TensorDock server's helper — keeps STOP-SHIP item 4
    (hard timeouts) working even if a hostile env var is set."""
    raw = os.environ.get(env_key, str(default))
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return default
    if val != val or val == float("inf") or val < minimum or val > maximum:
        return default
    return val


DEFAULT_TIMEOUT = _bounded_timeout("AISH_MODAL_TIMEOUT_DEFAULT", 120.0)
DEPLOY_TIMEOUT = _bounded_timeout("AISH_MODAL_TIMEOUT_DEPLOY", 300.0)
RUN_TIMEOUT = _bounded_timeout("AISH_MODAL_TIMEOUT_RUN", 600.0)

log = get_logger("aish.modal")

mcp = FastMCP(
    "aish-modal",
    instructions=(
        "Modal serverless GPU control plane. "
        "Use these tools to deploy and run Modal apps, manage volumes and secrets, "
        "and inspect environments. All inputs are validated; the Modal CLI is invoked "
        "as a list-form subprocess (no shell)."
    ),
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _err(status: str, code: int | None, message: str, *, hint: str | None = None) -> str:
    payload: dict[str, Any] = {"ok": False, "status": status, "code": code, "message": redact(message)}
    if hint:
        payload["hint"] = redact(hint)
    return json.dumps(payload, indent=2)


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, indent=2)


def _validation_error(exc: ValidationError) -> str:
    return _err("invalid_argument", 400, str(exc))


def _modal_bin() -> str:
    """Locate the modal CLI binary via PATH, reject if absent."""
    path = shutil.which("modal")
    if not path:
        raise RuntimeError(
            "Modal CLI not found on PATH. Install with `pip install modal`, "
            "then run `modal setup` to authenticate."
        )
    return path


async def _run(argv: list[str], timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Run a subprocess with a hard timeout and zombie-safe kill on expiry.

    Returns a dict {stdout, stderr, returncode}. Never invokes a shell.
    """
    log.debug("subprocess: %s (timeout=%.0fs)", argv[0], timeout)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        log.warning("subprocess timeout after %.0fs: %s", timeout, argv[0])
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        return {"stdout": "", "stderr": f"timeout after {timeout}s", "returncode": -1}
    return {
        "stdout": stdout.decode(errors="replace").strip(),
        "stderr": stderr.decode(errors="replace").strip(),
        "returncode": proc.returncode if proc.returncode is not None else -1,
    }


def _result_to_envelope(result: dict) -> str:
    rc = result.get("returncode", -1)
    stderr = redact(result.get("stderr", ""))
    stdout = redact(result.get("stdout", ""))
    if rc == 0:
        return _ok({"output": stdout, "stderr": stderr})
    if rc == -1:
        return _err("timeout", -1, stderr or "Subprocess timed out")
    return _err(
        "subprocess_failed",
        rc,
        stderr or stdout or f"modal CLI exited with code {rc}",
    )


# ── Tools: Apps ───────────────────────────────────────────────────────────────
@mcp.tool()
async def list_apps(show_stopped: bool = False) -> str:
    """List Modal apps.

    Args:
        show_stopped: include stopped/errored apps (default: live only).
    """
    try:
        modal = _modal_bin()
    except RuntimeError as exc:
        return _err("modal_cli_missing", None, str(exc))
    cmd = [modal, "app", "list"]
    if show_stopped:
        cmd.append("--show-stopped")
    return _result_to_envelope(await _run(cmd))


@mcp.tool()
async def deploy_app(
    file_path: str,
    name: str | None = None,
    environment: str | None = None,
) -> str:
    """Deploy a Modal app from a Python file.

    Args:
        file_path: Path to a .py file containing a Modal `App`.
        name: Optional deployment name override (alnum + `_.-`, <=64 chars).
        environment: Optional Modal environment (alnum + `_.-`, <=64 chars).
    """
    try:
        validate_safe_path(file_path, "file_path", allow_absolute=True, must_exist=True)
        if name is not None:
            validate_resource_name(name, "name")
        if environment is not None:
            validate_resource_name(environment, "environment")
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))

    cmd = [modal, "deploy", file_path]
    if name:
        cmd.extend(["--name", name])
    if environment:
        cmd.extend(["--env", environment])
    return _result_to_envelope(await _run(cmd, timeout=DEPLOY_TIMEOUT))


@mcp.tool()
async def run_app(
    file_path: str,
    function_name: str | None = None,
    detach: bool = False,
    args: list[str] | None = None,
) -> str:
    """Run a Modal app ephemerally.

    Args:
        file_path: Path to .py with the app.
        function_name: Optional function (alnum + `_`, <=64 chars).
        detach: Keep running after client disconnects.
        args: Extra CLI args to pass through (each <=512 chars, max 32 items, no NUL).
    """
    try:
        validate_safe_path(file_path, "file_path", allow_absolute=True, must_exist=True)
        if function_name is not None:
            validate_resource_name(function_name, "function_name")
        if args is not None:
            if not isinstance(args, list) or len(args) > 32:
                raise ValidationError("args must be a list of <=32 strings")
            for i, a in enumerate(args):
                if not isinstance(a, str) or len(a) > 512 or "\x00" in a:
                    raise ValidationError(f"args[{i}] must be a string <=512 chars without NUL")
        # Reject ambiguous combination: pre-qualified path + separate function_name
        if function_name and "::" in file_path:
            raise ValidationError(
                "Pass either function_name OR a file_path containing '::', not both"
            )
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))

    cmd = [modal, "run"]
    if detach:
        cmd.append("--detach")
    cmd.append(f"{file_path}::{function_name}" if function_name else file_path)
    if args:
        cmd.extend(args)
    return _result_to_envelope(await _run(cmd, timeout=RUN_TIMEOUT))


@mcp.tool()
async def stop_app(app_name: str) -> str:
    """Stop a deployed Modal app. Destructive — you'll need to redeploy.

    Args:
        app_name: Deployment name.
    """
    try:
        validate_resource_name(app_name, "app_name")
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "app", "stop", app_name, "--yes"]))


@mcp.tool()
async def app_logs(app_name: str) -> str:
    """Get a pointer to logs for a deployed app.

    Modal CLI doesn't expose a stable `app logs` subcommand in all versions, so
    we surface the dashboard URL alongside the current app listing.

    Args:
        app_name: Deployment name.
    """
    try:
        validate_resource_name(app_name, "app_name")
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))
    listing = await _run([modal, "app", "list"])
    if listing.get("returncode") != 0:
        # Don't masquerade an authentication or transport failure as success;
        # surface the real error to the caller.
        return _result_to_envelope(listing)
    return _ok(
        {
            "listing": redact(listing.get("stdout", "")),
            "dashboard_url": f"https://modal.com/apps/{app_name}",
            "tip": "Use `modal run --detach` so logs stay visible on the dashboard.",
        }
    )


# ── Tools: Shell & Containers ────────────────────────────────────────────────
@mcp.tool()
async def shell(
    gpu: str | None = None,
    image: str | None = None,
    cpu: float | None = None,
    memory: int | None = None,
    cmd: str | None = None,
) -> str:
    """Launch a Modal container shell or run a single command in one.

    Args:
        gpu: One of T4, A10G, A100, L4, H100 (case-insensitive).
        image: Image name (alnum + `_.:-/`, <=128 chars).
        cpu: 0.1..32.0.
        memory: 128..262144 MB.
        cmd: One-line non-interactive command (<=4 KB, no NUL).
    """
    try:
        if gpu is not None:
            validate_choice(gpu.upper(), ("T4", "A10G", "A100", "L4", "H100"), "gpu")
        if image is not None:
            import re as _re

            if (
                not isinstance(image, str)
                or len(image) > 128
                or "\x00" in image
                or any(ord(c) < 0x20 for c in image)
                or not _re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.\-:/]*", image)
            ):
                raise ValidationError(
                    "image must match OCI ref [a-zA-Z0-9][a-zA-Z0-9_.:-/]+ (<=128 chars, no controls)"
                )
        if cpu is not None and not (0.1 <= float(cpu) <= 32.0):
            raise ValidationError("cpu must be in [0.1, 32.0]")
        if memory is not None:
            validate_int_range(memory, "memory", minimum=128, maximum=262144)
        if cmd is not None and (len(cmd) > 4096 or "\x00" in cmd):
            raise ValidationError("cmd must be <=4KB without NUL")
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))

    shell_cmd = [modal, "shell"]
    if gpu:
        shell_cmd += ["--gpu", gpu.upper()]
    if image:
        shell_cmd += ["--image", image]
    if cpu is not None:
        shell_cmd += ["--cpu", str(cpu)]
    if memory is not None:
        shell_cmd += ["--memory", str(memory)]

    if cmd:
        shell_cmd += ["--cmd", cmd]
        return _result_to_envelope(await _run(shell_cmd, timeout=DEPLOY_TIMEOUT))
    return _ok(
        {
            "interactive_required": True,
            "run_in_terminal": " ".join(shell_cmd),
            "hint": "Pass `cmd` for a non-interactive run, or invoke this command directly in your shell.",
        }
    )


@mcp.tool()
async def list_containers() -> str:
    """List currently running Modal containers."""
    try:
        modal = _modal_bin()
    except RuntimeError as exc:
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "container", "list"]))


# ── Tools: Volumes ────────────────────────────────────────────────────────────
@mcp.tool()
async def list_volumes() -> str:
    """List all Modal volumes."""
    try:
        modal = _modal_bin()
    except RuntimeError as exc:
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "volume", "list"]))


@mcp.tool()
async def create_volume(name: str) -> str:
    """Create a new Modal volume.

    Args:
        name: Volume name (alnum + `_.-`, <=64 chars).
    """
    try:
        validate_resource_name(name, "name")
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "volume", "create", name]))


@mcp.tool()
async def volume_ls(volume_name: str, path: str = "/") -> str:
    """List files in a Modal volume.

    Args:
        volume_name: Volume name.
        path: Directory inside the volume.
    """
    try:
        validate_resource_name(volume_name, "volume_name")
        validate_safe_path(path, "path", allow_absolute=True)
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "volume", "ls", volume_name, path]))


@mcp.tool()
async def volume_put(volume_name: str, local_path: str, remote_path: str = "/") -> str:
    """Upload a file to a Modal volume.

    Args:
        volume_name: Volume name.
        local_path: Local file path (must exist).
        remote_path: Destination inside the volume.
    """
    try:
        validate_resource_name(volume_name, "volume_name")
        validate_safe_path(local_path, "local_path", must_exist=True)
        validate_safe_path(remote_path, "remote_path", allow_absolute=True)
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(
        await _run([modal, "volume", "put", volume_name, local_path, remote_path], timeout=DEPLOY_TIMEOUT)
    )


@mcp.tool()
async def volume_get(volume_name: str, remote_path: str, local_path: str) -> str:
    """Download a file from a Modal volume.

    Args:
        volume_name: Volume name.
        remote_path: File path inside the volume.
        local_path: Local destination path.
    """
    try:
        validate_resource_name(volume_name, "volume_name")
        validate_safe_path(remote_path, "remote_path", allow_absolute=True)
        validate_safe_path(local_path, "local_path", allow_absolute=True)
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(
        await _run([modal, "volume", "get", volume_name, remote_path, local_path], timeout=DEPLOY_TIMEOUT)
    )


@mcp.tool()
async def delete_volume(volume_name: str) -> str:
    """Delete a Modal volume. CANNOT BE UNDONE.

    Args:
        volume_name: Volume name.
    """
    try:
        validate_resource_name(volume_name, "volume_name")
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "volume", "delete", volume_name, "--yes"]))


# ── Tools: Secrets ────────────────────────────────────────────────────────────
@mcp.tool()
async def list_secrets() -> str:
    """List all Modal secrets."""
    try:
        modal = _modal_bin()
    except RuntimeError as exc:
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "secret", "list"]))


@mcp.tool()
async def create_secret(name: str, key_values: dict[str, str]) -> str:
    """Create a Modal secret.

    Args:
        name: Secret name (alnum + `_.-`, <=64 chars).
        key_values: Dict of POSIX env-var keys to values. Max 32 entries; each value <=4KB.
    """
    try:
        validate_resource_name(name, "name")
        if not isinstance(key_values, dict) or not key_values:
            raise ValidationError("key_values must be a non-empty dict")
        if len(key_values) > 32:
            raise ValidationError("key_values must have <=32 entries")
        for k, v in key_values.items():
            validate_env_key(k, "key_values key")
            if not isinstance(v, str) or len(v) > 4096 or "\x00" in v:
                raise ValidationError(f"key_values[{k}] must be a string <=4KB without NUL")
        modal = _modal_bin()
    except (ValidationError, RuntimeError) as exc:
        if isinstance(exc, ValidationError):
            return _validation_error(exc)
        return _err("modal_cli_missing", None, str(exc))

    cmd = [modal, "secret", "create", name]
    for k, v in key_values.items():
        cmd.append(f"{k}={v}")
    return _result_to_envelope(await _run(cmd))


# ── Tools: Environment & Config ──────────────────────────────────────────────
@mcp.tool()
async def list_environments() -> str:
    """List Modal environments."""
    try:
        modal = _modal_bin()
    except RuntimeError as exc:
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "environment", "list"]))


@mcp.tool()
async def check_config() -> str:
    """Show the Modal CLI's current config (workspace, env, token status)."""
    try:
        modal = _modal_bin()
    except RuntimeError as exc:
        return _err("modal_cli_missing", None, str(exc))
    return _result_to_envelope(await _run([modal, "config", "show"]))


@mcp.tool()
async def open_dashboard() -> str:
    """Return Modal dashboard URLs."""
    return _ok(
        {
            "apps": "https://modal.com/apps",
            "billing": "https://modal.com/settings/billing",
            "secrets": "https://modal.com/secrets",
            "storage": "https://modal.com/storage",
        }
    )


# ── Entry point ──────────────────────────────────────────────────────────────
def main() -> None:
    log.info("Starting aish-modal MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
