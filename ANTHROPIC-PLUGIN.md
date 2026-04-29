# ANTHROPIC-PLUGIN.md

> Best practices and security checklist for shipping `aish` as an officially-accepted Anthropic plugin.

This document is the contract between `aish` and the Anthropic plugin marketplace reviewer. Every item below is either implemented in this repository, scheduled in [`PLAN.md`](./PLAN.md), or explicitly out of scope with a written rationale.

It also stands as a reusable template — fork it for any plugin you author.

---

## 1. What "official" means

Anthropic publishes the canonical marketplace at [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official). Plugins listed there are submitted via [`claude.ai/settings/plugins/submit`](https://claude.ai/settings/plugins/submit) or [`platform.claude.com/plugins/submit`](https://platform.claude.com/plugins/submit) and reviewed by Anthropic before listing.

Two key facts from the official repo's README:

1. Anthropic does not control or warrant any MCP server or code shipped inside community plugins. The user is asked to trust the publisher. Therefore the bar for acceptance is **provable trustworthiness** — clean source, explicit dependencies, no surprises.
2. There is no `preinstall` / `postinstall` lifecycle hook today. The earliest user-facing code path runs is `SessionStart` once the user enables the plugin. **`aish` ships no `SessionStart` hook.** Install is side-effect-free.

References:
- [Plugins overview](https://code.claude.com/docs/en/plugins)
- [Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Discover plugins](https://code.claude.com/docs/en/discover-plugins)
- [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official)

---

## 2. Manifest contract

### 2.1 `.claude-plugin/plugin.json`

| Field | Required | aish value | Notes |
| --- | --- | --- | --- |
| `name` | yes | `aish` | kebab-case, must be globally unique within the marketplace it's published in |
| `version` | de-facto | `0.1.0` | semver; technically optional but every reviewable plugin pins one. Without it, `/plugin update` cannot work and reviewers cannot diff releases |
| `description` | yes | one-liner | shown in plugin manager |
| `author` | recommended | object with name/email/url | establishes accountability |
| `homepage` | recommended | repo URL | |
| `repository` | recommended | repo URL | string form (most plugins use string, not the npm-style object) |
| `license` | recommended | `MIT` | SPDX id; proprietary licenses are not accepted |
| `keywords` | optional | `["claude-code", "claude-code-plugin", "mcp", "gpu", ...]` | improves discoverability |

### 2.2 `.claude-plugin/marketplace.json`

`aish` ships as its own single-plugin marketplace so users can install via `/plugin marketplace add lonexreb/aish`. The fields used:

```json
{
  "name": "aish-marketplace",
  "owner": { "name": "...", "email": "...", "url": "..." },
  "metadata": { "description": "...", "version": "0.1.0" },
  "plugins": [{
    "name": "aish",
    "source": ".",
    "description": "...",
    "version": "0.1.0",
    "category": "developer-tools",
    "tags": ["gpu", "cloud", "tensordock", "modal", "mcp", "ml"]
  }],
  "strict": true
}
```

`strict: true` means we don't allow inline component overrides — components must come from the plugin's actual files. This is a security posture: no surprise tools defined only in the marketplace manifest.

### 2.3 `.mcp.json`

`aish` bundles two local-subprocess MCP servers, modeled on [`ZeframLou/call-me`](https://github.com/ZeframLou/call-me) (the closest analog in the public ecosystem).

```json
{
  "mcpServers": {
    "aish-tensordock": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/tensordock_mcp_server.py"],
      "env": { "TENSORDOCK_API_TOKEN": "${TENSORDOCK_API_TOKEN}" }
    },
    "aish-modal": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/modal_mcp_server.py"],
      "env": { "PATH": "${PATH}" }
    }
  }
}
```

Notes:
- `${CLAUDE_PLUGIN_ROOT}` is the only correct way to reference bundled files. Never hardcode paths or assume cwd.
- The `env` block is an **explicit allowlist**, not a passthrough. We list every variable we want — `TENSORDOCK_API_TOKEN`, `PATH`, `AISH_LOG_LEVEL` — and nothing else. The MCP server inherits no additional environment.
- No tokens live in `plugin.json`; they're resolved by Claude Code at server-launch time from `~/.claude/settings.json` `env` block or the user's shell.

---

## 3. STOP-SHIP security checklist

Eight items must be green before any release. CI fails the build if any of them regress.

- [ ] **No `shell=True` anywhere.** All subprocess calls use `asyncio.create_subprocess_exec(*argv)` with list-form arguments. Verified by `bandit B602/B603` and a project-specific grep test.
- [ ] **Bearer tokens redacted in every error path.** Httpx exceptions are wrapped; `Authorization` and `X-API-*` headers are stripped before any string is returned to the model.
- [ ] **Strict input validation at every `@mcp.tool()` boundary.** UUIDs, resource names, paths, and numeric ranges are validated by named helpers in `mcp/_validation.py`. No tool dispatches I/O on un-validated input.
- [ ] **Hard timeouts + zombie prevention.** Every httpx call has a `timeout=` kwarg. Every subprocess uses `asyncio.wait_for` and on `TimeoutError` does `proc.kill(); await proc.wait()`.
- [ ] **Env-var-only secrets + startup validation.** `TENSORDOCK_API_TOKEN` is read from `os.environ` once at server boot; missing → `RuntimeError`. `.gitignore` blocks `.env`, `*.pem`, `*.token`. `.env.example` is the only `.env*` file in the repo.
- [ ] **`pip-audit` and `bandit` blocking in CI.** PRs cannot merge with known-CVE deps or `bandit` HIGH findings.
- [ ] **No `PreToolUse` hooks that mutate `updatedInput`. No `CLAUDE_ENV_FILE` writes.** Per the [hooks docs](https://code.claude.com/docs/en/hooks), input mutation is invisible in the transcript and treated as a security smell. We don't ship those hook types.
- [ ] **`SessionStart` hook is absent.** Install is side-effect-free; no network calls or file writes happen when a user enables the plugin.

---

## 4. MCP-server security (per [official spec, 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices))

| # | Control | aish status |
| --- | --- | --- |
| 4.1 | Validate every tool argument at the boundary (UUIDs, paths, ranges, enums) | implemented via `mcp/_validation.py` |
| 4.2 | Reject paths with `..`, NUL bytes, absolute escapes; resolve and re-check `is_relative_to(allowed_root)` | implemented |
| 4.3 | Subprocess: `asyncio.create_subprocess_exec(*argv)`; never `shell=True` | implemented (modal server) |
| 4.4 | Locate external binaries via `shutil.which()`; reject if not found | implemented (`_modal_bin()`) |
| 4.5 | Hard timeout on every subprocess + `proc.kill()` on timeout to prevent zombies | implemented |
| 4.6 | Hard timeout on every httpx call; `httpx.AsyncClient` as context manager so sockets close on error | implemented (tensordock server) |
| 4.7 | Strip/redact `Authorization`, `X-API-*` headers from error strings | implemented via `mcp/_redact.py` |
| 4.8 | Catch `httpx.HTTPStatusError`; return `{status, code, message}` — never `repr(exc)` | implemented |
| 4.9 | Enforce HTTPS for the TensorDock base URL; reject `http://` or redirects to private/loopback IPs (SSRF) | implemented |
| 4.10 | Stdio transport only — no HTTP/SSE | enforced by `mcp.run()` defaults |
| 4.11 | Cap response size returned to the model (e.g. 20 hostnodes) so a hostile API cannot blow context or smuggle prompt injection | implemented (existing cap in `list_hostnodes`) |
| 4.12 | Treat all upstream API responses as untrusted text — sanitize before placing in JSON returned to Claude | implemented |
| 4.13 | Never accept tokens in tool arguments — env-var-only credentials (no token-passthrough anti-pattern) | enforced |

---

## 5. Plugin hook safety (per [hooks docs](https://code.claude.com/docs/en/hooks))

Hooks execute arbitrary shell with full user privileges and zero sandboxing. They are equivalent to checked-in shell scripts. Therefore:

- `aish` ships **no hooks in v1**. If hooks are added later, they go through this gate:
  - Read input from stdin as JSON; never embed `$ARGUMENTS`-style interpolation into shell commands.
  - Use `set -euo pipefail` and fail closed.
  - Pin commands to absolute paths or `bin/` shipped in the plugin — do not rely on user `$PATH`.
  - No `PreToolUse` hooks that set `updatedInput` (invisible in transcript, see [hook docs](https://code.claude.com/docs/en/hooks)).
  - No `SessionStart` hooks that mutate `CLAUDE_ENV_FILE` (environment poisoning persists for the whole session).
  - Document every hook in the README with its purpose, inputs, and exit-code semantics.

Exit-code semantics inversion is a documented Claude Code footgun: code `2` blocks, code `1` is silently non-blocking. Never use `1` for safety-critical checks.

---

## 6. Secrets & credentials

- All credentials are environment variables. Never read from a file inside the repo.
- Validate at startup that required env vars are present; fail fast with a helpful message.
- Never log, print, or include secrets in tracebacks or returned errors. Wrap httpx calls in a helper that strips sensitive headers.
- `.env.example` is checked in with placeholders. `.env` is gitignored. There is no other config file format.
- GitHub repo settings: secret-scanning enabled, push-protection enabled.
- Pre-commit hook: `gitleaks` blocks staged secrets locally before commit ([gitleaks](https://github.com/gitleaks/gitleaks)).
- Weekly scheduled CI run: `trufflehog` over full git history with verification (classifies 800+ secret types and verifies live credentials).

---

## 7. Supply chain

| Control | aish status |
| --- | --- |
| Pin all deps with hashes (`uv pip compile --generate-hashes` or `pip-compile --generate-hashes`) | scheduled phase 6 |
| `pip-audit` in CI on every PR; fail on known CVEs | scheduled phase 6 |
| `bandit -r mcp/ src/` in CI; fail on HIGH severity | scheduled phase 6 |
| Pin Python in `pyproject.toml` to `>=3.11,<3.13` | done |
| Sign release tags (`git tag -s`); upload SBOM (`cyclonedx-py`) to GitHub Release | scheduled phase 7 |
| Generate provenance attestation via [GitHub Attestations](https://docs.github.com/en/actions/security-guides/using-artifact-attestations-to-establish-provenance-for-builds) | scheduled phase 7 |
| Dependabot weekly for `pip` ecosystem | scheduled phase 6 |
| CodeQL enabled for Python | scheduled phase 6 |

`uv pip compile --exclude-newer` may be added later to put a one-week embargo on freshly-published packages (defense against day-zero malicious-package publishes).

---

## 8. Permissions and tool scoping

- Subagents (`agents/*.md`) declare a `tools` whitelist in their frontmatter. **No subagent gets blanket `Bash` access.** The `gpu-operator` subagent gets only the `aish-tensordock:*` MCP tools it needs; the `ml-env-setup` subagent gets `aish-modal:*` and read-only `aish-tensordock:list_*`.
- Slash commands do not invoke shell directly. They produce prompt text; any execution flows through validated MCP tools.

---

## 9. Documentation expectations

- `README.md`: install steps, env-var table, three usage examples, security summary, license. SVG banner. ~150–400 lines per the public-plugin survey.
- `CLAUDE.md`: working agreement for in-repo agents. Hard rules + workflow.
- `PLAN.md`: phased roadmap with status markers. Always current.
- `ANTHROPIC-PLUGIN.md`: this file. Cited from the README.
- `SECURITY.md`: disclosure email, 90-day window, scope (which surfaces are in scope for vuln reports).
- `CONTRIBUTING.md`: how to file issues, propose changes, run the test/lint/audit triad.
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1.
- `docs/PRIOR-ART.md`: explicit accounting of what was carried over from AIsh, AIsh-v0, gpu-cloud-mcp; what was dropped and why. Reviewers look for evidence the author has thought about scope.
- `docs/SUBMISSION.md`: a one-page checklist of how each acceptance item is met, with file:line citations.

---

## 10. Testing expectations

- Unit tests for every MCP tool. External calls are mocked (`respx` for httpx, `unittest.mock` for `asyncio.create_subprocess_exec`). No test is allowed to reach a real API.
- Coverage gate ≥ 70% with `pytest --cov`. Reviewers can run `pytest -q` from a fresh clone and have it pass.
- Tests for both happy and error paths, including: token-redaction in errors, timeout handling, missing-binary handling, malformed responses, validation rejections.
- Security-specific tests: a regex test asserts `shell=True` does not appear anywhere in `mcp/`.

---

## 11. Distribution mechanics

The plugin can be installed three ways. We document all three in the README and CI verifies the first two work end-to-end.

```text
# 1. From the aish marketplace
/plugin marketplace add lonexreb/aish
/plugin install aish@aish-marketplace

# 2. From the official Anthropic marketplace (post-acceptance)
/plugin install aish@claude-plugins-official

# 3. Local development clone
/plugin marketplace add ./
/plugin install aish@aish-marketplace
```

Restart Claude Code after any of the above so the bundled stdio MCP servers boot.

---

## 12. Decision log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-04-29 | Defer voice (Hume AI) and multi-framework agents (LangChain/CrewAI/uAgents) from AIsh-v0 to a future plugin | Voice is out of scope for a code plugin and dramatically expands the dep tree (PyAudio, hume). LangChain/CrewAI/uAgents duplicate Claude Code's native subagent system. |
| 2026-04-29 | License = MIT | Most permissive, most common in Claude Code plugin ecosystem (Notion, claude-hud, arscontexta), zero-friction for marketplace acceptance. |
| 2026-04-29 | No hooks in v1 | The Claude Code hook surface has known footguns (input mutation invisibility, `SessionStart` env poisoning, exit-code inversion). v1 has no need for hooks; adding any will require explicit ANTHROPIC-PLUGIN.md update. |
| 2026-04-29 | Bundle MCP via stdio subprocess (not HTTP) | Stdio matches Claude Code's primary transport, avoids hosting a public endpoint and the auth/SSRF surface that comes with one. |
| 2026-04-29 | Single-plugin marketplace with `strict: true` | No surprise inline tools defined only in `marketplace.json`. Components must come from the plugin's actual files, which are reviewable in git. |

Add a row whenever you change a security-relevant control or scope decision. The decision log is part of the submission packet.

---

## 13. References

- [Claude Code Plugins overview](https://code.claude.com/docs/en/plugins)
- [Claude Code Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Discover plugins](https://code.claude.com/docs/en/discover-plugins)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official)
- [MCP Security Best Practices (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices)
- [OWASP OS Command Injection Defense Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html)
- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Python subprocess security notes](https://docs.python.org/3/library/subprocess.html#security-considerations)
- [`pypa/pip-audit`](https://github.com/pypa/pip-audit)
- [`PyCQA/bandit`](https://github.com/PyCQA/bandit)
- [`gitleaks/gitleaks`](https://github.com/gitleaks/gitleaks)
- [`trufflesecurity/trufflehog`](https://github.com/trufflesecurity/trufflehog)
- [GitHub Artifact Attestations](https://docs.github.com/en/actions/security-guides/using-artifact-attestations-to-establish-provenance-for-builds)
- Reference plugin (closest analog): [`ZeframLou/call-me`](https://github.com/ZeframLou/call-me)
- Reference plugin (clean minimal): [`agenticnotetaking/arscontexta`](https://github.com/agenticnotetaking/arscontexta)
- Reference plugin (HTTP-MCP variant): [`makenotion/claude-code-notion-plugin`](https://github.com/makenotion/claude-code-notion-plugin)
