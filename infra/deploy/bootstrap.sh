#!/usr/bin/env bash
set -euo pipefail
# Run only on the chosen Ubuntu VM after reviewing the runbook.
[[ "$EUID" == 0 ]] || { printf 'Run as root on the deployment VM.\n' >&2; exit 1; }
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || {
    printf 'This bootstrap targets Ubuntu 24.04.\n' >&2; exit 1;
}
ssh_port="${1:-}"
[[ "$ssh_port" =~ ^[1-9][0-9]{0,4}$ && "$ssh_port" -le 65535 ]] || {
    printf 'Pass the existing SSH server port explicitly.\n' >&2; exit 1;
}
if [[ -n "${SSH_CONNECTION:-}" ]]; then
    read -r _ _ _ active_port <<< "$SSH_CONNECTION"
    [[ "$active_port" == "$ssh_port" ]] || {
        printf 'SSH port differs from the active session; refusing firewall changes.\n' >&2; exit 1;
    }
fi
directory="$(cd -- "$(dirname -- "$0")" && pwd)"
[[ "$directory" == /opt/hirup/current/infra/deploy ]] || {
    printf 'Install the checkout at /opt/hirup/current before bootstrapping.\n' >&2; exit 1;
}
[[ "$(dpkg --print-architecture)" == amd64 ]] || {
    printf 'This tested deployment profile targets x86-64.\n' >&2; exit 1;
}
if command -v docker >/dev/null 2>&1; then
    others="$(docker ps --filter 'label!=com.docker.compose.project=hirup-prod' -q)"
    [[ -z "$others" ]] || { printf 'Other containers found; review bootstrap manually.\n' >&2; exit 1; }
fi
apt-get update
apt-get install -y ca-certificates curl ufw python3
install -m 0755 -d /etc/apt/keyrings
curl --fail --location --retry 3 https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
arch="$(dpkg --print-architecture)"
printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: noble\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$arch" \
    > /etc/apt/sources.list.d/docker.sources
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
# This VM is dedicated to Hirup; do not alter another application's Docker ingress.
others="$(docker ps --filter 'label!=com.docker.compose.project=hirup-prod' -q)"
[[ -z "$others" ]] || { printf 'Other containers found; review firewall manually.\n' >&2; exit 1; }
if ! getent passwd hirup >/dev/null; then
    groupadd --gid 10001 hirup
    useradd --uid 10001 --gid 10001 --home-dir /var/lib/hirup --create-home \
        --shell /usr/sbin/nologin hirup
fi
[[ "$(id -u hirup)" == 10001 && "$(id -g hirup)" == 10001 ]] || {
    printf 'Hirup UID/GID must match the API image (10001).\n' >&2; exit 1;
}
install -d -m 0750 -o hirup -g hirup /var/lib/hirup/data
install -d -m 0700 -o root -g root /var/lib/hirup/releases
install -d -m 0750 -o root -g hirup /etc/hirup
# Preserve existing rules; permit SSH before enabling the firewall.
ufw insert 1 allow "$ssh_port/tcp"
ufw allow 80/tcp
ufw allow 443/tcp
ufw default deny incoming
ufw --force enable
install -m 0644 "$directory"/systemd/*.service "$directory"/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hirup-firewall.service
printf 'Bootstrap ready; configure deployment, health monitor and the P2 hook next.\n'
