# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] — 2026-05-05

Patch release. Pre-submission dependency hygiene sweep — all eight open Dependabot PRs resolved so a marketplace reviewer sees a maintained tree, not a stale one. No code changes; only dependency floors and CI action versions move.

### Changed

- **`mcp[cli]`** floor `>=1.23.0` → `>=1.27.0` (4 minor releases of upstream fixes; still `<2.0`).
- **`modal`** optional dep floor `>=0.74.5` → `>=1.4.2`. Major version jump on the Python package, but `aish_mcp/modal_mcp_server.py` shells out to the `modal` CLI binary via `asyncio.create_subprocess_exec` — no `import modal` anywhere in the code — so the API breakage in the SDK has no effect on this plugin. Floor bump is for users who `pip install aish[modal]`.
- **`pytest-asyncio`** floor `>=0.24.0` → `>=1.3.0` (major version stabilization). All 113 tests still pass under the new floor.
- **`ruff`** floor `>=0.7.4` → `>=0.15.12` (8 months of new lint rules; tree was already clean against them).
- **`setuptools`** build-system floor `>=68` → `>=82.0.1` (build-only, no runtime impact).
- **`actions/checkout`** v4 → v6 in CI workflows.
- **`actions/setup-python`** v5 → v6 in CI workflows.
- **`github/codeql-action`** v3 → v4 in CodeQL workflow (pre-empts the late-2026 v3 deprecation Anthropic reviewers would otherwise flag).

### Verified

- 113 tests passing under refreshed deps (`pytest -q`).
- `ruff check .` clean.
- `bandit -r aish_mcp/ skills/ --severity-level medium` reports zero MEDIUM/HIGH findings.
- `pip-audit` reports zero known vulnerabilities across the runtime + dev + modal extras.

## [0.1.2] — 2026-04-30

Patch release. Pre-submission polish on the plugin manifests so an Anthropic marketplace reviewer sees a clearer first impression. No code or behavior change — manifests only.

### Changed

- **`plugin.json` description** rewritten to lead with the verb (*Provision GPU VMs (TensorDock) and run serverless GPU apps (Modal) from Claude Code …*) instead of the buzzword "Agentic". Marketplace browsers truncate to the first ~80 chars, so those chars now describe what the plugin *does* rather than what it *is*.
- **`plugin.json` keywords** dropped redundant `claude-code` / `claude-code-plugin` entries (every entry in the marketplace is a Claude Code plugin — wasted slots) and added `huggingface`, `cuda`, `nvidia`, `serverless`, `agents` so the searchable surface matches the actual user audience. 9 → 12 keywords.
- **`marketplace.json`** plugin entry description and tag set updated to mirror `plugin.json` so a reviewer sees one consistent first impression in both manifests.

### Internal

- Version bumped in `plugin.json`, `marketplace.json` (top-level metadata + plugin entry), `pyproject.toml`, and `aish_mcp/__init__.py`.

## [0.1.1] — 2026-04-29

Patch release. Closes 5 HIGH-severity bugs found by an extensive multi-reviewer audit (security, python-idiom, plan-conformance) that ran post-v0.1.0. **Recommended over v0.1.0 for any new install.**

### Fixed

