set -e; rm -rf /tmp/b58-before && mkdir -p /tmp/b58-before && cd /home/rich/metaform && cp -r src conftest.py pyproject.toml /tmp/b58-before/ && cd /tmp/b58-before && python3 - <<'EOF'
p='src/metaform/modules/dispatch/runner.py'
s=open(p).read()
a="        if waiting is not None:\n            self.pending[waiting] = text\n        else:\n            self.turn(text)\n        self.board_text = text\n"
assert s.count(a)==1
s=s.replace(a,"        self.turn(text)\n        self.board_text = None\n")
open(p,'w').write(s)
EOF
find /tmp/b58-before -name __pycache__ -type d -prune -exec rm -rf {} +
env -u METAFORM_ROLE -u METAFORM_SESSION -u METAFORM_WORK -u METAFORM_NODE -u METAFORM_AUTHORED_ROLE -u METAFORM_LEASE PYTHONPATH=/tmp/b58-before/src timeout 300 /home/rich/metaform/.venv/bin/python -m pytest -p no:cacheprovider -n 0 -q --tb=short src/metaform/modules/dispatch/tests/test_dispatch.py -k "one_turn_for_what_the_board"