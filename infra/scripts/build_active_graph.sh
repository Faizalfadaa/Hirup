#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

ensure_tools
[[ -s "$REPO_ROOT/data/osm/pilot.osm.pbf" ]] || {
    printf 'Pilot OSM missing; run data-routing first.\n' >&2
    exit 1
}
mkdir -p -- "$REPO_ROOT/data/graphs"
# Keep complete road ways/nodes; conversion and filtering happen only in Docker.
docker run --rm \
    --mount "type=bind,source=$REPO_HOST/data,target=/data" \
    "$TOOLS_IMAGE" osmium tags-filter /data/osm/pilot.osm.pbf w/highway \
    --overwrite --output /data/graphs/active.osm
cd -- "$REPO_ROOT"
uv run python -m services.routing.build_active_graph
