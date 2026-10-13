#!/bin/sh
set -eu
proxy_ips=${AERZEN_TRUSTED_PROXY_IPS:-127.0.0.1}
case "$proxy_ips" in *\**) printf '%s\n' 'Set explicit trusted proxy IPs, not *' >&2; exit 1;; esac
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --proxy-headers --forwarded-allow-ips="$proxy_ips"
