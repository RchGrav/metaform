#!/usr/bin/env python3
"""Conformance check: every form of Metaform must give the same answers.

A case is a list of steps performed on a new, empty home through the form's stdio MCP server,
which is the surface an agent uses. Each `call` step sends one `project-map` command and compares
the answer with the recorded one, including the order of its keys. A `tools` step compares the
tool list. `reconnect` ends the connection and opens a new one on the same home, which shows
what is stored and what belongs to one context.

    python3 metaform/conformance/run.py --form rust|node|python [--case NAME] [--record]

`--record` writes the answers of the form into cases.json. Only the Rust form is recorded: it is
the reference, and its recorded answers are reviewed before they are committed.
Exit status: 0 every step matched, 1 a step differed, 2 the form could not be started.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
METAFORM = HERE.parent
CASES = HERE / "cases.json"

FORMS = {
    # METAFORM_RUST_BIN names another build of the Rust form, to compare two builds.
    "rust": [os.environ.get("METAFORM_RUST_BIN") or str(METAFORM / "rust/target/release/metaform")],
    "node": ["node", str(METAFORM / "node/src/main.ts")],
    "python": [sys.executable, "-m", "metaform"],
}
META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {"name": "metaform-conformance", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


class Connection:
    """One stdio MCP connection to a form, on one home and one project folder.

    With no handshake, every request carries the 2026-07-28 `_meta` fields. With a handshake
    version, the connection starts with `initialize`, as older clients do.
    """

    def __init__(self, form, home, project, handshake):
        env = dict(os.environ, METAFORM_LAUNCHER="")
        if form == "python":
            env["PYTHONPATH"] = str(METAFORM / "python")
        self.process = subprocess.Popen(
            FORMS[form] + ["mcp", "--home", str(home), "--project", str(project)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, cwd=str(project),
        )
        self.next = 0
        self.handshake = handshake
        if handshake:
            self.request("initialize", {
                "protocolVersion": handshake, "capabilities": {},
                "clientInfo": META["io.modelcontextprotocol/clientInfo"],
            })
            self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.next += 1
        if not self.handshake:
            params = dict(params, _meta=META)
        self.send({"jsonrpc": "2.0", "id": self.next, "method": method, "params": params})
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(
                    f"the form closed the connection during {method}: "
                    + self.process.stderr.read()[-2000:]
                )
            reply = json.loads(line)
            if reply.get("id") == self.next and "method" not in reply:
                return reply

    def call(self, command):
        """One tool command. Returns (answer, refused); the answer keeps its key order."""
        reply = self.request("tools/call", {"name": "project-map", "arguments": command})
        if "error" in reply:
            return {"protocol_error": reply["error"]}, True
        result = reply["result"]
        return json.loads(result["content"][0]["text"]), bool(result.get("isError"))

    def tools(self):
        return self.request("tools/list", {})["result"]["tools"]

    def close(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=10)
        except Exception:
            self.process.kill()


def end_server(form, home):
    """The Rust form leaves one server for the home. End it, so no process outlives the case.

    The server is found by its exact arguments, so no other process can match.
    """
    if form != "rust":
        return
    wanted = ["serve", "--home", str(home)]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            arguments = (entry / "cmdline").read_bytes().decode(errors="replace").split("\0")
        except OSError:
            continue
        if arguments[1:4] == wanted:
            try:
                os.kill(int(entry.name), signal.SIGTERM)
            except OSError:
                pass


def perform(form, case, record):
    """Perform one case. Returns the list of differences, as text."""
    work = Path(tempfile.mkdtemp(prefix="metaform-conformance-"))
    home, project = work / "home", work / "project"
    home.mkdir()
    project.mkdir()
    differences = []
    handshake = case.get("handshake")
    connection = Connection(form, home, project, handshake)
    try:
        for number, step in enumerate(case["steps"], 1):
            if step.get("reconnect"):
                connection.close()
                connection = Connection(form, home, project, handshake)
                continue
            is_call = "call" in step
            if is_call:
                answer, refused = connection.call(step["call"])
            else:
                answer, refused = connection.tools(), False
            if record:
                step["answer"] = answer
                if is_call:
                    step["refused"] = refused
                continue
            want = json.dumps(step.get("answer"), ensure_ascii=False)
            got = json.dumps(answer, ensure_ascii=False)
            want_refused = step.get("refused", False)
            if want != got or (is_call and refused != want_refused):
                asked = json.dumps(step["call"], ensure_ascii=False) if is_call else "tools/list"
                text = f"{case['name']} step {number}: {asked}\n  expected: {want}\n  received: {got}"
                if is_call and refused != want_refused:
                    text += f"\n  expected refused={want_refused}, received refused={refused}"
                differences.append(text)
    finally:
        connection.close()
        end_server(form, home)
        shutil.rmtree(work, ignore_errors=True)
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--form", required=True, choices=sorted(FORMS))
    parser.add_argument("--case", help="perform only the case with this name")
    parser.add_argument("--record", action="store_true",
                        help="write the form's answers into cases.json")
    arguments = parser.parse_args()
    if arguments.record and arguments.form != "rust":
        parser.error("only the Rust form is recorded; it is the reference")
    cases = json.loads(CASES.read_text())
    chosen = [case for case in cases if arguments.case in (None, case["name"])]
    if not chosen:
        parser.error(f"no case named {arguments.case}")
    differences, steps = [], 0
    for case in chosen:
        try:
            differences += perform(arguments.form, case, arguments.record)
        except (OSError, RuntimeError) as error:
            print(f"{case['name']}: {error}", file=sys.stderr)
            return 2
        steps += sum(1 for step in case["steps"] if not step.get("reconnect"))
    if arguments.record:
        CASES.write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n")
        print(f"recorded {steps} steps in {len(chosen)} cases from the {arguments.form} form")
        return 0
    for difference in differences:
        print(difference)
    print(f"{arguments.form}: {len(chosen)} cases, {steps} steps, {len(differences)} differences")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
