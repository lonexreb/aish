#!/usr/bin/env python3
"""GPU detection helper for the gpu-detect skill.

Detects local GPU using platform-specific tools:
- NVIDIA: nvidia-smi (cross-platform, primary signal)
- macOS: system_profiler (Apple Silicon + discrete GPUs)
- Falls back to a clearly-marked simulated GPU when nothing is detected.

Dependency-free: stdlib only. Reads no env vars. Touches no network.
Adapted from AIsh-v0 infrastructure/hardware.py — flattened to one file.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess  # noqa: S404 — list-form argv only, no shell
import sys
from typing import Any

# Compute-capability lookup. Conservative: substring match on common SKUs.
_COMPUTE_CAPABILITY: dict[str, str] = {
    "H100": "9.0",
    "H200": "9.0",
    "A100": "8.0",
    "A40": "8.6",
    "A30": "8.0",
    "A10G": "8.6",
    "A10": "8.6",
    "L40": "8.9",
    "L4": "8.9",
    "Tesla T4": "7.5",
    "RTX 6000 Ada": "8.9",
    "RTX 5000 Ada": "8.9",
    "RTX 4090": "8.9",
    "RTX 4080": "8.9",
    "RTX 4070": "8.9",
    "RTX 4060": "8.9",
    "RTX 3090": "8.6",
    "RTX 3080": "8.6",
    "RTX 3070": "8.6",
    "RTX 3060": "8.6",
    "RTX 2080": "7.5",
    "RTX 2070": "7.5",
    "RTX 2060": "7.5",
    "GTX 1660": "7.5",
    "GTX 1650": "7.5",
    "GTX 1080": "6.1",
    "GTX 1070": "6.1",
    "GTX 1060": "6.1",
    "P100": "6.0",
    "V100": "7.0",
}


def _compute_capability(model: str) -> str | None:
    m = model.lower()
    for sku, cc in _COMPUTE_CAPABILITY.items():
        if sku.lower() in m:
            return cc
    return None


def _detect_nvidia() -> dict | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(  # nosec B603 B607  # noqa: S603 — list-form argv after which() guard
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    line = out.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2:
        return None
    model, mem_mib, driver = (parts + [None, None, None])[:3]
    try:
        memory_gb = round(float(mem_mib) / 1024.0, 2) if mem_mib else 0.0
    except ValueError:
        memory_gb = 0.0

    cuda_version = None
    nvcc = shutil.which("nvcc")
    if nvcc:
        try:
            nv_out = subprocess.run(  # nosec B603  # noqa: S603 — absolute path from shutil.which
                [nvcc, "--version"], capture_output=True, text=True, timeout=5, check=False
            )
            m = re.search(r"release\s+(\d+\.\d+)", nv_out.stdout or "")
            if m:
                cuda_version = m.group(1)
        except (subprocess.SubprocessError, OSError):
            pass

    return {
        "model": model,
        "memory_gb": memory_gb,
        "gpu_type": "NVIDIA",
        "cuda_capability": _compute_capability(model),
        "driver_version": driver,
        "cuda_version": cuda_version,
    }


def _detect_macos() -> dict | None:
    if platform.system() != "Darwin":
        return None
    if not shutil.which("system_profiler"):
        return None
    try:
        out = subprocess.run(  # nosec B603 B607  # noqa: S603 — list-form argv after which() guard
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if out.returncode != 0:
        return None

    text = out.stdout or ""
    model_match = re.search(r"Chipset Model:\s*([^\n]+)", text)
    if not model_match:
        return None
    model = model_match.group(1).strip()

    memory_gb = 0.0
    mem_match = re.search(r"VRAM \(Total\):\s*(\d+(?:\.\d+)?)\s*([MG]B)", text)
    if mem_match:
        val = float(mem_match.group(1))
        unit = mem_match.group(2).upper()
        memory_gb = val if unit == "GB" else round(val / 1024.0, 2)

    lower = model.lower()
    if any(k in lower for k in ("apple", "m1", "m2", "m3", "m4")):
        gpu_type = "APPLE"
    elif any(k in lower for k in ("nvidia", "geforce", "rtx", "gtx", "quadro")):
        gpu_type = "NVIDIA"
    elif any(k in lower for k in ("amd", "radeon")):
        gpu_type = "AMD"
    elif any(k in lower for k in ("intel", "iris")):
        gpu_type = "INTEL"
    else:
        gpu_type = "UNKNOWN"

    return {
        "model": model,
        "memory_gb": memory_gb,
        "gpu_type": gpu_type,
        "cuda_capability": None if gpu_type != "NVIDIA" else _compute_capability(model),
        "driver_version": None,
        "cuda_version": None,
    }


def _simulated() -> dict:
    return {
        "model": "Simulated NVIDIA RTX 4090",
        "memory_gb": 24.0,
        "gpu_type": "NVIDIA",
        "cuda_capability": "8.9",
        "driver_version": None,
        "cuda_version": None,
    }


def detect() -> dict[str, Any]:
    notes: list[str] = []
    gpu = _detect_nvidia()
    if gpu:
        notes.append("Detected via nvidia-smi.")
        return {
            "platform": platform.system(),
            "detected": True,
            "simulated": False,
            "gpu": gpu,
            "notes": notes,
        }
    gpu = _detect_macos()
    if gpu:
        notes.append("Detected via system_profiler.")
        return {
            "platform": platform.system(),
            "detected": True,
            "simulated": False,
            "gpu": gpu,
            "notes": notes,
        }
    notes.append(
        "No physical GPU detected (no nvidia-smi result and no macOS GPU info). "
        "Returning a simulated GPU so downstream planning can continue. "
        "Treat `simulated: true` as 'no GPU available locally — recommend cloud'."
    )
    return {
        "platform": platform.system(),
        "detected": False,
        "simulated": True,
        "gpu": _simulated(),
        "notes": notes,
    }


def main() -> int:
    print(json.dumps(detect(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
