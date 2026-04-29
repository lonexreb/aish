# Contributing to aish

Thanks for your interest. This is a small, focused plugin and we'd like to keep it that way.

## Before opening an issue

1. Search existing issues and the [`PLAN.md`](./PLAN.md) phase markers — your idea may already be tracked.
2. Read [`CLAUDE.md`](./CLAUDE.md) and [`ANTHROPIC-PLUGIN.md`](./ANTHROPIC-PLUGIN.md). They define what the plugin will and won't do.

## Issue templates

| Template | When to use |
| --- | --- |
| `bug_report.md` | The plugin or one of its tools misbehaved. Include reproduction steps and the command output. |
| `feature_request.md` | You want a new tool, skill, or command. Tell us the workflow it enables, not just the feature name. |
| `security.md` | Use this for **non-sensitive** security suggestions. For actual vulnerabilities, follow [`SECURITY.md`](./SECURITY.md) instead. |

## Pull requests

1. Fork → branch → PR. Branch names: `feat/...`, `fix/...`, `docs/...`, etc.
2. Conventional commits. One logical change per commit.
3. Run the local triad before opening the PR:

   ```bash
   ruff check .
   bandit -r mcp/ -c pyproject.toml
   pytest --cov
   pip-audit -r <(pip freeze)
   ```
4. PRs that change anything in `mcp/`, `.mcp.json`, or `.claude-plugin/` require:
   - A new or updated test in `tests/`.
   - A note in the `ANTHROPIC-PLUGIN.md` decision log if a security control is affected.
5. PRs that add a new MCP tool must:
   - Validate every parameter at the tool boundary (use helpers in `mcp/_validation.py`).
   - Wrap I/O in token-redacting error handlers (helpers in `mcp/_redact.py`).
   - Update the tool table in `README.md`.

## Local dev setup

```bash
git clone https://github.com/lonexreb/aish.git
cd aish
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,modal]"
modal setup
export TENSORDOCK_API_TOKEN="tdk_..."
pytest -q
```

## Running the plugin against your own Claude Code

```text
/plugin marketplace add /absolute/path/to/aish
/plugin install aish@aish-marketplace
```

Restart Claude Code so the MCP servers boot.

## Releasing (maintainers only)

1. Bump version in `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.
2. Update `PLAN.md` and `ANTHROPIC-PLUGIN.md` decision log.
3. `git tag -s vX.Y.Z` (signed) and `git push --tags`.
4. The release workflow generates the SBOM and creates the GitHub Release.

## Code of conduct

Participation in this project is governed by [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).
