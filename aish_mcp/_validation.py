"""Input validators for MCP tool boundaries.

Every external-facing parameter — anything that flows into an HTTP request,
subprocess argv, or filesystem path — must pass through one of these helpers
before it is used. See ANTHROPIC-PLUGIN.md §4 (MCP server security).
"""

from __future__ import annotations

import re
from pathlib import Path

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
RESOURCE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
GPU_MODEL_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")


class ValidationError(ValueError):
    """Raised when an MCP tool argument fails validation at the boundary."""


def validate_uuid(value: str, field: str = "id") -> str:
    """Reject anything that is not a canonical UUID."""
    if not isinstance(value, str) or not UUID_RE.match(value):
        raise ValidationError(f"{field} must be a UUID (got: {_truncate(value)!r})")
    return value


def validate_resource_name(value: str, field: str = "name") -> str:
    """Resource names: alnum + `_.-`, 1-64 chars, must start with alnum."""
    if not isinstance(value, str) or not RESOURCE_NAME_RE.match(value):
        raise ValidationError(
            f"{field} must match [a-zA-Z0-9][a-zA-Z0-9_.-]{{0,63}} (got: {_truncate(value)!r})"
        )
    return value


def validate_gpu_model(value: str, field: str = "gpu_model") -> str:
    """GPU model identifiers (e.g. 'h100-sxm5-80gb')."""
    if not isinstance(value, str) or not GPU_MODEL_RE.match(value):
        raise ValidationError(
            f"{field} must match [a-zA-Z0-9][a-zA-Z0-9_.-]{{0,127}} (got: {_truncate(value)!r})"
        )
    return value


def validate_env_key(value: str, field: str = "env_key") -> str:
    """POSIX-style env var keys."""
    if not isinstance(value, str) or not ENV_KEY_RE.match(value):
        raise ValidationError(
            f"{field} must be a POSIX env-var name (got: {_truncate(value)!r})"
        )
    return value


def validate_int_range(
    value: int,
    field: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Numeric range gate."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} must be an int (got: {type(value).__name__})")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{field} must be >= {minimum} (got: {value})")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} must be <= {maximum} (got: {value})")
    return value


def validate_safe_path(
    value: str,
    field: str = "path",
    *,
    allow_absolute: bool = True,
    must_exist: bool = False,
) -> str:
    """Reject paths with `..`, NUL bytes, or weird control chars.

    If `allow_absolute=False`, also reject absolute paths.
    Always returns the raw string — caller is responsible for resolving and
    re-checking against an allowed root via Path.resolve().is_relative_to(...)
    if it will be opened locally. This validator is a syntactic gate only.
    """
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{field} must be a non-empty string")
    if "\x00" in value:
        raise ValidationError(f"{field} contains a NUL byte")
    if any(ord(c) < 0x20 for c in value):
        raise ValidationError(f"{field} contains control characters")
    parts = Path(value).parts
    if ".." in parts:
        raise ValidationError(f"{field} contains '..' (path traversal)")
    if not allow_absolute and Path(value).is_absolute():
        raise ValidationError(f"{field} must be a relative path")
    if must_exist and not Path(value).exists():
        raise ValidationError(f"{field} does not exist: {_truncate(value)!r}")
    return value


def validate_choice(value: str, choices: tuple[str, ...], field: str) -> str:
    """Enum gate — value must be one of `choices`."""
    if value not in choices:
        raise ValidationError(
            f"{field} must be one of {choices} (got: {_truncate(value)!r})"
        )
    return value


def _truncate(value: object, limit: int = 64) -> str:
    """Render an offending value short enough for an error message without
    leaking the entire payload (which might contain a token by mistake)."""
    s = repr(value)
    if len(s) > limit:
        s = s[:limit] + "...(truncated)"
    return s