- **`tests/test_no_shell_true.py` was scanning a nonexistent `mcp/` directory** and silently no-op'ing. The STOP-SHIP regex meta-test passed without ever inspecting a single file in the shipped `aish_mcp/` tree. Now scans `aish_mcp/`, `skills/`, `scripts/` with a fail-loud assertion if any directory contains no `.py` files.
- **Broad `except Exception` swallowed `_api_token()` `RuntimeError`** in all four httpx helpers. A user who forgot to set `TENSORDOCK_API_TOKEN` saw `"Unexpected error: RuntimeError"` instead of the actionable setup hint with the dashboard URL. Now caught explicitly and surfaced as a `configuration_error` envelope with the original message intact.
- **Modal `ak-`/`as-` token format wasn't in the redaction regex set.** `modal config show` (called by the `check_config` tool) prints `Token id: ak-…\nToken secret: as-…`; both passed through `redact()` unchanged, leaking workspace credentials into model context. Now caught by `_MODAL_TOKEN_RE` and `_MODAL_CONFIG_LINE_RE`.
- **README advertised a non-existent `set_password` TensorDock tool** in the surface table. Replaced with the explicit list of all 10 real tools.
- **Doc/code drift across the spec docs** — `PLAN.md`, `ANTHROPIC-PLUGIN.md`, `docs/PRIOR-ART.md` all said `mcp/` while the code uses `aish_mcp/` (post-collision rename with the official MCP SDK package). Bulk rewrite; the `.mcp.json` example in `ANTHROPIC-PLUGIN.md` §2.3 now matches what ships.
- **`app_logs` returned `ok=true` even when the underlying `modal app list` failed** (e.g. not authenticated). Now propagates the real error envelope.
- **`run_app` silently dropped `function_name`** when `file_path` already contained `::`. Now raises `ValidationError` on the ambiguous combination.
- **`_put`/`_delete` had no `log.warning()` calls** on HTTP and network errors (only `_get`/`_post` did). Operational logs are now consistent across all four verbs.
- **Timeout env vars accepted `inf`/`nan`/negative**, silently disabling the hard-timeout STOP-SHIP item. New `_bounded_timeout()` helper rejects out-of-range values and falls back to the default.
- **`shell` tool `image` parameter** had no regex enforcing the OCI reference shape promised in the docstring. Now matches `[a-zA-Z0-9][a-zA-Z0-9_.\-:/]*` and rejects control characters.

### Security

- **Bumped pinned dependencies past 4 known CVEs**: `mcp` 1.2.0 → ≥1.23.0 (3 GHSAs), `pytest` 8.3.3 → ≥9.0.3 (1 GHSA). Switched all `==X.Y.Z` pins to `>=X.Y.Z,<MAJOR+1` so Dependabot can patch within a major without churning the manifest. `pip-audit` now reports zero known vulnerabilities.
- **Lowered `_TOKEN_RE` minimum** from `{16,}` to `{6,}` so short TensorDock tokens no longer slip through.
- **`PLAN.md` decision log** updated to add five concrete v0.2 hardening items derived from the security review (symlink resolution in `validate_safe_path`, `--from-json=<tempfile>` for `create_secret`, GPG-signed tags, hash-pinned deps, SBOM in release workflow).

### Added

- **30 round-trip smoke tests** (`tests/test_tools_smoke.py`) exercising every public MCP tool with mocked transport. Coverage rose from 52% to **78.93%**, comfortably above the 70% gate.
- **9 new redaction tests** including 4 specific to Modal token shapes.
- **CI `--severity-level medium` flag** on bandit so intentional LOW S603/S607 findings (after `shutil.which()` guards) don't fail builds.
- **CHANGELOG.md** (this file).

### Internal

- All `mcp/` references in docs replaced with `aish_mcp/` (the actual directory after the SDK-collision rename).
- `PLAN.md` status markers re-grounded against current state — Phases 2-7 now reflect what's actually shipped.
- `docs/SUBMISSION.md` re-derived all file:line citations from the live tree.
- `marketplace.json` plugin entry now includes the `license` field.

### Total commits since v0.1.0

```
5808135 ci: bandit threshold = MEDIUM (LOW S603/S607 are intentional)
90deacc docs: sync docs to code after security fixes (HIGH 2-5 from review)
e2ae847 fix(security): close 5 HIGH bugs found in specialist review
a5c352d security: bump deps past CVEs (mcp 1.2→1.27, pytest 8→9, httpx 0.27→0.28)
```

113 tests passing · ruff clean · bandit 0 MEDIUM/HIGH · pip-audit 0 CVEs · plugin discovery dry-run 21 OK / 0 problems.

## [0.1.0] — 2026-04-29

Initial alpha release. **Superseded by 0.1.1.**

- 2 MCP servers: `aish-tensordock` (10 tools), `aish-modal` (18 tools)
- 4 slash commands: `/aish:status`, `/aish:deploy-gpu`, `/aish:modal-run`, `/aish:hf-setup`
- 2 subagents: `gpu-operator`, `ml-env-setup`
- 2 skills: `gpu-detect`, `hf-env-setup`
- Full security/governance docs (CLAUDE.md, PLAN.md, ANTHROPIC-PLUGIN.md, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, docs/PRIOR-ART.md, docs/SUBMISSION.md)
- CI: ruff + bandit + pytest+cov + pip-audit + CodeQL + Dependabot

[0.1.1]: https://github.com/lonexreb/aish/releases/tag/v0.1.1
[0.1.0]: https://github.com/lonexreb/aish/releases/tag/v0.1.0
