"""`python3 -m metaform`: the command line of the Python form
(`docs/designs/sqlite-forms.md`, section 1). It has the role that `metaform-server/src/main.rs`
and `call.rs` have in the Rust form.

    python3 -m metaform mcp  [--home DIR] [--project DIR]   stdio MCP for an agent harness; DIR defaults to .
    python3 -m metaform call [--home DIR] [--project DIR] '<json command>' | -
                                                            one tool command; `-` reads it from stdin.
                                                            Exit 0 ok, 1 refused, 2 usage error.
    python3 -m metaform projects [--home DIR]               every registered project: id, name, folder

The home defaults to `METAFORM_HOME`, then `~/.metaform-sqlite`.
"""
import json
import sys
from pathlib import Path

from . import mcp, refusal
from .store import Store, StoreError, default_home
from .tool import MapTool
from .values import loads

USAGE = """usage: python3 -m metaform mcp  [--home DIR] [--project DIR]
       python3 -m metaform call [--home DIR] [--project DIR] '<json command>' | -
       python3 -m metaform projects [--home DIR]"""


def usage(problem: str) -> int:
    print(f"metaform: {problem}\n{USAGE}", file=sys.stderr)
    return 2


def open_tool(home: Path, project: Path) -> MapTool:
    """Open the home, register the project folder if it is new, and open its main map."""
    store = Store(home)
    return MapTool(store.main_map(store.register_project(project)))


def call(home: Path, project: Path, positional: list[str]) -> int:
    """`call`: print the tool's answer. Exit 0 ok, 1 refused, 2 usage or store error."""
    if len(positional) != 1:
        return usage("call takes one JSON command, or - to read it from stdin")
    text = sys.stdin.read() if positional[0] == "-" else positional[0]
    try:
        command = loads(text)
    except ValueError:
        command = None
    if not isinstance(command, dict):
        return usage("the command must be one JSON object, such as '{\".\": {}}'")
    answer, refused = open_tool(home, project).call(command)
    if not refused:
        print(answer)
        return 0
    # `INTERNAL_ERROR` is a store failure, not a refusal, so the exit status is 2, not 1.
    if json.loads(answer).get("code") == refusal.INTERNAL_ERROR:
        print(f"metaform: {answer}", file=sys.stderr)
        return 2
    print(answer)
    return 1


def projects(home: Path) -> int:
    """`projects`: print every project registered in the home."""
    listed = [{"id": p.id, "name": p.name, "folder": p.folder} for p in Store(home).projects()]
    print(json.dumps(listed, indent=2, ensure_ascii=False))
    return 0


def main(arguments: list[str]) -> int:
    home = default_home()
    project = Path(".")
    positional: list[str] = []
    rest = iter(arguments[1:])
    for argument in rest:
        if not argument.startswith("--"):
            positional.append(argument)
            continue
        value = next(rest, None)
        if argument == "--home" and value is not None:
            home = Path(value)
        elif argument == "--project" and value is not None:
            project = Path(value)
        else:
            return usage(f"unknown or incomplete option {argument}")
    command = arguments[0] if arguments else None
    try:
        if command == "call":
            return call(home, project, positional)
        if positional:
            if command == "projects":
                return usage("projects takes no arguments")
            return usage(f"unexpected argument {positional[0]}")
        if command == "projects":
            return projects(home)
        if command == "mcp":
            mcp.serve(open_tool(home, project))
            return 0
    except StoreError as error:
        print(f"metaform: {error}", file=sys.stderr)
        return 2 if command == "call" else 1
    return usage("expected mcp, call or projects")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
