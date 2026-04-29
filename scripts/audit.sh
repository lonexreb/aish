#!/usr/bin/env bash
# Run full supply-chain audit: pip-audit + bandit + secret scan.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▸ pip-audit"
pip-audit --strict --skip-editable || true

echo "▸ bandit"
bandit -q -r aish_mcp/ skills/ -c pyproject.toml

if command -v gitleaks >/dev/null 2>&1; then
  echo "▸ gitleaks"
  gitleaks detect --redact --no-git -s .
else
  echo "▸ gitleaks (skipped — install for full secret scan)"
fi
