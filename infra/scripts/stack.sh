#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

case "${1:-}" in
    up)
        [[ ! -e "$REPO_ROOT/data/otp/.build-incomplete" ]] || {
            printf 'Previous graph build did not finish. Run graphs again.\n' >&2
            exit 1
        }
        [[ -s "$REPO_ROOT/data/otp/graph.obj" ]] || {
            printf 'OTP graph missing. Run make -f infra/Makefile graphs first.\n' >&2
            exit 1
        }
        ensure_tools
        compose up -d --wait --wait-timeout 300
        ;;
    down) compose down ;;
    config) compose config --quiet ;;
    logs) compose logs --tail 80 "${@:2}" ;;
    ps) compose ps ;;
    *) printf 'Usage: %s {up|down|config|logs|ps}\n' "$0" >&2; exit 2 ;;
esac
