"""The store's checks (`docs/designs/sqlite-forms.md`, section 5).

Each test starts the form as an agent's harness does, `python3 -m metaform`, on a new home in a
temporary folder. The tests read the database only to look at the layout.

    PYTHONPATH=metaform/python python3 -m unittest discover -s metaform/python/tests
"""
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {"name": "metaform-tests", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


def form(home: Path, project: Path, *arguments: str) -> list[str]:
    return [sys.executable, "-m", "metaform", *arguments, "--home", str(home), "--project", str(project)]


def environment() -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(PACKAGE))


def call(home: Path, project: Path, command: Any) -> tuple[int, Any, str]:
    """One `call`. Returns the exit status, the answer and what the form wrote to stderr."""
    done = subprocess.run(
        form(home, project, "call", json.dumps(command)), capture_output=True, text=True, env=environment()
    )
    return done.returncode, json.loads(done.stdout) if done.stdout.strip() else None, done.stderr


def start_server(home: Path, project: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        form(home, project, "mcp"), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=environment()
    )


def request(number: int, command: Any) -> str:
    params = {"name": "project-map", "arguments": command, "_meta": META}
    return json.dumps({"jsonrpc": "2.0", "id": number, "method": "tools/call", "params": params}) + "\n"


def acknowledged(line: str) -> int | None:
    """The id of the request that a complete answer line acknowledges as stored, or `None`."""
    if not line.endswith("\n"):
        return None
    reply = json.loads(line)
    return None if reply["result"]["isError"] else int(reply["id"])


