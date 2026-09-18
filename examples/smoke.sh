#!/usr/bin/env bash
# End-to-end check of a running PreFormServer using curl and python3 only.
# Also an example of driving the Formlabs Local API from a shell script.
#
#   PREFORM_URL=http://127.0.0.1:44388 \
#   SMOKE_LOCAL_DIR=$PWD/jobs      # where this script writes cube.stl and expects cube.form back
#   SMOKE_REMOTE_DIR=Z:/jobs       # the same directory as PreFormServer (under Wine) sees it
#   examples/smoke.sh
#
# For a bare-metal install SMOKE_REMOTE_DIR is "Z:$SMOKE_LOCAL_DIR"; for the
# Docker image with ./jobs mounted at /jobs it is "Z:/jobs" (the default).
set -euo pipefail

BASE="${PREFORM_URL:-http://127.0.0.1:44388}"
LOCAL_DIR="${SMOKE_LOCAL_DIR:-$PWD/jobs}"
REMOTE_DIR="${SMOKE_REMOTE_DIR:-Z:/jobs}"
MACHINE="${SMOKE_MACHINE:-FORM-4-0}"
MATERIAL="${SMOKE_MATERIAL:-FLGPBK05}"
ALLOW_SCREENSHOT_FAIL="${SMOKE_ALLOW_SCREENSHOT_FAIL:-1}"
POLL_TIMEOUT="${SMOKE_POLL_TIMEOUT:-600}"

failures=0
pass() { echo "[PASS] $*"; }
fail() { echo "[FAIL] $*"; failures=$((failures + 1)); }
check() { local name="$1"; shift; if "$@"; then pass "$name"; else fail "$name"; fi; }
json() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$1"; }

api() { # api METHOD PATH [JSON-BODY]
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then curl -sS -f -X "$method" -H 'Content-Type: application/json' -d "$body" "$BASE$path"
  else curl -sS -f -X "$method" "$BASE$path"; fi
}

op() { # op PATH JSON-BODY: POST ?async=true and poll /operations/{id}/ until it finishes; prints the result
  local path="$1" body="${2:-{\}}" accepted id status deadline
  accepted="$(curl -sS -f -X POST -H 'Content-Type: application/json' -d "$body" "$BASE$path?async=true")"
  id="$(json "d.get('operationId') or d.get('operation_id') or ''" <<<"$accepted")"
  if [ -z "$id" ]; then printf '%s' "$accepted"; return 0; fi
  deadline=$((SECONDS + POLL_TIMEOUT))
  while :; do
    local o; o="$(api GET "/operations/$id/")"
    status="$(json "d.get('status','')" <<<"$o")"
    case "$status" in
      SUCCEEDED) json "json.dumps(d.get('result'))" <<<"$o"; return 0 ;;
      FAILED) echo "operation $id failed: $(json "json.dumps(d.get('result'))" <<<"$o")" >&2; return 1 ;;
    esac
    [ "$SECONDS" -lt "$deadline" ] || { echo "operation $id timed out" >&2; return 1; }
    sleep 1
  done
}

cube_stl() { # 10 mm cube, ASCII STL
  python3 - <<'PY'
s = 10
v = [(0,0,0),(s,0,0),(s,s,0),(0,s,0),(0,0,s),(s,0,s),(s,s,s),(0,s,s)]
tris = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
print("solid cube")
for t in tris:
    print(" facet normal 0 0 0\n  outer loop")
    for i in t: print("   vertex %d %d %d" % v[i])
    print("  endloop\n endfacet")
print("endsolid cube")
PY
}

mkdir -p "$LOCAL_DIR"
rm -f "$LOCAL_DIR/cube.form" "$LOCAL_DIR/cube.png"
cube_stl >"$LOCAL_DIR/cube.stl"

echo "[smoke] PreFormServer at $BASE, local dir $LOCAL_DIR, remote dir $REMOTE_DIR"
version="$(api GET / | json "d.get('version') or d.get('preform_version') or json.dumps(d)")"
check "health: $version" test -n "$version"

