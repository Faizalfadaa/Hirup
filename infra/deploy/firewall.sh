#!/usr/bin/env bash
set -euo pipefail
# UFW alone does not filter Docker's forwarded published ports.
for binary in iptables ip6tables; do
    if ! "$binary" -n -L DOCKER-USER >/dev/null 2>&1; then
        [[ "$binary" == ip6tables ]] && continue
        printf 'Docker iptables DOCKER-USER chain unavailable.\n' >&2; exit 1
    fi
    "$binary" -N HIRUP-INGRESS 2>/dev/null || true
    add() { "$binary" -C HIRUP-INGRESS "$@" 2>/dev/null || "$binary" -A HIRUP-INGRESS "$@"; }
    add -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
    add -i docker0 -j RETURN
    add -i br+ -j RETURN
    add -p tcp -m multiport --dports 80,443 -j RETURN
    add -j DROP
    "$binary" -C DOCKER-USER -j HIRUP-INGRESS 2>/dev/null || \
        "$binary" -I DOCKER-USER 1 -j HIRUP-INGRESS
done
