#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

ensure_tools
download 'https://files.mobilitydatabase.org/mdb-1909/latest.zip' \
    "$REPO_ROOT/data/gtfs/transjakarta.gtfs.zip"
run_python infra/scripts/routing_data.py prepare-gtfs
