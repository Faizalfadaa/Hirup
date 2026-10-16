#!/usr/bin/env bash
# Source this file from scripts; all host paths remain quoted.
set -euo pipefail

INFRA_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd -- "$INFRA_ROOT/.." && pwd)"
set -a
source "$INFRA_ROOT/images.env"
set +a

host_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -am "$1"
    else
        printf '%s\n' "$1"
    fi
}

# Prevent Git Bash from rewriting container paths such as /opt/car.lua.
export MSYS_NO_PATHCONV=1
REPO_HOST="$(host_path "$REPO_ROOT")"
INFRA_HOST="$(host_path "$INFRA_ROOT")"

# Linux bind mounts preserve numeric ownership. Build files as the invoking user
# so host-side markers, cache uploads and subsequent builds remain writable.
# Docker Desktop maps Windows permissions itself; do not pass a Git Bash UID.
HOST_USER_OPTIONS=()
if [[ "$(uname -s)" == Linux ]]; then
    HOST_USER_OPTIONS=(--user "$(id -u):$(id -g)")
fi

compose() {
    docker compose --project-name hirup-routing \
        --project-directory "$INFRA_HOST" \
        --env-file "$INFRA_HOST/images.env" \
        -f "$INFRA_HOST/docker-compose.yml" "$@"
}

ensure_tools() {
    docker info >/dev/null
    if ! docker image inspect "$TOOLS_IMAGE" >/dev/null 2>&1; then
        docker build -t "$TOOLS_IMAGE" -f "$INFRA_HOST/tools/Dockerfile" \
            "$INFRA_HOST/tools"
    fi
}

run_python() {
    docker run --rm "${HOST_USER_OPTIONS[@]}" \
        --mount "type=bind,source=$REPO_HOST,target=/workspace" \
        --workdir /workspace "$TOOLS_IMAGE" python "$@"
}

download() {
    local url="$1" destination="$2"
    if [[ -s "$destination" ]]; then
        printf 'Using cached download: %s\n' "$destination"
        return
    fi
    mkdir -p -- "$(dirname -- "$destination")"
    curl --fail --location --retry 3 --connect-timeout 30 \
        --continue-at - --output "$(host_path "$destination.part")" "$url"
    mv -- "$destination.part" "$destination"
}