materials="$(api GET /list-materials/)"
n="$(json "len(d.get('printer_types', d if isinstance(d, list) else []))" <<<"$materials" 2>/dev/null || echo 0)"
check "list-materials: $n printer types" test "$n" -gt 0

scene="$(api POST /scene/ "{\"machine_type\":\"$MACHINE\",\"material_code\":\"$MATERIAL\",\"layer_thickness_mm\":0.1}")"
sid="$(json "d.get('id','')" <<<"$scene")"
if [ -n "$sid" ]; then pass "create scene $sid ($MACHINE, $MATERIAL)"; else fail "create scene: $scene"; exit 1; fi

if op "/scene/$sid/import-model/" "{\"file\":\"$REMOTE_DIR/cube.stl\"}" >/dev/null; then
  models="$(api GET "/scene/$sid/" | json "len(d.get('models', []))")"
  check "import-model ($models model in scene)" test "$models" = 1
else fail "import-model"; fi

for step in auto-orient auto-support auto-layout; do
  if op "/scene/$sid/$step/" "{}" >/dev/null; then pass "$step"; else fail "$step"; fi
done

est="$(op "/scene/$sid/estimate-print-time/" "{}" || true)"
secs="$(json "d.get('total_print_time_s','')" <<<"$est" 2>/dev/null || true)"
check "estimate-print-time: ${secs}s ($est)" test -n "$secs"

if op "/scene/$sid/save-form/" "{\"file\":\"$REMOTE_DIR/cube.form\"}" >/dev/null && [ -s "$LOCAL_DIR/cube.form" ]; then
  pass "save-form: $LOCAL_DIR/cube.form ($(wc -c <"$LOCAL_DIR/cube.form" | tr -d ' ') bytes)"
else fail "save-form"; fi

if op "/scene/$sid/save-screenshot/" "{\"file\":\"$REMOTE_DIR/cube.png\",\"image_size_px\":512,\"view_type\":\"ZOOM_ON_MODELS\"}" >/dev/null && [ -s "$LOCAL_DIR/cube.png" ]; then
  pass "save-screenshot: $LOCAL_DIR/cube.png"
elif [ "$ALLOW_SCREENSHOT_FAIL" = 1 ]; then echo "[WARN] save-screenshot failed (rendering under Wine/Xvfb); allowed"
else fail "save-screenshot"; fi

# PreFormServer ships one built-in virtual printer per model ("Form 4", "Fuse 1+", ...;
# connection_type VIRTUAL). Printing to one runs the whole job upload path without
# hardware, so this is the closest thing to a print test a CI runner can do.
if r="$(op "/scene/$sid/print/" '{"printer":"Form 4","job_name":"smoke"}')"; then
  pass "print to the virtual Form 4: job $(json "d.get('job_id','')" <<<"$r")"
else fail "print to the virtual Form 4"; fi

api DELETE "/scene/$sid/" >/dev/null 2>&1 || true

# Printer discovery must at least fail cleanly under Wine: a broadcast scan (no mDNS
# answers arrive) and a directed probe of an address nothing answers on (TEST-NET-2;
# PreFormServer parks its built-in virtual printers on TEST-NET-1, 192.0.2.x).
if d="$(op /discover-devices/ '{"timeout_seconds":2}')"; then pass "discover-devices (broadcast): $(json "d.get('count', 0)" <<<"$d") found"; else fail "discover-devices (broadcast)"; fi
if d="$(op /discover-devices/ '{"ip_address":"198.51.100.1","timeout_seconds":3}')"; then pass "discover-devices at 198.51.100.1: $(json "d.get('count', 0)" <<<"$d") found (expected 0)"; else fail "discover-devices at 198.51.100.1"; fi
if d="$(api GET /devices/)"; then pass "devices: $(json "d.get('count', len(d.get('devices', [])))" <<<"$d") known"; else fail "devices"; fi
echo "[smoke] $failures failure(s)"
[ "$failures" = 0 ]
