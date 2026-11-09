#!/bin/bash
# Runs inside a throwaway sandbox. From the repo root:
#   boat run --no-env --type small --timeout 280 --push experiments/ladybug-concurrency bash run.sh
python3 -m venv /tmp/v >/dev/null
/tmp/v/bin/pip -q install ladybug==0.22.1
/tmp/v/bin/python spike.py
/tmp/v/bin/python crash.py
mkdir -p /tmp/n && cp spike.mjs /tmp/n && cd /tmp/n && npm init -y >/dev/null 2>&1
# 0.22.1 needs @ladybugdb/core-linux-x64@0.22.1, which was not published on 2026-10-30.
npm i @ladybugdb/core@0.22.0 2>&1 | tail -1
timeout 60 node spike.mjs
