#!/bin/bash
# Run the contract tests in a clean Boat sandbox. Sends only the files listed here:
# reference/ holds protected intake material and is never uploaded.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
cd "$root"
for file in metaform.schema.json validate_metaform.py mcp-tools.proposed.json \
    owner-skills-example.json provider-reference-example.json intake-example.json \
    tool-examples.json requirements-dev.txt tests/check_contract.py tests/check_tool_input.py; do
  mkdir -p "$stage/$(dirname "$file")"
  cp "$file" "$stage/$file"
done
cat > "$stage/run.sh" <<'SCRIPT'
set -eo pipefail
mkdir -p verification
python3 -m venv /tmp/v >/dev/null
/tmp/v/bin/pip -q install -r requirements-dev.txt
/tmp/v/bin/python tests/check_contract.py 2>&1 | tail -4
/tmp/v/bin/python tests/check_tool_input.py 2>&1 | tail -4
SCRIPT
boat run --no-env --type small --timeout 180 --push "$stage" bash run.sh
