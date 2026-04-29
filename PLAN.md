# PLAN.md — aish

> Phased roadmap from a fresh repo to an Anthropic-marketplace-accepted Claude Code plugin.

This document lives next to the code so any future agent (human or Claude) can resume execution without losing intent. Update phase status as work lands. The phase that is currently in flight is marked `▶ in progress`.

---

## North star

Ship a Claude Code plugin that:

1. Installs cleanly via `/plugin install aish@<marketplace>` and exposes working `aish-tensordock` + `aish-modal` MCP servers, four slash commands, two skills, and two subagents.
2. Passes Anthropic's automated marketplace validation and survives a manual security review without rework.
3. Is good enough that an outside developer can fork it and submit their own provider plugin without rebuilding the security/test/CI scaffolding.

---

## Phase 0 — Research & decisions ✅

| Done | Item |
| --- | --- |
| ✅ | Read official plugin spec (`code.claude.com/docs/en/plugins`, `plugins-reference`, `plugin-marketplaces`, `hooks`). |
| ✅ | Survey 6+ public plugins for `plugin.json` shape, README conventions, MCP-bundling patterns. Closest analog: `ZeframLou/call-me`. |
| ✅ | Compile MCP security spec (`modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices`). |
| ✅ | Compile Python supply-chain practices (pip-audit, bandit, gitleaks, hash-pinning, signed tags). |
| ✅ | Lock v1 scope: defer voice + LangChain/CrewAI/uAgents from AIsh-v0 to v2. License = MIT. Repo = `lonexreb/aish` public. |

Outputs: [`ANTHROPIC-PLUGIN.md`](./ANTHROPIC-PLUGIN.md), [`docs/PRIOR-ART.md`](./docs/PRIOR-ART.md).

---

## Phase 1 — Plugin scaffold ✅

| Done | Item |
| --- | --- |
| ✅ | `.claude-plugin/plugin.json` (name, version, description, author, license, repository, keywords). |
| ✅ | `.claude-plugin/marketplace.json` (single-plugin marketplace, strict mode). |
| ✅ | `.mcp.json` referencing `${CLAUDE_PLUGIN_ROOT}/mcp/*.py` with env-var passthrough only. |
| ✅ | `pyproject.toml` (Python 3.11–3.12, pinned httpx + mcp + modal, dev extras: pytest, respx, ruff, bandit, pip-audit). |
| ✅ | `.gitignore` blocks `.env`, `*.pem`, `*.token`, `*.key`, `~/.modal/`. |
| ✅ | `.env.example` with placeholder TENSORDOCK_API_TOKEN. |
| ✅ | `assets/banner.svg` original wordmark. |
| ✅ | `LICENSE` (MIT). |

---

## Phase 2 — Core docs ▶ in progress

