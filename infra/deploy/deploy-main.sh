#!/usr/bin/env bash
set -euo pipefail
# Build and release one commit of main on the VM. Installed as /usr/local/sbin/hirup-deploy
# and triggered by .github/workflows/deploy.yml through a forced-command SSH key; see
# RUNBOOK.md "Automatic deployment from main". The argument is the full commit SHA and
# stdin carries a git bundle of main, so the VM needs no credentials for the repository.
[[ "$EUID" == 0 ]] || { printf 'Run as root.\n' >&2; exit 1; }
sha="${1:-}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { printf 'Expected one full 40-hex commit SHA.\n' >&2; exit 2; }

checkout=/opt/hirup/current
settings=/etc/hirup/deploy.env
state=/var/lib/hirup/releases
image="hirup-api:$sha"

exec 9>/run/hirup-deploy.lock
flock --nonblock 9 || { printf 'Another deployment is running.\n' >&2; exit 75; }

domain="$(sed -n 's/^HIRUP_DOMAIN=//p' "$settings" | tail -n 1)"
[[ "$domain" =~ ^[A-Za-z0-9.-]+$ ]] || { printf 'HIRUP_DOMAIN missing in %s.\n' "$settings" >&2; exit 1; }

bundle="$(mktemp /tmp/hirup-main.XXXXXX.bundle)"
trap 'rm -f "$bundle"' EXIT
head -c 200000000 > "$bundle"

cd "$checkout"
[[ -z "$(git status --porcelain)" ]] || { printf 'Checkout has local changes; refusing.\n' >&2; exit 1; }
git bundle verify --quiet "$bundle" >/dev/null
git fetch --quiet --force "$bundle" refs/heads/main:refs/remotes/origin/main
git merge-base --is-ancestor "$sha" origin/main || {
    printf 'Commit %s is not on main; refusing.\n' "$sha" >&2; exit 1;
}
git checkout --quiet --detach "$sha"
printf 'Building %s\n' "$image"
make --no-print-directory -f infra/Makefile deploy-image DEPLOY_API_IMAGE="$image" >/dev/null

status=0
python3 infra/deploy/ops.py release --image "$image" --url "https://$domain" || status=$?

# Keep the recorded current/previous releases and the two newest builds; drop the rest.
keep="$(cat "$state/current-image" "$state/previous-image" 2>/dev/null || true)"
docker image ls hirup-api --format '{{.Repository}}:{{.Tag}}' | tail -n +3 | while read -r old; do
    grep -qxF "$old" <<< "$keep" || docker image rm "$old" >/dev/null 2>&1 || true
done
exit "$status"
