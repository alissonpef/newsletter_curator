#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

newsletter-curator healthcheck
