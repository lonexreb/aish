# SUBMISSION.md — `aish` v0.1.3

> One-page checklist for the Anthropic plugin marketplace reviewer.

This document maps every acceptance criterion in [`ANTHROPIC-PLUGIN.md`](../ANTHROPIC-PLUGIN.md) to the file:line where it is implemented. Reviewers can verify each row in seconds. Citations are kept in sync with the code in CI; if you spot drift, please [open an issue](https://github.com/lonexreb/aish/issues/new?template=bug_report.md).

## Plugin contract

| Requirement | Source | Status |
| --- | --- | --- |
| `.claude-plugin/plugin.json` exists with required fields | [`.claude-plugin/plugin.json`](../.claude-plugin/plugin.json) | ✅ name, version, description, author, license, repository, homepage, keywords |
| `.claude-plugin/marketplace.json` exists for self-hosted install | [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | ✅ owner, metadata, plugins (with license + tags), `strict: true` |
| `.mcp.json` bundles all MCP servers via `${CLAUDE_PLUGIN_ROOT}` | [`.mcp.json`](../.mcp.json) | ✅ aish-tensordock + aish-modal, env-allowlist only |
| LICENSE = MIT (SPDX) | [`LICENSE`](../LICENSE) | ✅ |
| README with install/usage/security | [`README.md`](../README.md) | ✅ banner, 3 install paths, env-var table, 3 examples, security summary |

## STOP-SHIP security checklist (8 items, [`ANTHROPIC-PLUGIN.md` §3](../ANTHROPIC-PLUGIN.md#3-stop-ship-security-checklist))

| # | Item | Implementation | Verification |
| --- | --- | --- | --- |
| 1 | No `shell=True` anywhere | `aish_mcp/modal_mcp_server.py:105` (`asyncio.create_subprocess_exec(*argv, …)`) | `tests/test_no_shell_true.py:13,28,40` (regex meta-test scans `aish_mcp/`, `skills/`, `scripts/` — guarded by `_shipped_python_files()` which fails the test if any dir is empty) + CI `name: No-shell=True guard` step in `.github/workflows/ci.yml:51` |
| 2 | Bearer tokens redacted in every error path | `aish_mcp/_redact.py:16,17,20,23,24,25-27,29-31` (7 redaction patterns: auth header, inline bearer, `tdk_*/sk_*/hf_*/...`, Modal `ak-/as-`, hex blob, `X-Api-Key`, Modal config-show line) | `tests/test_redact.py` 13 tests covering each shape + idempotence |
| 3 | Strict input validation at every tool boundary | `aish_mcp/_validation.py:26,33,42,51,60,77,107` (UUID/name/gpu/envkey/range/path/choice) | `tests/test_validation.py` 22 tests + 56 parametric cases |
| 4 | Hard timeouts + zombie kill on subprocess | `aish_mcp/modal_mcp_server.py:99-124` (`_run` with `asyncio.wait_for` → `TimeoutError` → `proc.kill()` + `await proc.wait()`); env timeouts go through `_bounded_timeout` (line 42) which rejects inf/nan/negative | `tests/test_modal.py::test_timeout_kills_and_returns_typed_error` |
| 5 | Env-var-only secrets + startup validation | `aish_mcp/tensordock_mcp_server.py:72-82` (`_api_token()` raises `RuntimeError` if missing); `RuntimeError` is caught in every helper and surfaced as `configuration_error` not generic internal_error | `.gitignore:2-7` blocks `.env`, `.env.*`, `*.pem`, `*.key`, `*.token`; `.env.example` is the only `.env*` file in the repo; `tests/test_tensordock.py::test_missing_token_surfaces_actionable_error` |
| 6 | `pip-audit` + `bandit` blocking in CI | `.github/workflows/ci.yml:41,44` (bandit, with `--severity-level medium`), `.github/workflows/ci.yml:55-69` (pip-audit job) | bandit reports 0 MEDIUM, 0 HIGH; pip-audit reports 0 CVEs after 2026-05-05 dep bump (v0.1.3) |
| 7 | No `PreToolUse` input-mutation hooks; no `CLAUDE_ENV_FILE` writes | No `hooks/` directory shipped | [`ANTHROPIC-PLUGIN.md` decision log §12](../ANTHROPIC-PLUGIN.md#12-decision-log) |
| 8 | `SessionStart` hook absent — install side-effect-free | No `hooks/` directory shipped | [`ANTHROPIC-PLUGIN.md` decision log §12](../ANTHROPIC-PLUGIN.md#12-decision-log) |

## MCP server controls (13 items, [`ANTHROPIC-PLUGIN.md` §4](../ANTHROPIC-PLUGIN.md#4-mcp-server-security-per-official-spec-2025-06-18))

| # | Control | Where |
| --- | --- | --- |
| 4.1 | UUID/name/path/range validators at boundary | [`aish_mcp/_validation.py`](../aish_mcp/_validation.py) (entire module) |
| 4.2 | Path traversal guard (`..`, NUL, control chars) | `aish_mcp/_validation.py:77-104` (`validate_safe_path`) |
| 4.3 | `asyncio.create_subprocess_exec(*argv)` only | `aish_mcp/modal_mcp_server.py:105` |
| 4.4 | `shutil.which("modal")`; reject if not found | `aish_mcp/modal_mcp_server.py:88-96` (`_modal_bin`) |
| 4.5 | Subprocess timeout + kill + await on `TimeoutError` | `aish_mcp/modal_mcp_server.py:112-119` |
| 4.6 | httpx hard timeouts; AsyncClient as context manager | `aish_mcp/tensordock_mcp_server.py:159-165` (and parallel `_post/_put/_delete`) |
| 4.7 | Strip `Authorization` / `X-API-*` from errors | `aish_mcp/_redact.py:16-31`, applied at `_err()` in both servers |
| 4.8 | Catch `httpx.HTTPStatusError`; never `repr(exc)` | `aish_mcp/tensordock_mcp_server.py:108` (`_classify`) — returns `{ok, status, code, message, hint}` |
| 4.9 | HTTPS enforced; `follow_redirects=False` (SSRF) | `aish_mcp/tensordock_mcp_server.py:160` and parallel helpers |
| 4.10 | Stdio transport only | `mcp.run()` defaults; no HTTP code in either server |
| 4.11 | Cap response size returned to model | `aish_mcp/tensordock_mcp_server.py:342` (`hostnodes[:20]`) |
| 4.12 | Treat upstream responses as untrusted text | All tool returns wrapped in `_ok()` JSON envelope; `redact()` applied to subprocess stdout/stderr at `aish_mcp/modal_mcp_server.py:127-139` |
| 4.13 | No token-passthrough — env-var-only credentials | `_api_token()` is the only token reader; tools never accept tokens as arguments |

## Tests (≥70% coverage gate, all green)

```text
$ pytest --cov
113 passed in 0.72s
─────────── coverage ───────────
aish_mcp/__init__.py                   100%
aish_mcp/_logging.py                   100%
aish_mcp/_validation.py                100%
aish_mcp/_redact.py                     97%
aish_mcp/modal_mcp_server.py            78%
aish_mcp/tensordock_mcp_server.py       73%
TOTAL                                   ≈79%   (gate: 70%)
```

Test files:
- [`tests/test_validation.py`](../tests/test_validation.py) — UUID, resource name, path, numeric, env key, GPU model, choice
- [`tests/test_redact.py`](../tests/test_redact.py) — auth header / inline bearer / TDK / HF / hex / X-API / Modal `ak-`/`as-` / Modal config-show block / idempotence / non-string / short-token edge cases
- [`tests/test_no_shell_true.py`](../tests/test_no_shell_true.py) — `shell=True` and `os.system` absent in shipped code; **scans `aish_mcp/`, `skills/`, `scripts/`** with a fail-loud assertion if any directory is empty
- [`tests/test_tensordock.py`](../tests/test_tensordock.py) — happy paths, validation rejection, 401/503 classification, token redaction, missing-token actionable error
- [`tests/test_modal.py`](../tests/test_modal.py) — happy paths, missing CLI, path traversal rejection, GPU enum rejection, env-key validation, timeout-with-zombie-kill
- [`tests/test_tools_smoke.py`](../tests/test_tools_smoke.py) — round-trip smoke tests across every public MCP tool (30 tests)
- [`tests/conftest.py`](../tests/conftest.py) — autouse fixture scrubs production credentials so a stray real call fails closed

## Continuous integration

| Workflow | What it does |
| --- | --- |
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | py3.11 + py3.12 matrix → ruff (line 38) → bandit `--severity-level medium` (line 41) → pytest+cov (line 46) → shell=True grep (line 51) → pip-audit (separate job, line 55) → plugin-manifest validation (line 71); all uses `actions/checkout@v6`, `actions/setup-python@v6` after v0.1.3 |
| [`.github/workflows/codeql.yml`](../.github/workflows/codeql.yml) | weekly + on-PR Python `security-extended` query pack |
| [`.github/dependabot.yml`](../.github/dependabot.yml) | weekly pip + github-actions updates |

## Documentation surface

- [`README.md`](../README.md) — banner, install (3 paths), env-var table, 3 worked examples, security summary, license
- [`CLAUDE.md`](../CLAUDE.md) — working agreement for in-repo agents (8 hard rules)
- [`PLAN.md`](../PLAN.md) — 9-phase roadmap with status markers
- [`ANTHROPIC-PLUGIN.md`](../ANTHROPIC-PLUGIN.md) — full security/acceptance contract with decision log
- [`SECURITY.md`](../SECURITY.md) — disclosure policy + safe-harbor + 90-day window
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — local triad before PR
- [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) — Contributor Covenant 2.1
- [`docs/PRIOR-ART.md`](./PRIOR-ART.md) — explicit accounting of what was carried over from AIsh, AIsh-v0, gpu-cloud-mcp; what was dropped and why

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

- [`lonexreb/aish-legacy`](https://github.com/lonexreb/aish-legacy) — scaffold, name only
- [`lonexreb/AIsh-v0`](https://github.com/lonexreb/AIsh-v0) — `hardware.py` GPU detection logic carried into `skills/gpu-detect/`; everything else (voice, multi-framework agents, TUI, monolithic main.py) deliberately deferred or dropped
- [`lonexreb/gpu-cloud-mcp`](https://github.com/lonexreb/gpu-cloud-mcp) — both MCP servers, the 29 v1 hardening requirements, the architecture description

## Submission

When ready: open the form at [`claude.ai/settings/plugins/submit`](https://claude.ai/settings/plugins/submit) (or [`platform.claude.com/plugins/submit`](https://platform.claude.com/plugins/submit)) and reference:

- Repo: `https://github.com/lonexreb/aish`
- Tag: `v0.1.3` (annotated; GPG-signed planned for v0.2 — see PLAN Phase 7)
- This file: `https://github.com/lonexreb/aish/blob/main/docs/SUBMISSION.md`
