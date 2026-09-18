#!/usr/bin/env bash
# Healthy once PreFormServer answers HTTP on its port with anything below 500.
code="$(curl -s -o /dev/null -m 4 -w '%{http_code}' "http://127.0.0.1:${PREFORM_PORT:-44388}/" || echo 000)"
[ "$code" -ge 200 ] && [ "$code" -lt 500 ]
