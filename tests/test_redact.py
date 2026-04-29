"""Redaction-layer tests — bearer tokens and friends must never survive."""

from __future__ import annotations

from aish_mcp._redact import redact, redact_dict


def test_bearer_redacted():
    s = "Authorization: Bearer abcdefghij1234567890XYZ"
    assert "abcdefghij1234567890XYZ" not in redact(s)
    assert "***REDACTED***" in redact(s)


def test_tdk_token_redacted():
    s = "got 401 with TENSORDOCK_API_TOKEN=tdk_abcdefghijklmnopqrstuv expired"
    out = redact(s)
    assert "tdk_abcdefghijklmnopqrstuv" not in out
    assert "***REDACTED***" in out


def test_hf_token_redacted():
    # Construct at runtime so GitHub push-protection / secret-scanners don't see
    # a literal token-shaped string in the source file.
    fake = "hf_" + ("z" * 30)
    s = f"Header: {fake}"
    out = redact(s)
    assert fake not in out


def test_long_hex_redacted():
    s = "X-Trace: " + "a" * 64
    out = redact(s)
    assert "a" * 64 not in out


def test_xapi_header_redacted():
    s = "X-Api-Key: leakythingleakythingleakything"
    assert "leakything" not in redact(s)


def test_idempotent():
    s = "Authorization: Bearer abcdef1234567890"
    assert redact(redact(s)) == redact(s)


def test_redact_dict_sensitive_keys():
    d = {"Authorization": "Bearer secret123abc", "User-Agent": "claude"}
    out = redact_dict(d)
    assert out["Authorization"] == "***REDACTED***"
    assert out["User-Agent"] == "claude"


def test_redact_dict_redacts_values_containing_tokens():
    d = {"trace": "saw token tdk_abcdefghijklmnopqrstuv in logs"}
    out = redact_dict(d)
    assert "tdk_abcdefghijklmnopqrstuv" not in out["trace"]


def test_redact_handles_non_string():
    assert "***REDACTED***" not in redact(42)  # number passes through stringified
