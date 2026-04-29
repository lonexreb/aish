"""Validation-layer tests."""

from __future__ import annotations

import pytest

from aish_mcp._validation import (
    ValidationError,
    validate_choice,
    validate_env_key,
    validate_gpu_model,
    validate_int_range,
    validate_resource_name,
    validate_safe_path,
    validate_uuid,
)


class TestUUID:
    def test_canonical_uuid_passes(self):
        assert validate_uuid("550e8400-e29b-41d4-a716-446655440000") == (
            "550e8400-e29b-41d4-a716-446655440000"
        )

    def test_uppercase_uuid_passes(self):
        validate_uuid("550E8400-E29B-41D4-A716-446655440000")

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "not-a-uuid",
            "550e8400-e29b-41d4-a716",
            "550e8400-e29b-41d4-a716-44665544000g",
            "550e8400-e29b-41d4-a716-446655440000-extra",
            "../../etc/passwd",
            None,
            123,
        ],
    )
    def test_garbage_rejected(self, bad):
        with pytest.raises(ValidationError):
            validate_uuid(bad)


class TestResourceName:
    @pytest.mark.parametrize("name", ["my-app", "App_1", "x", "a.b-c_d", "A" * 64])
    def test_ok(self, name):
        validate_resource_name(name)

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "-leading-dash",
            ".leading-dot",
            "_leading-underscore",
            "has space",
            "has/slash",
            "has;semicolon",
            "$inject",
            "name`with`backticks",
            "A" * 65,
            None,
        ],
    )
    def test_rejects_garbage(self, bad):
        with pytest.raises(ValidationError):
            validate_resource_name(bad)


class TestPath:
    def test_basic_relative_passes(self):
        assert validate_safe_path("dir/file.py") == "dir/file.py"

    def test_absolute_when_allowed(self):
        validate_safe_path("/tmp/foo", allow_absolute=True)

    def test_absolute_rejected_when_disallowed(self):
        with pytest.raises(ValidationError):
            validate_safe_path("/etc/passwd", allow_absolute=False)

    def test_traversal_rejected(self):
        with pytest.raises(ValidationError):
            validate_safe_path("../etc/passwd")

    def test_nul_rejected(self):
        with pytest.raises(ValidationError):
            validate_safe_path("file\x00.py")

    def test_control_chars_rejected(self):
        with pytest.raises(ValidationError):
            validate_safe_path("file\x07.py")

    def test_empty_rejected(self):
        with pytest.raises(ValidationError):
            validate_safe_path("")


class TestNumeric:
    def test_in_range(self):
        assert validate_int_range(5, "x", minimum=1, maximum=10) == 5

    def test_below_min(self):
        with pytest.raises(ValidationError):
            validate_int_range(0, "x", minimum=1, maximum=10)

    def test_above_max(self):
        with pytest.raises(ValidationError):
            validate_int_range(11, "x", minimum=1, maximum=10)

    def test_bool_rejected(self):
        # `bool` is `int` in Python — extra guard keeps `True` from sneaking through
        with pytest.raises(ValidationError):
            validate_int_range(True, "x", minimum=0, maximum=2)


class TestGpuModel:
    @pytest.mark.parametrize("v", ["h100-sxm5-80gb", "geforcertx4090-pcie-24gb", "L4"])
    def test_ok(self, v):
        validate_gpu_model(v)

    def test_rejects_bad(self):
        with pytest.raises(ValidationError):
            validate_gpu_model("$rm -rf")


class TestEnvKey:
    @pytest.mark.parametrize("k", ["HF_TOKEN", "WANDB_API_KEY", "_X", "A1"])
    def test_ok(self, k):
        validate_env_key(k)

    @pytest.mark.parametrize("k", ["lower_case", "1LEADING_DIGIT", "HAS-DASH", "HAS SPACE", ""])
    def test_rejects(self, k):
        with pytest.raises(ValidationError):
            validate_env_key(k)


class TestChoice:
    def test_match(self):
        assert validate_choice("a", ("a", "b"), "x") == "a"

    def test_miss(self):
        with pytest.raises(ValidationError):
            validate_choice("c", ("a", "b"), "x")
