#!/usr/bin/env bash
# Empirically close F12 (mixed per-seat tools) and F13 (nondefault-bank review)
# against the roundtable crate, without any source edit. This only runs the
# crate's own tests and asserts the FINDINGS-required test AND are present and
# exercise the exact scenario.
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD/../..")

echo "=== F13: nondefault-bank review test must exist and be the lone-free review test ==="
F13_NEEDED=(
  'config(vec![busy, free], false, 700)'
  'ends_with("You have 700 Characters to Respond")'
)
for s in "${F13_NEEDED[@]}"; do
  if grep -qF "$s" "$ROOT/crates/roundtable/tests/engine.rs"; then
    echo "  ok: engine.rs contains: $s"
  else
    echo "  FAIL: engine.rs missing: $s"; exit 1
  fi
done

echo "=== F12: mixed per-seat tools test must exist (Some(tools) -> Tools line) ==="
F12_NEEDED=(
  'roundtable::ToolsEndpoint'
  "roundtable::spawn(\"p6\""
  'assert!(first.contains("- Tools: `advance`"), "{first}")'
  'Some(tools)'
)
for s in "${F12_NEEDED[@]}"; do
  if grep -qF "$s" "$ROOT/crates/roundtable/tests/engine.rs"; then
    echo "  ok: engine.rs contains: $s"
  else
    echo "  FAIL: engine.rs missing: $s"; exit 1
  fi
done

echo "=== Run both tests against the crate ==="
(
  cd "$ROOT"
  cargo test -p roundtable --test engine a_seat_with_tools_is_told_about_them
  cargo test -p roundtable --test engine a_lone_free_agent_is_asked_to_review_once_while_the_other_works
)
echo
echo "PASS: F12 mixed-tools and F13 nondefault-bank tests exist and pass against the crate."
