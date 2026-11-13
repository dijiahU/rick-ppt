#!/bin/bash
set -eu
ROOT=/root/autodl-tmp/rick-ppt
mkdir -p "$ROOT/deploy/private" "$ROOT/deploy/logs"
chmod 700 "$ROOT/deploy/private" "$ROOT/deploy/logs"
if /root/miniconda3/bin/supervisorctl -c "$ROOT/deploy/supervisord.conf" pid >/dev/null 2>&1; then
    exit 0
fi
exec /root/miniconda3/bin/supervisord -c "$ROOT/deploy/supervisord.conf"
