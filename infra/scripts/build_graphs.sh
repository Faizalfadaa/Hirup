#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
started=$SECONDS
heap="${HIRUP_OTP_BUILD_HEAP:-8g}"
ci_project="${HIRUP_CI_PROJECT:-}"
build_options=()
if [[ -n "$ci_project" ]]; then
    [[ "$ci_project" =~ ^hirup-ci-[a-z0-9-]+$ ]] || {
        printf 'Invalid isolated CI project name.\n' >&2; exit 1;
    }
    build_options=(--name "$ci_project-build" --label "hirup.ci.project=$ci_project")
fi
[[ "$heap" == 8g || ( "$heap" == 4g && -n "$ci_project" ) ]] || {
    printf 'OTP heap must be 8g, or 4g for an isolated CI project.\n' >&2; exit 1;
}

ensure_tools
run_python infra/scripts/routing_data.py stage
touch "$REPO_ROOT/data/otp/.build-incomplete"
# Stop only this project's runtime before building to free memory.
if [[ -n "$ci_project" ]]; then
    docker compose --project-name "$ci_project" --project-directory "$INFRA_HOST" \
        --env-file "$INFRA_HOST/images.env" -f "$INFRA_HOST/docker-compose.yml" \
        stop otp osrm-car osrm-moto
else
    compose stop otp osrm-car osrm-moto
fi
docker pull "$OSRM_IMAGE"
for profile in car motorcycle; do
    profile_started=$SECONDS
    mkdir -p -- "$REPO_ROOT/data/osrm/$profile"
    cp -- "$REPO_ROOT/data/osm/pilot.osm.pbf" \
        "$REPO_ROOT/data/osrm/$profile/pilot.osm.pbf"
    for phase in extract partition customize; do
        args=("osrm-$phase")
        if [[ "$phase" == extract ]]; then
            args+=(-p "/profiles/$profile.lua" /data/pilot.osm.pbf)
        else
            args+=(/data/pilot.osrm)
        fi
        docker run --rm "${HOST_USER_OPTIONS[@]}" "${build_options[@]}" \
            --mount "type=bind,source=$REPO_HOST/data/osrm/$profile,target=/data" \
            --mount "type=bind,source=$INFRA_HOST/osrm,target=/profiles,readonly" \
            "$OSRM_IMAGE" "${args[@]}"
    done
    printf 'OSRM %s graph built in %s seconds\n' "$profile" "$((SECONDS - profile_started))"
done
otp_started=$SECONDS
docker pull "$OTP_IMAGE"
docker run --rm "${HOST_USER_OPTIONS[@]}" "${build_options[@]}" --env "JAVA_TOOL_OPTIONS=-Xmx$heap" --env TZ=Asia/Jakarta \
    --mount "type=bind,source=$REPO_HOST/data/otp,target=/var/opentripplanner" \
    "$OTP_IMAGE" --build --save
rm -- "$REPO_ROOT/data/otp/.build-incomplete"
printf 'OTP graph built in %s seconds\n' "$((SECONDS - otp_started))"
printf 'All routing graphs built in %s seconds\n' "$((SECONDS - started))"
