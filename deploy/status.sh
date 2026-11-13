#!/bin/bash
set -eu
exec /root/miniconda3/bin/supervisorctl -c /root/autodl-tmp/rick-ppt/deploy/supervisord.conf status
