"""The project map: a store on LadybugDB (`store`) and the command engine of the `project` tool (`commands`).

This package is part of the public base. A module reads and writes a project's map through the names below and
through nothing beneath them; none of them opens a database, which the home's single-writer service alone holds.
"""
from __future__ import annotations

from pathlib import Path

from metaform.project.texts import COMMANDS, ROLE_WORDS

__all__ = ['COMMANDS', 'MEMORY_URI', 'ROLE_WORDS', 'bases', 'clear', 'cypher', 'drawn', 'holds', 'memory', 'memory_answer',
           'memory_tools', 'memory_tools_changing', 'overlay_record', 'overlay_records', 'run', 'specification_document',
           'stored_name']

MEMORY_URI = 'memory://knowledge-graph'  # the memory layer's whole graph as a resource, as the reference serves it


def memory_tools() -> tuple[dict[str, object], ...]:
    """The memory layer's nine tools as the MCP reference memory server registers them: name, title, description,
    input and output schemas and annotations."""
    from metaform.project import memory_layer
    return memory_layer.TOOLS


def memory_tools_changing() -> tuple[str, ...]:
    """The memory tools that change the graph, after which a subscribed client is told the graph was updated."""
    from metaform.project import memory_layer
    return memory_layer.MUTATIONS


def run(command: object, home: Path | None = None, caller: str = '') -> dict[str, object]:
    """Answer one command of the project tool: one JSON command in, one JSON answer out, `commands.run`."""
    from metaform.project import commands
    return commands.run(command, home, caller)


def memory(project: str, tool: str, arguments: object, home: Path | None = None,
           caller: str = '') -> dict[str, object]:
    """Call one of the memory layer's tools, the MCP reference memory server's nine, on a project: `memory.run`."""
    from metaform.project import memory_layer
    return memory_layer.run(project, tool, arguments, home, caller)


def memory_answer(tool: str, arguments: dict[str, object], result: object) -> tuple[list[str], dict[str, object]]:
    """A memory tool's result as the reference returns it: its text items and its structured content."""
    from metaform.project import memory_layer
    return memory_layer.answer(tool, arguments, result)


def drawn(project: str, home: Path | None = None) -> dict[str, object] | None:
    """Everything a display draws of a project in one read, or None when the store holds no such project."""
    from metaform.project import commands
    return commands.drawn(project, home)


def overlay_records(project: str, key: str, home: Path | None = None, at: str | None = None,
                    below: bool = False) -> list[dict[str, object]] | None:
    """Every record of one overlay across a project, each with its element's path and its position there, for a
    display that lists them all; None when the store holds no such project. With `at`, an element's address beneath
    the project, only the records it holds, and with `below` those beneath it too, selected in the store."""
    from metaform.project import commands
    return commands.overlay_records(project, key, home, at, below)


def overlay_record(project: str, key: str, field: str, value: object,
                   home: Path | None = None) -> dict[str, object] | None:
    """The one record of an overlay whose `field` holds `value`, such as a ticket by its id, open or completed, with
    `completed` when it is; None when no record holds it. A reference resolves; nothing else completed is read."""
    from metaform.project import commands
    return commands.overlay_record(project, key, field, value, home)


def cypher(project: str, query: str, home: Path | None = None, caller: str = '') -> dict[str, object]:
    """A Cypher query over a project's graph, run by the home's service on a reader inside a read-only transaction:
    `{'columns': [names], 'rows': [[values]]}`. A query that would write, or that the engine cannot answer, is refused
    as the tool's refusals are, with `status`, `code` and `message`, and changes nothing."""
    from metaform import home as metaform_home
    from metaform.project import service
    where = home if home is not None else metaform_home.home()
    return service.send(None, where, caller or 'cypher', cypher={'project': project, 'query': query})


def clear(project: str, home: Path | None = None) -> bool:
    """Remove a project's map from the store. False when it holds none."""
    from metaform.project import commands
    return commands.clear(project, home)


def holds(project: str, home: Path | None = None) -> bool:
    """Whether the store holds a map of this project, asked of the folder: no database is opened and no read made."""
    from metaform import home as metaform_home
    return ((home if home is not None else metaform_home.home()) / 'maps' / f'{project}.lbug').exists()


def stored_name(project_id: str) -> str:
    """The name a registered project has in the project store: its id, with the underscores a step is written with."""
    return project_id.lower().replace('-', '_')


def specification_document(project: str, document: str | None = None, home: Path | None = None,
                           caller: str = '') -> dict[str, object]:
    """A project's specification document (kickoff 2026-11-17 Phase 4): with no document, `{'document': ...}`, its
    export; with one, its import, `{'status': 'ok', 'changed': [...]}`, all or nothing. A refusal answers as the tool's
    refusals do."""
    from metaform import home as metaform_home
    from metaform.project import service
    where = home if home is not None else metaform_home.home()
    return service.send(None, where, caller or 'specification',
                        specification={'project': project, 'document': document})


def bases(project: str, op: str = 'list', name: str = '', home: Path | None = None) -> dict[str, object]:
    """A project's bases, the maps it keeps of itself (`metaform.project.base_maps`): op=list, the default, answers each
    with whether it is active and mapped; add, collapse, activate and remove change them by `name`. A refusal answers
    as the tool's refusals do."""
    from metaform import home as metaform_home
    from metaform.project import service
    where = home if home is not None else metaform_home.home()
    return service.send(None, where, 'bases', bases={'project': project, 'op': op, 'name': name})
