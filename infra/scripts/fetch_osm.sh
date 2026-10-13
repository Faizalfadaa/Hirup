#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

ensure_tools
download 'https://download.geofabrik.de/asia/indonesia/java-latest.osm.pbf' \
    "$REPO_ROOT/data/osm/java-latest.osm.pbf"

bbox="$(run_python infra/scripts/routing_data.py bbox)"
printf 'Clipping OSM to pilot plus 2 km buffer: %s\n' "$bbox"
docker run --rm \
    --mount "type=bind,source=$REPO_HOST/data/osm,target=/data" \
    "$TOOLS_IMAGE" osmium extract --strategy complete_ways --bbox "$bbox" \
    --overwrite --output /data/pilot.osm.pbf /data/java-latest.osm.pbf
docker run --rm \
    --mount "type=bind,source=$REPO_HOST/data/osm,target=/data,readonly" \
    "$TOOLS_IMAGE" osmium fileinfo --extended /data/pilot.osm.pbf