| Done | Item |
| --- | --- |
| ✅ | `README.md` with banner, install steps, env-var table, examples, security summary. |
| ✅ | `CLAUDE.md` working-agreement file for in-repo agents. |
| ✅ | `PLAN.md` (this file). |
| ⏳ | `ANTHROPIC-PLUGIN.md` — full best/secure-practices guide for marketplace acceptance. |
| ⏳ | `SECURITY.md` — disclosure policy + reporting email + 90-day window. |
| ⏳ | `CONTRIBUTING.md` — issue/PR flow, test/lint/audit commands. |
| ⏳ | `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1. |
| ⏳ | `docs/PRIOR-ART.md` — what was carried over from AIsh, AIsh-v0, gpu-cloud-mcp; what was dropped and why. |

---

## Phase 3 — Port MCP servers (TensorDock + Modal)

| Item |
| --- |
| Move `tensordock_mcp_server.py` from `gpu-cloud-mcp` into `mcp/`, add input validation per the 29 testable requirements (ERR-01 → QAL-04 in the original `REQUIREMENTS.md`). |
| Move `modal_mcp_server.py` likewise; ensure `_run()` uses `asyncio.create_subprocess_exec` (already does), add stricter timeout-tier table per tool. |
| Add `mcp/_validation.py` with shared validators (UUID, resource name, path, numeric range). |
| Add `mcp/_redact.py` with token-redaction helpers; wrap every error path. |
| Add tool-level docstrings in Google style — FastMCP turns these into the JSON schema users see. |
| Each tool must compose: `validate inputs → call → wrap error → return json.dumps(...)`. |

Acceptance signal for this phase: the existing 29 v1 requirements all pass when re-read against the ported code, and `bandit -r mcp/` is clean.

---

## Phase 4 — Skills

| Skill | What it does |
| --- | --- |
| `gpu-detect` | Port `hardware.py` from AIsh-v0 — NVIDIA via `nvidia-smi`, macOS via `system_profiler`, Apple Silicon, simulated fallback, CUDA capability lookup. |
| `hf-env-setup` | Walk a HuggingFace model/dataset URL → recommend Python/CUDA/torch versions, generate a Modal app spec. |

Each skill: `skills/<name>/SKILL.md` + a small Python helper in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

---

## Phase 5 — Slash commands & subagents

Slash commands (flat `.md` in `commands/`):

- `/aish:status` — health check across both providers
- `/aish:deploy-gpu` — guided GPU provisioning
- `/aish:modal-run` — one-line Modal function execution
- `/aish:hf-setup` — HF model/dataset env setup

Subagents (`.md` with YAML frontmatter in `agents/`):

- `gpu-operator` — capacity planning, hostnode selection, cost optimization. `tools` whitelist: `mcp:aish-tensordock:*`, no bash.
- `ml-env-setup` — environment bring-up, version pinning, verification. `tools`: `mcp:aish-modal:*`, `mcp:aish-tensordock:list_*`, no bash.

---

## Phase 6 — Tests, CI, security tooling

| Item |
| --- |
| `tests/test_tensordock.py` — unit tests for all 10 tools with `respx`-mocked httpx. Cover happy paths, 4xx classification, 5xx retries (if added), token redaction in errors. |
| `tests/test_modal.py` — unit tests for all 18 tools with mocked `asyncio.create_subprocess_exec`. Cover timeouts, non-zero exits, missing `modal` binary. |
| `tests/test_validation.py` — UUID / path / resource name / numeric validators. |
| `tests/test_redact.py` — token redaction in error strings. |
| `.github/workflows/ci.yml` — matrix py3.11/3.12 → ruff → bandit → pytest with `--cov` (fail under 70%) → `pip-audit`. |
| `.github/workflows/release.yml` — tag-triggered, signs tag verification, generates SBOM (`cyclonedx-py`), creates GitHub Release with provenance attestation. |
| `.github/dependabot.yml` — weekly pip ecosystem updates. |
| `scripts/lint.sh`, `scripts/test.sh`, `scripts/audit.sh` — single-command developer entry points. |
| `.github/ISSUE_TEMPLATE/{bug_report.md,feature_request.md,security.md}`. |
| `.github/PULL_REQUEST_TEMPLATE.md`. |

---

## Phase 7 — Submission packet

| Item |
| --- |
| `docs/SUBMISSION.md` — checklist of how `aish` meets each item in `ANTHROPIC-PLUGIN.md` (with file:line citations). |
| Tag `v0.1.0`, signed (`git tag -s`). |
| GitHub Release with attached SBOM and a short changelog. |
| Submit via `claude.ai/settings/plugins/submit` (or `platform.claude.com/plugins/submit`) referencing the v0.1.0 release. |
| Open a tracking issue on this repo for any review feedback. |

---

## Phase 8 — Post-acceptance hardening (v0.2)

- Add retry-with-backoff on transient TensorDock 5xx (per gpu-cloud-mcp REL-01..05).
- Add `--json` output parsing for Modal CLI (verify availability first — open question from prior research).
- Add structured logging via `logging` (not print) so `AISH_LOG_LEVEL` actually works end-to-end.
- Optional `gpu-cost-optimizer` subagent that compares TensorDock vs Modal price points.

---

## Phase 9 — Reactivate the deferred AIsh-v0 surface (v1.0)

Only after v0.x is accepted and stable:

- `voice` skill: opt-in, ships as a separate plugin (`aish-voice`) so the core stays small.
- Multi-framework agent adapters: only if there's user demand — Claude Code subagents already cover most cases.

---

## Cadence & decision log

- Commit frequently; conventional commits; push after each logical change.
- Anything that changes a security control requires an entry in `ANTHROPIC-PLUGIN.md` decision log.
- This `PLAN.md` is the single source of truth — update phase markers as work lands.
