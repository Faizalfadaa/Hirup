#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/../scripts/common.sh"

project="${HIRUP_CI_PROJECT:-}"
[[ "$project" =~ ^hirup-ci-[a-z0-9-]+$ ]] || {
    printf 'Set HIRUP_CI_PROJECT to hirup-ci-<unique-suffix>.\n' >&2
    exit 1
}
# Separate ports even when a user already runs the default stack on this host.
export OTP_HOST_PORT=18081 OSRM_CAR_HOST_PORT=5100 OSRM_MOTO_HOST_PORT=5101
ci_compose() {
    docker compose --project-name "$project" --project-directory "$INFRA_HOST" \
        --env-file "$INFRA_HOST/images.env" -f "$INFRA_HOST/docker-compose.yml" \
        -f "$INFRA_HOST/ci/compose.yml" "$@"
}
case "${1:-}" in
    config) ci_compose config --quiet ;;
    up)
        [[ ! -e "$REPO_ROOT/data/otp/.build-incomplete" ]] || {
            printf 'Graph build is incomplete.\n' >&2; exit 1;
        }
        ci_compose up -d --wait --wait-timeout 300 otp osrm-car osrm-moto
        ;;
    down)
        # Never prune globally or stop the user's hirup-routing project.
        status=0
        ci_compose down --remove-orphans --timeout 30 || status=$?
        build_ids="$(docker ps -aq --filter "label=hirup.ci.project=$project")"
        if [[ -n "$build_ids" ]]; then
            mapfile -t builds <<< "$build_ids"
            docker rm -f "${builds[@]}" || status=$?
        fi
        exit "$status"
        ;;
    *) printf 'Usage: stack.sh {config|up|down}\n' >&2; exit 2 ;;
esac
