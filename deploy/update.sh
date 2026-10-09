#!/bin/bash
# Runs ON THE SERVER every few minutes (see cron). If CI has published a newer image, it is pulled and the
# containers using it are restarted. If nothing changed, nothing happens. Output goes to the system log:
#   journalctl -t omnidoc-update
set -eu
exec > >(logger -t omnidoc-update) 2>&1
cd "$HOME/omnidoc"
docker compose pull --quiet
docker compose up -d --remove-orphans
docker image prune -f > /dev/null
