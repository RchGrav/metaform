#!/usr/bin/env python3
"""One MCP connection to a form of Metaform, kept open for a harness that has no MCP client.

`metaform call` opens a new connection for each command, so `goto` delivers every part of its
summary sheet each time. An agent on a real MCP connection receives each part once per context
(R-5.30). This tool gives the same thing from a shell: `start` opens one connection and keeps
it, `send` performs one command on it, `end` closes it. Every command and answer is written to a
log with its size in bytes, so what the tool delivered to the agent can be measured afterwards.

    session.py start --dir DIR --home HOME --project FOLDER [--form rust|node|python]
    session.py send  --dir DIR '<json command>'      prints the answer; exit 1 if refused
    session.py end   --dir DIR                       closes the connection; prints the totals

DIR holds the session's socket and its log, `log.jsonl`: one line for each command, with the
command, the answer, whether it was refused, and both sizes in bytes.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conformance"))
from run import Connection  # noqa: E402  (the conformance check's MCP connection)


def serve(directory, form, home, project):
    """Hold the connection and answer `send` and `end` requests on a Unix socket."""
    connection = Connection(form, home, project, handshake=None)
    path = directory / "socket"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen(1)
    log = (directory / "log.jsonl").open("a")
    (directory / "ready").write_text("ready\n")
    try:
        while True:
            peer, _ = listener.accept()
            with peer, peer.makefile("rw") as stream:
                request = json.loads(stream.readline())
                if request.get("end"):
                    stream.write("{}\n")
                    return
                command = request["command"]
                try:
                    answer, refused = connection.call(command)
                except RuntimeError as error:
                    answer, refused = {"status": "error", "message": str(error)}, True
                sent = json.dumps(command, ensure_ascii=False, separators=(",", ":"))
                received = json.dumps(answer, ensure_ascii=False, separators=(",", ":"))
                log.write(json.dumps({
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "command": command, "answer": answer,
                    "refused": refused, "sent_bytes": len(sent.encode()),
                    "received_bytes": len(received.encode()),
                }, ensure_ascii=False) + "\n")
                log.flush()
                stream.write(json.dumps({"answer": received, "refused": refused}) + "\n")
    finally:
        connection.close()
        listener.close()
        path.unlink(missing_ok=True)


def ask(directory, request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.connect(str(directory / "socket"))
        with peer.makefile("rw") as stream:
            stream.write(json.dumps(request) + "\n")
            stream.flush()
            return json.loads(stream.readline())


def totals(directory):
    lines = [json.loads(line) for line in (directory / "log.jsonl").read_text().splitlines()]
    return {
        "commands": len(lines),
        "refused": sum(1 for line in lines if line["refused"]),
        "sent_bytes": sum(line["sent_bytes"] for line in lines),
        "received_bytes": sum(line["received_bytes"] for line in lines),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=["start", "send", "end", "serve"])
    parser.add_argument("command", nargs="?")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--form", default="rust", choices=["rust", "node", "python"])
    arguments = parser.parse_intermixed_args()
    directory = arguments.dir.resolve()
    if arguments.action == "serve":
        serve(directory, arguments.form, arguments.home, arguments.project)
        return 0
    if arguments.action == "start":
        if arguments.home is None or arguments.project is None:
            parser.error("start needs --home and --project")
        directory.mkdir(parents=True, exist_ok=True)
        arguments.home.mkdir(parents=True, exist_ok=True)
        (directory / "ready").unlink(missing_ok=True)
        subprocess.Popen(
            [sys.executable, __file__, "serve", "--dir", str(directory), "--form", arguments.form,
             "--home", str(arguments.home.resolve()), "--project", str(arguments.project.resolve())],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=(directory / "errors.txt").open("a"), start_new_session=True,
        )
        for _ in range(100):
            if (directory / "ready").exists():
                print(f"session started in {directory}")
                return 0
            time.sleep(0.1)
        print((directory / "errors.txt").read_text()[-2000:], file=sys.stderr)
        return 2
    if arguments.action == "send":
        try:
            command = json.loads(arguments.command or "")
        except json.JSONDecodeError as error:
            print(f"the command is not JSON: {error}", file=sys.stderr)
            return 2
        reply = ask(directory, {"command": command})
        print(reply["answer"])
        return 1 if reply["refused"] else 0
    ask(directory, {"end": True})
    print(json.dumps(totals(directory)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
