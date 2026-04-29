# SUBMISSION.md — `aish` v0.1.0

> One-page checklist for the Anthropic plugin marketplace reviewer.

This document maps every acceptance criterion in [`ANTHROPIC-PLUGIN.md`](../ANTHROPIC-PLUGIN.md) to the file:line where it is implemented. Reviewers can verify each row in seconds.

## Plugin contract

| Requirement | Source | Status |
| --- | --- | --- |
| `.claude-plugin/plugin.json` exists with required fields | `.claude-plugin/plugin.json:1` | ✅ name, version, description, author, license, repository, keywords |
| `.claude-plugin/marketplace.json` exists for self-hosted install | `.claude-plugin/marketplace.json:1` | ✅ owner, metadata, plugins, `strict: true` |
| `.mcp.json` bundles all MCP servers via `${CLAUDE_PLUGIN_ROOT}` | `.mcp.json:1` | ✅ aish-tensordock + aish-modal, env-allowlist only |
| LICENSE = MIT (SPDX) | `LICENSE:1` | ✅ |
| README with install/usage/security | `README.md:1` | ✅ banner, 3 install paths, env-var table, 3 examples, security summary |

## STOP-SHIP security checklist (8 items, [`ANTHROPIC-PLUGIN.md` §3](../ANTHROPIC-PLUGIN.md#3-stop-ship-security-checklist))

| # | Item | Implementation | Verification |
| --- | --- | --- | --- |
| 1 | No `shell=True` anywhere | `aish_mcp/modal_mcp_server.py:90` (`asyncio.create_subprocess_exec`) | `tests/test_no_shell_true.py:14` (regex meta-test) + CI grep |
| 2 | Bearer tokens redacted in every error path | `aish_mcp/_redact.py:16-21` (5 redaction patterns) | `tests/test_redact.py:8-58` (9 tests) |
| 3 | Strict input validation at every tool boundary | `aish_mcp/_validation.py:1-117` (UUID/name/path/range/enum) | `tests/test_validation.py:1-145` (38 cases) |
| 4 | Hard timeouts + `proc.kill()` on subprocess | `aish_mcp/modal_mcp_server.py:95-104` | `tests/test_modal.py:88-101` (timeout + kill assertion) |
| 5 | Env-var-only secrets + startup validation | `aish_mcp/tensordock_mcp_server.py:60-67` (`_api_token()` raises) | `.gitignore:3-9` blocks `.env`/`*.pem`/`*.token`; `.env.example` is the only `.env*` file in repo |
| 6 | `pip-audit` + `bandit` blocking in CI | `.github/workflows/ci.yml:31-36` (bandit), `:50-66` (pip-audit job) | bandit `LOW: 6, MEDIUM: 0, HIGH: 0` locally |
| 7 | No `PreToolUse` input-mutation hooks; no `CLAUDE_ENV_FILE` writes | No `hooks/` directory shipped | `ANTHROPIC-PLUGIN.md:96-105` decision |
| 8 | `SessionStart` hook absent — install side-effect-free | No `hooks/` directory shipped | `ANTHROPIC-PLUGIN.md:96-105` decision |

## MCP server controls (13 items, [`ANTHROPIC-PLUGIN.md` §4](../ANTHROPIC-PLUGIN.md#4-mcp-server-security-per-official-spec-2025-06-18))

| # | Control | Where |
| --- | --- | --- |
| 4.1 | UUID/name/path/range validators at boundary | `aish_mcp/_validation.py` (entire module) |
| 4.2 | Path traversal guard (`..`, NUL, control chars) | `aish_mcp/_validation.py:73-100` |
| 4.3 | `asyncio.create_subprocess_exec(*argv)` only | `aish_mcp/modal_mcp_server.py:90` |
| 4.4 | `shutil.which("modal")`; reject if not found | `aish_mcp/modal_mcp_server.py:73-81` |
| 4.5 | Subprocess timeout + kill + await on `TimeoutError` | `aish_mcp/modal_mcp_server.py:95-104` |
| 4.6 | httpx hard timeouts; AsyncClient as context manager | `aish_mcp/tensordock_mcp_server.py:135` |
| 4.7 | Strip `Authorization` / `X-API-*` from errors | `aish_mcp/_redact.py:16-21,39-60` |
| 4.8 | Catch `httpx.HTTPStatusError`; never `repr(exc)` | `aish_mcp/tensordock_mcp_server.py:88-130` (`_classify`) |
| 4.9 | HTTPS enforced; `follow_redirects=False` (SSRF) | `aish_mcp/tensordock_mcp_server.py:135` |
| 4.10 | Stdio transport only | `mcp.run()` defaults; no HTTP code in server |
| 4.11 | Cap response size returned to model | `aish_mcp/tensordock_mcp_server.py:240` (`hostnodes[:20]`) |
| 4.12 | Treat upstream responses as untrusted text | All tool returns wrapped in `_ok()` JSON envelope |
| 4.13 | No token-passthrough — env-var-only credentials | `_api_token()` is the only token reader |

