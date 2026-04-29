# CLAUDE.md — aish

This file is loaded by Claude Code when working inside the `aish` repository. It is the working agreement between human, agent, and reviewer.

## What this project is

`aish` is a **Claude Code plugin** that bundles two MCP servers (TensorDock REST, Modal CLI), a set of skills, slash commands, and subagents — all aimed at giving Claude Code first-class control over GPU cloud infrastructure.

The plugin is being prepared for submission to the **official Anthropic plugin marketplace**. Every change must keep that goal credible.

## Repository layout

```
aish/
├── .claude-plugin/
│   ├── plugin.json          # plugin manifest (REQUIRED)
│   └── marketplace.json     # single-plugin marketplace manifest
├── .mcp.json                # bundles aish-tensordock + aish-modal
├── mcp/
│   ├── tensordock_mcp_server.py
│   └── modal_mcp_server.py
├── commands/                # slash commands (flat .md files)
├── agents/                  # subagent .md files with YAML frontmatter
├── skills/<name>/SKILL.md   # skills, one folder each
├── tests/                   # pytest, all external calls mocked
├── assets/banner.svg        # README banner
├── docs/                    # extra docs (PRIOR-ART, etc.)
├── scripts/                 # dev helpers
├── .github/workflows/       # CI (lint + test + audit)
└── README.md / PLAN.md / ANTHROPIC-PLUGIN.md / SECURITY.md / CONTRIBUTING.md
```

## How to run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,modal]"
export TENSORDOCK_API_TOKEN="tdk_..."   # or set in ~/.claude/settings.json env
modal setup                              # one-time
pytest -q
python3 mcp/tensordock_mcp_server.py     # speaks stdio MCP
python3 mcp/modal_mcp_server.py
```

## How to run as a plugin in Claude Code

```text
/plugin marketplace add ./                # local dev
/plugin install aish@aish-marketplace
```

Restart Claude Code. The two MCP servers boot via the `${CLAUDE_PLUGIN_ROOT}` resolution in `.mcp.json`.

## Hard rules (load-bearing — don't break)

1. **No secrets in the repo.** `TENSORDOCK_API_TOKEN` is env-var-only. `.gitignore` blocks `.env`, `*.pem`, `*.token`, `*.key`. If you see a secret in a diff, halt.
2. **No `shell=True`, ever.** Subprocess calls use `asyncio.create_subprocess_exec` with list-form argv. Modal binary located via `shutil.which("modal")`, never via shell expansion.
3. **Validate at the tool boundary.** Every `@mcp.tool()` parameter that flows to an external API or subprocess must be validated:
   - UUIDs: `re.fullmatch(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", val, re.IGNORECASE)`
   - Resource names: `re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", val)`
   - Paths: resolve with `Path(p).resolve()` then `is_relative_to(allowed_root)`
   - Numeric: explicit min/max
4. **Redact tokens in error paths.** Never `repr(exc)` an httpx exception — wrap and return `{status, code, message}` with `Authorization` and `X-API-*` stripped.
5. **Hard timeouts.** httpx: 30s GET / 60s POST. Subprocess: 120s default, override to 300/600 for deploy/run only. On timeout: `proc.kill()` then `await proc.wait()`.
6. **Tests mock everything external.** `respx` for httpx; `unittest.mock` for `asyncio.create_subprocess_exec`. No test ever hits a real API.
7. **No `PreToolUse` hooks that mutate `updatedInput`.** Anthropic's hook docs warn this is invisible in the transcript and is treated as a security smell. We don't ship any such hook.
8. **Install is side-effect-free.** No `SessionStart` hook that writes anywhere outside the plugin dir. No network calls during enable.

## Adding a new MCP tool

1. Add a function decorated with `@mcp.tool()` in the appropriate server file.
2. Type-hint every parameter — FastMCP generates the JSON schema from the hints.
3. Validate every parameter that flows externally (see rule 3 above).
4. Wrap the I/O in try/except, redact tokens, return JSON via `json.dumps(data, indent=2)`.
5. Add a unit test in `tests/` that mocks the external call and asserts both happy and error paths.
6. Update the tool table in `README.md`.

## Adding a new skill

1. `skills/<kebab-name>/SKILL.md` with YAML frontmatter (`description`, optionally `disable-model-invocation`).
2. Keep skills focused — one verb each. Reference scripts via `${CLAUDE_PLUGIN_ROOT}/scripts/...` if needed.

## Adding a new slash command

1. `commands/<kebab-name>.md` (flat — not in a directory).
2. Frontmatter: `description`. Body is the prompt template.
3. Don't accept secrets via command args.

## Adding a new subagent

1. `agents/<kebab-name>.md` with frontmatter `name`, `description`, `tools` (whitelist explicit MCP tools — no blanket bash).

## Workflow when working on this repo

- Use the **planner** agent for new feature design.
- Use the **tdd-guide** agent — write tests before implementation.
- Use the **security-reviewer** agent before committing anything that touches subprocess, httpx, or env vars.
- Use the **python-reviewer** agent for any new Python module.
- Run `ruff check . && bandit -r . -c pyproject.toml && pytest -q` before pushing.

## Commit style

Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `perf:`, `ci:`, `security:`. One logical change per commit. Push frequently.

## Out of scope (for v1)

- Voice (Hume AI) — deferred to v2.
- Multi-framework agents (LangChain / CrewAI / uAgents) — Claude Code's own subagent system supersedes them.
- TUI (Textual) — Claude Code is the UI now.
- New cloud providers — TensorDock + Modal only until v1 ships.

## Reference docs

- [`PLAN.md`](./PLAN.md) — phased roadmap & milestones
- [`ANTHROPIC-PLUGIN.md`](./ANTHROPIC-PLUGIN.md) — security & acceptance checklist
- [`docs/PRIOR-ART.md`](./docs/PRIOR-ART.md) — what was carried over and what was dropped
