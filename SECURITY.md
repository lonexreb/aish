# Security Policy

## Supported versions

`aish` is in alpha (v0.x). Security fixes are made on the `main` branch and released as patch versions. Older minor versions are not maintained.

| Version | Supported |
| --- | --- |
| 0.1.x | ✅ |
| < 0.1 | ❌ |

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue.

**Email:** reach2shubhankar@gmail.com (subject prefix: `[aish-security]`)

Or use [GitHub's private vulnerability disclosure](https://github.com/lonexreb/aish/security/advisories/new) on this repository.

### What to include

- A clear description of the vulnerability and its impact.
- Steps to reproduce (proof-of-concept code is welcome).
- The version / commit you tested against.
- Any suggested mitigation.

### Our response

| Time | What we'll do |
| --- | --- |
| 48 h | Acknowledge receipt. |
| 7 d | Triage and confirm whether it's a vulnerability. |
| 30 d | Provide a target fix date or mitigation. |
| 90 d | Publicly disclose, with credit, after a fix ships. We can extend on mutual agreement. |

### Scope

In scope:

- The two MCP servers (`mcp/tensordock_mcp_server.py`, `mcp/modal_mcp_server.py`).
- The skills, slash commands, subagent definitions, and helper scripts in this repo.
- The plugin and marketplace manifests.

Out of scope:

- Vulnerabilities in upstream services (TensorDock API, Modal control plane, MCP SDK, FastMCP, httpx, Python). Please report those upstream; we'll mirror advisories.
- Vulnerabilities that require a malicious user to also install or modify the plugin themselves.
- Issues that depend on the user's `~/.claude/settings.json` having dangerous values they set manually.

### Safe-harbor

Good-faith research that follows this policy is welcome. We will not pursue legal action against researchers who:

- Make a good-faith effort to avoid privacy violations, data destruction, or service disruption.
- Stop testing as soon as they discover a vulnerability (no further exfiltration / pivot).
- Give us a reasonable window to ship a fix before public disclosure.
