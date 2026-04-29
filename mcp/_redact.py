"""Redaction helpers.

Bearer tokens, API keys, and equivalent credentials must never appear in
strings returned to the model. Use these helpers to wrap any error path
before returning text to the FastMCP framework.

See ANTHROPIC-PLUGIN.md §3 (STOP-SHIP item 2) and §6 (Secrets & credentials).
"""

from __future__ import annotations

import re

# Patterns that match common secret formats. These are intentionally broad —
# false-positive redaction is fine; the cost of a missed secret is high.
_BEARER_RE = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-+/=]{8,}")
_TOKEN_RE = re.compile(r"\b(tdk|sk|hf|wandb|gho|ghp|ghs|ghu|github_pat)_[A-Za-z0-9_\-]{16,}")
_GENERIC_LONG_HEX_RE = re.compile(r"\b[A-Fa-f0-9]{32,}\b")
_HEADER_VALUE_RE = re.compile(
    r"(?i)(x-api[-_](?:key|token)|api[-_]key|secret[-_]key)\s*:\s*\S+"
)


def redact(text: str) -> str:
    """Return `text` with likely secrets replaced by '***REDACTED***'.

    Idempotent — redact(redact(x)) == redact(x).
    """
    if not isinstance(text, str):
        text = str(text)
    text = _BEARER_RE.sub(r"\1***REDACTED***", text)
    text = _HEADER_VALUE_RE.sub(r"\1: ***REDACTED***", text)
    text = _TOKEN_RE.sub("***REDACTED***", text)
    text = _GENERIC_LONG_HEX_RE.sub("***REDACTED***", text)
    return text


def redact_dict(d: dict) -> dict:
    """Shallow redaction of suspicious keys in a dict (for logging headers)."""
    sensitive_keys = {
        "authorization",
        "api-key",
        "api_key",
        "x-api-key",
        "x-api-token",
        "secret",
        "secret-key",
        "secret_key",
        "token",
        "tensordock_api_token",
    }
    out: dict = {}
    for k, v in d.items():
        if str(k).lower() in sensitive_keys:
            out[k] = "***REDACTED***"
        elif isinstance(v, str):
            out[k] = redact(v)
        else:
            out[k] = v
    return out
