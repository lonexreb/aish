#!/usr/bin/env bash
# Run the full local triad: lint + security scan + tests + coverage.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▸ ruff"
ruff check aish_mcp/ tests/ skills/

echo "▸ bandit"
bandit -q -r aish_mcp/ skills/ -c pyproject.toml

echo "▸ pytest"
pytest --cov --cov-report=term-missing

echo "▸ shell=True guard"
if grep -RIn --include='*.py' 'shell\s*=\s*True' aish_mcp/ skills/ scripts/; then
  echo "shell=True found in shipped code — STOP-SHIP" >&2
  exit 1
fi

echo "▸ all checks passed"
