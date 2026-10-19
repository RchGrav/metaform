#!/bin/bash
# Usage: check-lock-parity.sh PROJECT_DIR PACKAGE...
# Compares each installed package version with its uv.lock entry. Exits 1 on any drift.
set -u
dir=$1
shift
cd "$dir" || exit 2
rc=0
for p in "$@"; do
  inst=$(uv pip show "$p" 2>/dev/null | sed -n 's/^Version: //p')
  lock=$(awk -v n="$p" '$0 == "name = \"" n "\"" {f = 1; next} f && /^version = / {gsub(/"/, "", $3); print $3; exit}' uv.lock)
  if [ -z "$inst" ] || [ "$inst" != "$lock" ]; then
    echo "DRIFT $p installed=${inst:-missing} locked=${lock:-missing}"
    rc=1
  else
    echo "ok    $p $inst"
  fi
done
exit $rc
