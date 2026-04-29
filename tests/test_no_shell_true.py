"""STOP-SHIP guard: assert `shell=True` does not appear in shipped MCP code.

This is the explicit test referenced in ANTHROPIC-PLUGIN.md §3 STOP-SHIP item 1.
If a future change introduces `shell=True`, the build fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPPED_DIRS = (ROOT / "mcp", ROOT / "skills", ROOT / "scripts")
SHELL_TRUE_RE = re.compile(r"shell\s*=\s*True", re.IGNORECASE)


def test_no_shell_true_in_shipped_code() -> None:
    offenders: list[str] = []
    for d in SHIPPED_DIRS:
        if not d.exists():
            continue
        for path in d.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if SHELL_TRUE_RE.search(text):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        f"shell=True found in shipped code: {offenders}. "
        "Use list-form argv with create_subprocess_exec / subprocess.run instead."
    )


def test_no_os_system_in_shipped_code() -> None:
    offenders: list[str] = []
    for d in SHIPPED_DIRS:
        if not d.exists():
            continue
        for path in d.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"\bos\.system\(", text):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"os.system() found in shipped code: {offenders}"