def database(home: Path) -> sqlite3.Connection:
    (path,) = home.glob("projects/*/project.db")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def contents(home: Path) -> dict[str, list[Any]]:
    """Every table of the project's database with its rows."""
    connection = database(home)
    try:
        names = [name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return {name: sorted(connection.execute(f'SELECT * FROM "{name}"'), key=repr) for name in names}
    finally:
        connection.close()


def element(number: int, worker: int = 0) -> tuple[str, dict[str, Any]]:
    """An element that a write stores in several tables: four fields, a layer and a want."""
    address = f"code.worker{worker}.item{number}"
    return address, {
        "technical_name": f"item{number} worker{worker}",
        "name": f"Item {number} of worker {worker}",
        "role": "Supportive",
        "count": number,
        "sources": [f"./a{number}.md", f"./b{number}.md"],
        "wants": {"code.shared": {"why": "read ticks", "how": "delivers tick events", "direction": "inbound"}},
    }


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.home = Path(self.folder.name) / "home"
        self.project = Path(self.folder.name) / "project"
        self.project.mkdir()

    def write(self, command: Any) -> None:
        status, answer, problem = call(self.home, self.project, command)
        self.assertEqual((status, answer["status"]), (0, "ok"), problem or answer)

    def test_layout_is_one_table_for_each_field_and_layer(self) -> None:
        engine = {"technical_name": "game engine", "name": "Quake core", "role": "Definitive", "frame_count": 3, "framecount": 4}
        self.write({"add": {"code.engine.game": engine}})
        self.write({"add": {"code.bus": {"technical_name": "bus", "name": "Pulsar router", "role": "Supportive"}}})
        want = {"why": "receive input", "how": "dispatches events", "direction": "inbound"}
        self.write({"update": {"code.engine.game": {"wants": {"code.bus": want}, "sources": ["./a.md", "./b.md"]}}})
        before = contents(self.home)["l_sources"]
        self.write({"add": {"code.engine.game": {"sources": ["./c.md"]}}})
        tables = contents(self.home)

        fixed = {"map", "element", "wants", "field", "layer", "holds"}
        self.assertTrue(fixed <= set(tables))
        self.assertTrue(all(name.startswith(("f_", "l_")) for name in set(tables) - fixed), sorted(tables))
        keys = {address: key for key, _, address, _ in tables["element"]}
        self.assertEqual(
            set(keys),
            {".", "code", "code.bus", "code.engine", "code.engine.game", "layer", "layer.document", "layer.document.specification"},
        )
        game, bus = keys["code.engine.game"], keys["code.bus"]
        # Each field has its own table, with one row for each element that has the field.
        self.assertIn((game, '"game engine"'), tables["f_technicalName"])
        self.assertIn((bus, '"Pulsar router"'), tables["f_name"])
        self.assertIn(("frameCount",), tables["field"])
        # SQLite ignores the case of a table name, so the later of two such names has `f__`.
        self.assertEqual(tables["f_frameCount"], [(game, "3")])
        self.assertEqual(tables["f__framecount"], [(game, "4")])
        _, answer, _ = call(self.home, self.project, {"code.engine.game": {}})
        self.assertEqual((answer["code.engine.game"]["frame_count"], answer["code.engine.game"]["framecount"]), (3, 4))
        # Each layer has its own table, with one row for each record, in order.
        self.assertEqual(tables["l_sources"], [(game, 0, '"./a.md"'), (game, 1, '"./b.md"'), (game, 2, '"./c.md"')])
        self.assertEqual(tables["l_sources"][:2], before, "an appended record rewrote the rows before it")
        self.assertEqual(tables["holds"], [(game, "sources")])
        self.assertEqual(tables["wants"], [(game, bus, "receive input", "dispatches events", "inbound")])
        # No table holds a whole element: no row holds two of an element's values.
        for name, rows in tables.items():
            for row in rows:
                held = [value for value in ("game engine", "Quake core", "Definitive") if any(value in str(cell) for cell in row)]
                self.assertLessEqual(len(held), 1, f"{name}: {row}")

    def test_processes_that_write_at_once_all_have_their_writes_kept(self) -> None:
        workers, writes = 4, 12
        stored: list[list[int]] = [[] for _ in range(workers)]

        def work(worker: int) -> None:
            server = start_server(self.home, self.project)
            assert server.stdin is not None and server.stdout is not None
            for number in range(writes):
                address, fields = element(number, worker)
                server.stdin.write(request(number, {"add": {address: fields}}))
                server.stdin.flush()
                if acknowledged(server.stdout.readline()) == number:
                    stored[worker].append(number)
            server.stdin.close()
            server.stdout.close()
            server.wait(timeout=30)

        threads = [threading.Thread(target=work, args=(worker,)) for worker in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(stored, [list(range(writes))] * workers, "a write was refused or failed")
        status, answer, problem = call(self.home, self.project, {".": {}})
        self.assertEqual(status, 0, problem)
        for worker in range(workers):
            for number in range(writes):
                _, fields = element(number, worker)
                self.assertEqual(answer["."]["code"][f"worker{worker}"][f"item{number}"], fields)

    def test_an_ended_process_loses_no_acknowledged_write(self) -> None:
        writes, wait_for = 400, 25
        server = start_server(self.home, self.project)
        assert server.stdin is not None and server.stdout is not None

        def feed() -> None:
            # The commands go into the pipe faster than the process performs them, so the
            # process is writing when it is ended. The pipe breaks when the process ends.
            try:
                for number in range(writes):
                    server.stdin.write(request(number, {"add": dict([element(number)])}))
                server.stdin.flush()
            except OSError:
                pass

        feeder = threading.Thread(target=feed)
        feeder.start()
        stored = [acknowledged(server.stdout.readline()) for _ in range(wait_for)]
        server.send_signal(signal.SIGKILL)
        stored += [acknowledged(line) for line in server.stdout]
        server.wait(timeout=30)
        feeder.join()
        server.stdout.close()
        try:
            server.stdin.close()
        except OSError:
            pass
        self.assertNotIn(None, stored[:wait_for], "a write was refused or failed")
        self.assertLess(len(stored), writes, "the process finished before it was ended")

        status, answer, problem = call(self.home, self.project, {".": {}})
        self.assertEqual(status, 0, f"the database did not open: {problem}")
        items = answer["."]["code"]["worker0"]
        for number in stored:
            if number is not None:
                self.assertIn(f"item{number}", items, "an acknowledged write is missing")
        for name, fields in items.items():
            self.assertEqual(fields, element(int(name.removeprefix("item")))[1], "a half-written element is visible")

    def test_a_refused_write_stores_nothing(self) -> None:
        self.write({"add": {"code.engine.game": {"technical_name": "game engine", "name": "Quake core", "role": "Definitive"}}})
        before = contents(self.home)
        # The command has a new field and a new layer, and it is refused after both were applied
        # to the copy of the map: a map has one Definitive element.
        fields = {"technical_name": "main loop", "name": "Frame pump", "role": "Definitive", "brand_new": 1, "memory": ["note"]}
        status, answer, _ = call(self.home, self.project, {"add": {"code.loop.main": fields}})
        self.assertEqual((status, answer["code"]), (1, "ROLE_TAXONOMY_FAILURE"))
        after = contents(self.home)
        self.assertEqual(after, before)
        self.assertNotIn("f_brandNew", after)
        self.assertNotIn("l_memory", after)

    def test_a_home_with_another_format_marker_or_none_is_refused(self) -> None:
        command = {"add": {"code.engine": {"note": "x"}}}
        other = Path(self.folder.name) / "rust-home"
        other.mkdir()
        (other / "store.format").write_text("metaform-store 1\n")
        status, answer, problem = call(other, self.project, command)
        self.assertEqual((status, answer), (2, None))
        self.assertIn("holds a store of another format", problem)
        self.assertIn("metaform-store 1", problem)
        self.assertEqual(os.listdir(other), ["store.format"])

        unmarked = Path(self.folder.name) / "unmarked-home"
        unmarked.mkdir()
        (unmarked / "notes.txt").write_text("someone's file\n")
        status, answer, problem = call(unmarked, self.project, command)
        self.assertEqual((status, answer), (2, None))
        self.assertIn("holds files this store did not write (no store.format)", problem)
        self.assertEqual(os.listdir(unmarked), ["notes.txt"])


if __name__ == "__main__":
    unittest.main()
