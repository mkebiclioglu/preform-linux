#!/usr/bin/env bash
# Container entrypoint: install (no-op when already installed at the pinned version), then run.
set -euo pipefail
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
