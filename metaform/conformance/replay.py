#!/usr/bin/env python3
"""Measure what a form delivers to an agent, by replaying recorded intake sessions.

`traces/` holds the commands that agents sent during real intakes, one file for each session,
in order. This tool sends each session's commands again to a form, on a new home and one
connection, and adds up the size of every answer. The same commands on two builds give two
totals that can be compared, so a change to what the tool answers can be measured.

    python3 metaform/conformance/replay.py --form rust|node|python [--trace NAME] [--parts]

It prints one line for each session and a total. `--parts` also prints the bytes by kind of
answer: successful writes, refusals, `goto`, `map`, `help`, raw dumps, `orphaned` and addressed reads.

What it establishes: the number of bytes these sessions would have received from this build.
What it does not establish: how an agent would have behaved with different answers. An agent
that receives less might send other commands.
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import Connection, end_server  # noqa: E402

TRACES = HERE / "traces"


def kind(command, refused):
    if refused:
        return "refusal"
    key = next(iter(command), "")
    if key in ("add", "update", "delete"):
        return "write"
    if key in ("goto", "map", "orphaned", "help"):
        return key
    return "dump" if key.startswith(".") else "read"


def replay(form, trace):
    """Replay one session. Returns (commands, refused, bytes sent, bytes received, by kind)."""
    commands = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    work = Path(tempfile.mkdtemp(prefix="metaform-replay-"))
    home, project = work / "home", work / "project"
    home.mkdir()
    project.mkdir()
    connection = Connection(form, home, project, None)
    sent = received = refusals = 0
    parts = {}
    try:
        for command in commands:
            answer, refused = connection.call(command)
            size = len(json.dumps(answer, ensure_ascii=False, separators=(",", ":")).encode())
            sent += len(json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode())
            received += size
            refusals += refused
            name = kind(command, refused)
            parts[name] = parts.get(name, 0) + size
    finally:
        connection.close()
        end_server(form, home)
        shutil.rmtree(work, ignore_errors=True)
    return len(commands), refusals, sent, received, parts


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--form", required=True, choices=["rust", "node", "python"])
    parser.add_argument("--trace", help="replay only the session with this name")
    parser.add_argument("--parts", action="store_true", help="print the bytes by kind of answer")
    arguments = parser.parse_args()
    traces = sorted(t for t in TRACES.glob("*.jsonl") if arguments.trace in (None, t.stem))
    if not traces:
        parser.error("no trace found")
    total = [0, 0, 0, 0]
    all_parts = {}
    for trace in traces:
        commands, refused, sent, received, parts = replay(arguments.form, trace)
        print(f"{trace.stem}: {commands} commands, {refused} refused, "
              f"{sent} bytes sent, {received} bytes received")
        for index, value in enumerate((commands, refused, sent, received)):
            total[index] += value
        for name, size in parts.items():
            all_parts[name] = all_parts.get(name, 0) + size
    print(f"total: {total[0]} commands, {total[1]} refused, "
          f"{total[2]} bytes sent, {total[3]} bytes received")
    if arguments.parts:
        for name, size in sorted(all_parts.items(), key=lambda item: -item[1]):
            print(f"  {name}: {size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
