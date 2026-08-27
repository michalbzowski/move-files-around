#!/usr/bin/env bash
# One-shot installer for host-side log retention of the move-files-around stack.
# Run as a normal user (it will sudo where needed):
#   ./host-etc/install-logrotate.sh
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)/logrotate.d/move-files-around"
DST_DIR="/etc/logrotate.d"
DST="${DST_DIR}/move-files-around"

[ -f "$SRC" ] || { echo "missing $SRC" >&2; exit 1; }

# Pick the docker group user so `su` inside logrotate is valid on this host.
docker_group_user="$(getent group docker >/dev/null 2>&1 && echo 'root docker' || echo 'root root')"
# Rewrite the `su` line to match this system before installing.
SRC_PATCHED="$(mktemp)"
sed "s/^    su root .*$/    su ${docker_group_user}/" "$SRC" > "$SRC_PATCHED"

sudo install -m 0644 -o root -g root "$SRC_PATCHED" "$DST"
rm -f "$SRC_PATCHED"
echo "installed: $DST"
echo "verify    : sudo logrotate -dv $DST"
echo "test-cycle: sudo logrotate -f $DST"
