## What changed

<!-- 1-2 sentences. -->

## Why

<!-- Reference PLAN.md phase or an issue number. -->

## Checklist

- [ ] Conventional commit prefix (`feat:` / `fix:` / `docs:` / `chore:` / `test:` / `security:`)
- [ ] `ruff check .` clean
- [ ] `bandit -r aish_mcp/ skills/ -c pyproject.toml` clean (no MEDIUM/HIGH)
- [ ] `pytest --cov` passes (≥70% coverage)
- [ ] Tests added or updated for any changed behavior
- [ ] If a security control changed: `ANTHROPIC-PLUGIN.md` decision log updated
- [ ] If an MCP tool added/changed: `README.md` tool table updated
- [ ] No `.env`, secrets, or credentials in the diff
