#!/usr/bin/env bash
# Container entrypoint.
#
# Started as root (the default) it aligns the "preform" user with PUID/PGID
# (default 1000) so files written to the mounted /jobs and /data directories
# belong to you, hands them to that user, then drops privileges. Started with
# --user it skips all of that and runs as whoever you chose.
#
#   run [args]   install PreFormServer if needed, then run it (the default)
#   <anything>   any preform-linux subcommand: doctor, install, wine ...
set -euo pipefail

if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-1000}"
  PGID="${PGID:-1000}"
  if [ "$(id -g preform)" != "$PGID" ]; then groupmod -o -g "$PGID" preform; fi
  if [ "$(id -u preform)" != "$PUID" ]; then usermod -o -u "$PUID" preform; fi
  for d in /data /jobs /home/preform; do
    [ -d "$d" ] || continue
    if [ "$(stat -c %u "$d")" != "$PUID" ] || [ "$(stat -c %g "$d")" != "$PGID" ]; then
      chown -R "$PUID:$PGID" "$d"
    fi
  done
  exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups --reset-env \
    env HOME=/home/preform PATH="$PATH" \
        PREFORM_LINUX_HOME="${PREFORM_LINUX_HOME:-/data}" PREFORM_PORT="${PREFORM_PORT:-44388}" \
        PREFORM_VERSION="${PREFORM_VERSION:-latest}" PREFORM_SHIM_DLL="${PREFORM_SHIM_DLL:-}" \
        PREFORM_SHIM="${PREFORM_SHIM:-}" PREFORM_TELEMETRY="${PREFORM_TELEMETRY:-}" \
        PREFORM_INSTALL_UNVERIFIED="${PREFORM_INSTALL_UNVERIFIED:-}" PREFORM_WINE_UNCHECKED="${PREFORM_WINE_UNCHECKED:-}" \
        QT_OPENGL="${QT_OPENGL:-software}" WINEDEBUG="${WINEDEBUG:--all}" \
    "$0" "$@"
fi

case "${1:-run}" in
  run)
    shift || true
    preform-linux install
    exec preform-linux run "$@"
    ;;
  *)
    exec preform-linux "$@"
    ;;
esac
