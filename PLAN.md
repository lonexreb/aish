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
| ✅ | `.mcp.json` referencing `${CLAUDE_PLUGIN_ROOT}/aish_mcp/*.py` with env-var passthrough only. |
| ✅ | `pyproject.toml` (Python 3.11–3.12, pinned httpx + mcp + modal, dev extras: pytest, respx, ruff, bandit, pip-audit). |
| ✅ | `.gitignore` blocks `.env`, `*.pem`, `*.token`, `*.key`, `~/.modal/`. |
| ✅ | `.env.example` with placeholder TENSORDOCK_API_TOKEN. |
| ✅ | `assets/banner.svg` original wordmark. |
| ✅ | `LICENSE` (MIT). |

---

## Phase 2 — Core docs ✅

| Done | Item |
| --- | --- |
| ✅ | `README.md` with banner, install steps, env-var table, examples, security summary. |
| ✅ | `CLAUDE.md` working-agreement file for in-repo agents. |
| ✅ | `PLAN.md` (this file). |
| ✅ | `ANTHROPIC-PLUGIN.md` — full best/secure-practices guide for marketplace acceptance. |
| ✅ | `SECURITY.md` — disclosure policy + reporting email + 90-day window. |
| ✅ | `CONTRIBUTING.md` — issue/PR flow, test/lint/audit commands. |
| ✅ | `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1. |
| ✅ | `docs/PRIOR-ART.md` — what was carried over from AIsh, AIsh-v0, gpu-cloud-mcp; what was dropped and why. |

---

## Phase 3 — Port MCP servers (TensorDock + Modal) ✅

| Done | Item |
| --- | --- |
| ✅ | Moved `tensordock_mcp_server.py` from `gpu-cloud-mcp` into `aish_mcp/`, validation per the 29 v1 requirements. |
| ✅ | Moved `modal_mcp_server.py` likewise; `_run()` uses `asyncio.create_subprocess_exec` with bounded per-tool timeouts. |
| ✅ | `aish_mcp/_validation.py` with shared validators (UUID, resource name, path, numeric range, env key, choice). |
| ✅ | `aish_mcp/_redact.py` with token-redaction helpers (incl. Modal `ak-`/`as-` after security review). |
| ✅ | `aish_mcp/_logging.py` for `AISH_LOG_LEVEL`-controlled stderr structured logging. |
| ✅ | Google-style docstrings on every `@mcp.tool()` — FastMCP exposes these as JSON schema. |
| ✅ | Every tool composes: validate → call → wrap error → return `_ok()`/`_err()` envelope. |

Acceptance signal: 29 v1 requirements verified against ported code; `bandit -r aish_mcp/` reports 0 MEDIUM/HIGH.

---

## Phase 4 — Skills ✅

| Done | Skill | What it does |
| --- | --- | --- |
| ✅ | `gpu-detect` | NVIDIA via `nvidia-smi`, macOS via `system_profiler`, Apple Silicon, simulated fallback, CUDA capability lookup (carries `hardware.py` logic from AIsh-v0). |
| ✅ | `hf-env-setup` | HuggingFace identifier → license/gating check + recommended Python/torch/CUDA + Modal scaffold. |

Each skill is `skills/<name>/SKILL.md` plus optional helper script.

---

## Phase 5 — Slash commands & subagents ✅

Slash commands (flat `.md` in `commands/`):

- ✅ `/aish:status` — health check across both providers
- ✅ `/aish:deploy-gpu` — guided GPU provisioning
- ✅ `/aish:modal-run` — one-line Modal function execution
- ✅ `/aish:hf-setup` — HF model/dataset env setup

Subagents (`.md` with YAML frontmatter in `agents/`):

- ✅ `gpu-operator` — capacity planning, hostnode selection, cost optimization. `tools` whitelist: `mcp__aish-tensordock__*`, no bash.
- ✅ `ml-env-setup` — environment bring-up, version pinning, verification. `tools`: `mcp__aish-modal__*` plus read-only `mcp__aish-tensordock__list_*`, no bash.

---

## Phase 6 — Tests, CI, security tooling ✅ (release.yml deferred)

| Done | Item |
| --- | --- |
| ✅ | `tests/test_tensordock.py` — respx-mocked httpx, classification, validation, redaction. |
| ✅ | `tests/test_modal.py` — subprocess-mocked, timeouts, non-zero exits, missing CLI. |
| ✅ | `tests/test_tools_smoke.py` — 30 round-trip tests across every public tool. |
| ✅ | `tests/test_validation.py` + `tests/test_redact.py` + `tests/test_no_shell_true.py`. |
| ✅ | 113 tests passing, ≥70% coverage gate, ruff + bandit clean. |
| ✅ | `.github/workflows/ci.yml` — matrix py3.11/3.12 → ruff → bandit → pytest+cov → pip-audit → manifest validation. |
| ⏳ | `.github/workflows/release.yml` — tag-triggered SBOM + provenance attestation. (deferred to v0.2 — current release flow uses gh release manually.) |
| ✅ | `.github/dependabot.yml` — weekly pip + actions updates (already filed PRs after first push). |
| ✅ | `.github/workflows/codeql.yml` — weekly + on-PR security-extended scan. |
| ✅ | `scripts/test.sh`, `scripts/audit.sh` — local entry points. (`scripts/lint.sh` not created — `ruff check .` is shorter.) |
| ✅ | `.github/ISSUE_TEMPLATE/{bug_report.md,feature_request.md,security.md}` + `PULL_REQUEST_TEMPLATE.md`. |

---

## Phase 7 — Submission packet ✅ (signed tag deferred)

| Done | Item |
| --- | --- |
| ✅ | `docs/SUBMISSION.md` — file:line citations for every acceptance row. |
| ⚠️ | Tag `v0.1.0` cut and pushed; **annotated, not GPG-signed** — `git tag -s` deferred until a key is provisioned. |
| ✅ | GitHub Release published with changelog. SBOM attached in v0.2. |
| ⏳ | Submit via `claude.ai/settings/plugins/submit` referencing the v0.1.0 release. |
| ⏳ | Open a tracking issue for any review feedback. |

---

## Phase 8 — Post-acceptance hardening (v0.2)

- Retry-with-backoff on transient TensorDock 5xx (per gpu-cloud-mcp REL-01..05).
- `--json` output parsing for Modal CLI (verify availability first — open question from prior research).
- `release.yml` workflow with cyclonedx SBOM and GitHub artifact attestations.
- Hash-pinned dependencies via `uv pip compile --generate-hashes`.
- GPG-signed git tags (provision key, then `git tag -s` for v0.2).
- `validate_safe_path` callers add `Path.resolve().is_relative_to(allowed_root)` for symlink safety.
- `create_secret` switches to `--from-json=<tempfile>` to avoid `ps aux` argv exposure.
- Optional `gpu-cost-optimizer` subagent comparing TensorDock vs Modal price points.

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
