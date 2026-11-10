"""The project registry in the core database, `metaform.db`. Ports `registry.rs`.

It holds each project's name and source folder. A project's own database never stores the
project's name (R-4.1).
"""
import sqlite3
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path


@dataclass(frozen=True)
class Registered:
    """One registered project: its id (the folder under `projects/`), its name and its source
    folder."""

    id: str
    name: str
    folder: str


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS project (id TEXT PRIMARY KEY, source TEXT NOT NULL UNIQUE, name TEXT NOT NULL)"
    )


def find(connection: sqlite3.Connection, source: str) -> str | None:
    """The registered project id for a source folder, if any."""
    row = connection.execute("SELECT id FROM project WHERE source = ?", (source,)).fetchone()
    return None if row is None else str(row[0])


def register(connection: sqlite3.Connection, home: Path, source: str, name: str) -> str:
    """Register `source` under `name`, or return its existing id. The id is the folder's
    canonical path with every character that is not an ASCII letter or digit replaced by `-`,
    followed by a three-digit number, the first that is free. The write lock makes the choice of
    the number and the row one step, so two processes cannot take one id."""
    found = find(connection, source)
    if found is not None:
        return found
    connection.execute("BEGIN IMMEDIATE")
    try:
        found = find(connection, source)
        if found is not None:
            connection.execute("COMMIT")
            return found
        encoded = "".join(c if c.isascii() and c.isalnum() else "-" for c in source)
        projects = home / "projects"
        number = 1
        while (projects / f"{encoded}{number:03}").exists():
            number += 1
        project = f"{encoded}{number:03}"
        folder = projects / project
        folder.mkdir(parents=True)
        (folder / "source.txt").write_text(f"{source}\n", encoding="utf-8")
        connection.execute("INSERT INTO project (id, source, name) VALUES (?, ?, ?)", (project, source, name))
        connection.execute("COMMIT")
        return project
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def list_projects(connection: sqlite3.Connection) -> list[Registered]:
    """Every registered project, by name and then id. Reads only; registers nothing."""
    rows = connection.execute("SELECT id, name, source FROM project").fetchall()
    return sorted((Registered(str(i), str(n), str(s)) for i, n, s in rows), key=attrgetter("name", "id"))
