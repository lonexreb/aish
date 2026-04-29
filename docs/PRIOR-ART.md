# Prior art — what was carried into aish, what was dropped

`aish` is the consolidation of three earlier prototypes. This document records what was carried over, what was dropped, and the reasoning. Reviewers and future contributors should read this before suggesting we resurrect any of the dropped pieces.

## Sources

| Repo | Last push | Status before consolidation |
| --- | --- | --- |
| [`lonexreb/aish-legacy`](https://github.com/lonexreb/aish-legacy) (renamed from `lonexreb/aish`) | 2025-03-08 | Scaffold only (~1.4 KB Python). Clean-architecture skeleton, no real implementation. |
| [`lonexreb/AIsh-v0`](https://github.com/lonexreb/AIsh-v0) | 2025-03-11 | ~416 KB Python. Substantive: GPU detection (`hardware.py`, 297 lines), monolithic `main.py` (1591 lines), partial multi-framework agent system, Textual TUI, voice integration (Hume AI). |
| [`lonexreb/gpu-cloud-mcp`](https://github.com/lonexreb/gpu-cloud-mcp) | 2026-04-13 | Two FastMCP servers (TensorDock REST + Modal CLI), in hardening milestone. 29 testable v1 requirements defined in `REQUIREMENTS.md`. |

## Carried over

### From `gpu-cloud-mcp`

- **`tensordock_mcp_server.py`** — moved into `mcp/`, hardened against the 29 v1 requirements (UUID/path/range validation, token redaction, classified error handling).
- **`modal_mcp_server.py`** — moved into `mcp/`, same hardening pass.
- **The 29 v1 requirements** themselves (ERR-01..05, VAL-01..05, TST-01..06, SEC-01..04, REL-01..05, QAL-01..04) — they're the acceptance criteria for [phase 3 in `PLAN.md`](../PLAN.md#phase-3--port-mcp-servers-tensordock--modal).
- **The pinned dep philosophy** (`httpx==0.27.x`, `mcp[cli]==1.x`).

### From `AIsh-v0`

- **`infrastructure/hardware.py`** — reshaped into the `gpu-detect` skill in `skills/gpu-detect/`. Same logic (NVIDIA via `nvidia-smi`, macOS via `system_profiler`, Apple Silicon, simulated fallback, CUDA capability map), but exposed as a Claude-Code-native skill rather than a Python class.
- **The agent-dispatch heuristic concept** (auto-routing commands by prefix and content) — re-implemented as `gpu-operator` and `ml-env-setup` subagents using Claude Code's native subagent system.
- **The HuggingFace integration intent** — `hf-env-setup` skill picks up where AIsh-v0 left off.

### From `aish-legacy`

- The package name `aish`. Nothing else; the scaffold was empty.

## Dropped

| Dropped | Reason |
| --- | --- |
| **`AIsh-v0/main.py`** (1591 lines) | Monolithic REPL entry point. The "REPL" is now Claude Code itself; we don't need a competing interactive shell. |
| **`AIsh-v0/tui/`** (Textual TUI) | Same reason. Claude Code is the TUI. |
| **`AIsh-v0/agents/langchain_engine.py`, `crew_agents.py`, `uagents_tasks.py`, `agent_manager.py`** | Multi-framework agent orchestration was the v0 thesis. Claude Code's native subagent system covers the same use cases without the dep tree (`langchain`, `crewai`, `uagents`). Re-introducing them as adapters is a v1.x decision documented in [`PLAN.md` phase 9](../PLAN.md#phase-9--reactivate-the-deferred-aish-v0-surface-v10). |
| **`AIsh-v0/voice/`, `infrastructure/voice.py`** (Hume AI integration) | Out of scope for a code plugin. Voice adds heavy native deps (`PyAudio`, `simpleaudio`, `hume==0.7.8`) and is hardware-dependent. If revived, it ships as a separate plugin (`aish-voice`). |
| **`AIsh-v0/ide/windsurf.py`** | Tied to a specific IDE that isn't Claude Code. |
| **`AIsh-v0/utils/package_manager.py`** | Wraps pip/PyPI lookups. Out of scope — Claude Code already has `Bash` and editing tools that handle this. |
| **`AIsh-v0/build_executable.py`** | PyInstaller bundling for a standalone exe. Not relevant when the artifact is a plugin loaded by Claude Code. |
| **`AIsh-v0/agentic_terminal/application/gpu_setup.py`, `infrastructure/installation.py`** | Empty stubs in the original. The intent (CUDA/cuDNN setup) is partially absorbed by `gpu-detect` skill; full installation orchestration is deferred. |

## Stylistic carryovers

- The Google-style docstrings in MCP tools come from `gpu-cloud-mcp`. FastMCP turns these into the JSON schema users see.
- The `_format_size` / `_run` / `_modal_bin` helper pattern from `gpu-cloud-mcp/modal_mcp_server.py` is preserved.
- The "tool layer / client layer / config layer" architecture description from `gpu-cloud-mcp/CLAUDE.md` is preserved as the architecture for `mcp/`.

## What this means for reviewers

Anything Anthropic might reasonably ask — "why isn't there a CLI launcher?", "why no LangChain?", "why no voice?" — has an answer in this document. The answers are deliberate choices, not oversights.