## Tests (≥70% coverage gate, all green)

```text
$ pytest --cov
.........................................................................
.......
79 passed in 0.27s
```

Test files:
- `tests/test_validation.py` — 38 cases across UUID, resource name, path, numeric, env key, GPU model, choice
- `tests/test_redact.py` — 9 cases for bearer/HF/hex/header redaction + idempotence
- `tests/test_no_shell_true.py` — 2 meta-tests asserting `shell=True` and `os.system(` are absent in shipped code
- `tests/test_tensordock.py` — happy paths, validation rejection, 401/503 classification, token redaction in errors, missing-token surface
- `tests/test_modal.py` — happy paths, missing CLI, path traversal rejection, GPU enum rejection, env-key validation, timeout-with-zombie-kill
- `tests/conftest.py` — autouse fixture scrubs production credentials so a stray real call fails closed

## Continuous integration

| Workflow | What it does |
| --- | --- |
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | py3.11 + py3.12 matrix → ruff → bandit → pytest+cov → shell=True grep → pip-audit (separate job) → plugin-manifest validation (separate job) |
| [`.github/workflows/codeql.yml`](../.github/workflows/codeql.yml) | weekly + on-PR Python security-extended scan |
| [`.github/dependabot.yml`](../.github/dependabot.yml) | weekly pip + github-actions updates |

## Documentation surface

- `README.md` — banner, install (3 paths), env-var table, 3 worked examples, security summary, license
- `CLAUDE.md` — working agreement for in-repo agents (8 hard rules)
- `PLAN.md` — 9-phase roadmap with status markers
- `ANTHROPIC-PLUGIN.md` — full security/acceptance contract with decision log
- `SECURITY.md` — disclosure policy + safe-harbor + 90-day window
- `CONTRIBUTING.md` — local triad (ruff/bandit/pytest/pip-audit) before PR
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `docs/PRIOR-ART.md` — explicit accounting of what was carried over from AIsh, AIsh-v0, gpu-cloud-mcp; what was dropped and why

## Surface inventory

| Component | Count | Notes |
| --- | --- | --- |
| MCP servers | 2 | aish-tensordock (10 tools), aish-modal (18 tools) |
| Slash commands | 4 | `/aish:status`, `/aish:deploy-gpu`, `/aish:modal-run`, `/aish:hf-setup` |
| Subagents | 2 | `gpu-operator`, `ml-env-setup` — both with explicit `tools` whitelists, no blanket Bash |
| Skills | 2 | `gpu-detect` (with bundled `detect.py`), `hf-env-setup` |
| Hooks | 0 | Deliberately none — see ANTHROPIC-PLUGIN.md decision log |

## Provenance

`aish` consolidates three earlier prototypes — see [`docs/PRIOR-ART.md`](./PRIOR-ART.md) for the full per-file accounting:

- `lonexreb/aish-legacy` — scaffold, name only
- `lonexreb/AIsh-v0` — `hardware.py` GPU detection logic carried into `skills/gpu-detect/`; everything else (voice, multi-framework agents, TUI, monolithic main.py) deliberately deferred or dropped
- `lonexreb/gpu-cloud-mcp` — both MCP servers, the 29 v1 hardening requirements, the architecture description

## Submission

When ready: open the form at [`claude.ai/settings/plugins/submit`](https://claude.ai/settings/plugins/submit) (or [`platform.claude.com/plugins/submit`](https://platform.claude.com/plugins/submit)) and reference:

- Repo: `https://github.com/lonexreb/aish`
- Tag: `v0.1.0` (signed)
- This file: `https://github.com/lonexreb/aish/blob/main/docs/SUBMISSION.md`
