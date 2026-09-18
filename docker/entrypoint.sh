#!/usr/bin/env bash
# Container entrypoint.
#
# Started as root (the default) it aligns the "preform" user with PUID/PGID
# (default 1000) so files written to the mounted /jobs and /data directories
# belong to you, hands them to that user, then drops privileges. Started with
# --user it skips all of that and runs as whoever you chose.
#
#   run [args]   install PreFormServer if needed, then run it (the default)
#   <anything>   any preform-linux subcommand: doctor, printers, login, install, wine ...
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
  # Only the variables preform-linux understands cross the privilege drop
  # (PREFORM_*, FORMLABS_* account settings, QT_* and WINE* tuning).
  passthru=()
  while IFS= read -r name; do passthru+=("$name=${!name}"); done < <(compgen -e | grep -E '^(PREFORM_|FORMLABS_|QT_|WINE)' || true)
  exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups --reset-env \
    env HOME=/home/preform PATH="$PATH" "${passthru[@]}" "$0" "$@"
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
