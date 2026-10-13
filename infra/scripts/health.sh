#!/usr/bin/env bash
# Check a real HTTP endpoint using only Bash available in both engine images.
set -euo pipefail
engine="${1:?engine is required}"
case "$engine" in
    otp)
        port=8080
        path=/otp/gtfs/v1
        payload='{"query":"{ __typename }"}'
        exec 3<>"/dev/tcp/127.0.0.1/$port"
        printf 'POST %s HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: %s\r\nConnection: close\r\n\r\n%s' \
            "$path" "${#payload}" "$payload" >&3
        ;;
    osrm)
        port=5000
        path='/nearest/v1/driving/106.800,-6.200?number=1'
        exec 3<>"/dev/tcp/127.0.0.1/$port"
        printf 'GET %s HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n' "$path" >&3
        ;;
    *) exit 2 ;;
esac
IFS= read -r status <&3
[[ "$status" == *' 200 '* ]]
body="$(cat <&3)"
if [[ "$engine" == otp ]]; then
    [[ "$body" == *'"__typename"'* && "$body" != *'"errors"'* ]]
else
    [[ "$body" == *'"code":"Ok"'* ]]
fi
