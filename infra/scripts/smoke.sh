#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

ensure_tools
compose run --rm --no-deps --entrypoint python api \
    /workspace/infra/scripts/smoke.py "$@"
