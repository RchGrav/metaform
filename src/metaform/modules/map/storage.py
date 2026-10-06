"""Map's work queue, messages, challenges, plans and report records.

Tables and operations are owned here and installed through the public DAO.
Legacy physical names preserve existing stores and exchange documents.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from typing import Any, cast

from metaform.data import (
    COLUMNS,
    CONDITIONS,
    LIMIT,
    MESSAGES,
    TAKEN,
    TICKETS,
    Answer,
    ChallengeState,
    Column,
    Data,
    DataConnection,
    DataRow,
    Element,
    Index,
    Item,
    Join,
    Message,
    Node,
    Notice,
    Operation,
    Outcome,
    Page,
    PastWork,
    Plan,
    Provenance,
    Ref,
    Report,
    Step,
    StoreError,
    Table,
    Tables,
    Ticket,
    Where,
    WorkLink,
    WorkRecord,
    as_object,
    new_id,
    now,
    paged,
    sliced,
)
from metaform.data import (
    DataTx as Tx,
)

Row = DataRow
ANSWERS = ("A", "B", "C")
WORK_FIELDS = ("condition", "note", "task", "held", "reviewed")
REPORT_KINDS = ("report", "feedback", "shape")
JOINS_AT = (  # the current joins an element receives or holds
    "SELECT join_id FROM current_joins WHERE receiver=? UNION SELECT c.join_id FROM join_elements e "
    "JOIN current_joins c ON c.row = e.join_row WHERE e.element_id=?"
)


def _work_text(value: Any, field: str, notices: list[Notice]) -> str | None:
    """A note, task or resolution: text, or anything else kept as JSON text with a notice, BASE-044."""
    if value is None or isinstance(value, str):
        return value
    notices.append(Notice(field, f"{field} is not text; it was stored as JSON text."))
    return json.dumps(value, ensure_ascii=False)


def _condition(value: Any, notices: list[Notice]) -> str:
    """The condition as given; a missing one is stored as empty text, since the column is never null, BASE-044."""
    if value in CONDITIONS:
        return str(value)
    if value is None:
        notices.append(Notice("condition", "condition is missing; stored empty."))
        return ""
    if value in MESSAGES:
        notices.append(
            Notice(
                "condition",
                f"A {value} is not the condition of a part; it was stored as given. Ask the "
                "user with metaform map ask, and leave a message with metaform map tell.",
            )
        )
        return str(value)
    notices.append(
        Notice(
            "condition", f"{value!r} is not missing, broken, flawed, enhancement or exclude; it was stored as given."
        )
    )
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _work_row(tx: Tx, work_id: str) -> Any:
    row = tx.execute("SELECT * FROM work WHERE work_id=?", (work_id,)).fetchone()
    if row is None:
        raise StoreError(f"No work record has the id {work_id}.", "metaform map work")
    return row


def add_work(
    tx: Tx,
    node: Any,
    condition: Any,
    *,
    note: Any = None,
    task: Any = None,
    held: Any = False,
    reviewed: Any = False,
    links: Any = (),
) -> WorkRecord:
    """Write the condition of an element or join as its own record, apart from the map, STORE-042."""
    notices: list[Notice] = []
    kind, thing = work_target(tx, node, notices)
    work_id = new_id()
    tx.execute(
        "INSERT INTO work(work_id, target_kind, target_id, condition, note, task, held, reviewed, created) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            work_id,
            kind,
            thing,
            _condition(condition, notices),
            _work_text(note, "note", notices),
            _work_text(task, "task", notices),
            int(bool(held)),
            int(bool(reviewed)),
            now(),
        ),
    )
    _link(tx, work_id, links, notices)
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def _link(tx: Tx, work_id: str, links: Any, notices: list[Notice]) -> None:
    """Replace the nodes a ticket links for reference, VIEW-035: each an element or a join, in the order given."""
    tx.execute("DELETE FROM work_links WHERE work_id=?", (work_id,))
    for number, node in enumerate(links or ()):
        kind, thing = work_target(tx, node, notices)
        tx.execute(
            "INSERT INTO work_links(work_id, number, target_kind, target_id) VALUES (?, ?, ?, ?)",
            (work_id, number, kind, thing),
        )


def edit_work(tx: Tx, work_id: str, changes: Any) -> WorkRecord:
    """Change a work record's fields, attachment or reference links in place, preserving its identity and progress."""
    notices: list[Notice] = []
    _work_row(tx, work_id)
    given = as_object(changes)
    if given is None:
        raise StoreError("The changes to a work record are an object of its fields.", "metaform help map work")
    for key in sorted(given):
        if key == "node":
            kind, thing = work_target(tx, given[key], notices)
            tx.execute("UPDATE work SET target_kind=?, target_id=? WHERE work_id=?", (kind, thing, work_id))
            continue
        if key == "links":
            _link(tx, work_id, given[key], notices)
            continue
        if key not in WORK_FIELDS:
            notices.append(Notice(key, f"A work record has no field {key}; it was not stored."))
            continue
        value: Any = given[key]
        if key == "condition":
            value = _condition(value, notices)
        elif key in ("held", "reviewed"):
            value = int(bool(value))
        else:
            value = _work_text(value, key, notices)
        tx.execute(f"UPDATE work SET {key}=? WHERE work_id=?", (value, work_id))
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def _message_row(tx: Tx, message_id: str) -> Any:
    row = tx.execute("SELECT * FROM messages WHERE message_id=?", (message_id,)).fetchone()
    if row is None:
        raise StoreError(f"No question or message has the id {message_id}.", "metaform map messages")
    return row


def add_message(tx: Tx, node: Any, kind: str, text: Any, *, suggestions: Any = None, by: Any = None) -> Message:
    """What an agent says to the user at a node, MAP-050: a question, with the answers it suggests, or a message.
    Nothing is refused: a question with no suggestions is stored, and the agent is told to suggest."""
    notices: list[Notice] = []
    target_kind, thing = work_target(tx, node, notices)
    suggested: list[str] = []
    if isinstance(suggestions, (list, tuple)):
        suggested = [
            one if isinstance(one, str) else json.dumps(one, ensure_ascii=False)
            for one in cast("list[Any] | tuple[Any, ...]", suggestions)
        ]
    elif suggestions is not None:
        notices.append(
            Notice("suggestions", "suggestions is a list of answers; what was sent was kept as the one suggestion.")
        )
        suggested = [suggestions if isinstance(suggestions, str) else json.dumps(suggestions, ensure_ascii=False)]
    if kind == "question" and not suggested:
        notices.append(
            Notice(
                "suggestions",
                "This question has no suggestions. Ask with the answers you suggest, the "
                'one you recommend first: suggestions=["...", "..."].',
            )
        )
    message_id = new_id()
    tx.execute(
        "INSERT INTO messages(message_id, target_kind, target_id, kind, text, suggestions, by, created) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            message_id,
            target_kind,
            thing,
            kind,
            _work_text(text, "text", notices),
            json.dumps(suggested, ensure_ascii=False) if suggested else None,
            _work_text(by, "by", notices),
            now(),
        ),
    )
    return message(tx, _message_row(tx, message_id), tuple(notices))


def close_message(tx: Tx, message_id: str, answer: Any = None) -> Message:
    """The user answered a question or read a message. One already closed keeps its first answer."""
    notices: list[Notice] = []
    row = _message_row(tx, message_id)
    if row["closed"] is not None:
        notices.append(Notice("message_id", f"This was closed at {row['closed']}; its answer was kept."))
        return message(tx, row, tuple(notices))
    tx.execute(
        "UPDATE messages SET closed=?, answer=? WHERE message_id=?",
        (now(), _work_text(answer, "answer", notices), message_id),
    )
    return message(tx, _message_row(tx, message_id), tuple(notices))


def move_message(tx: Tx, message_id: str, node: Node) -> Message:
    """Move a question or message to another node, keeping its identity, suggestions, answer and closed state."""
    _message_row(tx, message_id)
    notices: list[Notice] = []
    kind, thing = work_target(tx, node, notices)
    tx.execute("UPDATE messages SET target_kind=?, target_id=? WHERE message_id=?", (kind, thing, message_id))
    return message(tx, _message_row(tx, message_id), tuple(notices))


def reopen_message(tx: Tx, message_id: str) -> Message:
    """A question answered by mistake waits again, with its suggestions and no answer, MAP-050. Only a question is
    reopened; one already open is left as it is."""
    row = _message_row(tx, message_id)
    if row["kind"] != "question":
        raise StoreError("Only a question is reopened; this is a message.", "metaform map messages kind=question")
    if row["closed"] is None:
        return message(tx, row, (Notice("message_id", "This question is open; it was left as it is."),))
    tx.execute("UPDATE messages SET closed=NULL, answer=NULL WHERE message_id=?", (message_id,))
    return message(tx, _message_row(tx, message_id))


def _count(value: Any, notices: list[Notice]) -> int | None:
    """The steps an agent plans: a whole number from 0, or none, which means the task has no steps. Anything else is
    named and read as none, BASE-044."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    notices.append(Notice("steps", f"{value!r} is not a count of steps; the task was left with no count."))
    return None


def plan_work(tx: Tx, work_id: str, steps: Any) -> WorkRecord:
    """The agent says how many steps it plans, or says it again when its plan changes, MAP-053. A count below the
    steps already done is raised to them, since what is done is done."""
    notices: list[Notice] = []
    row = _work_row(tx, work_id)
    count = _count(steps, notices)
    done = int(row["steps_done"] or 0)
    if count is not None and count < done:
        notices.append(Notice("steps", f"{done} steps are done already; the count was set to {done}."))
        count = done
    tx.execute("UPDATE work SET steps=? WHERE work_id=?", (count, work_id))
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def step_work(tx: Tx, work_id: str, said: Any = None) -> WorkRecord:
    """The agent finished a step, and says what it did, MAP-053. Nothing is refused: a step beyond the count raises
    the count, and a step on a record never taken or already done is stored, each named in a notice."""
    notices: list[Notice] = []
    row = _work_row(tx, work_id)
    if row["done"] is not None:
        notices.append(Notice("done", f"This work record was done at {row['done']}; the step was stored."))
    elif row["taken"] is None:
        notices.append(
            Notice(
                "condition",
                "This task was not taken when the step was reported; the step was stored. "
                "Take a task before its first step.",
            )
        )
    done = int(row["steps_done"] or 0) + 1
    planned = row["steps"]
    if planned is not None and done > int(planned):
        notices.append(Notice("steps", f"Step {done} is beyond the {planned} planned; the count was raised to {done}."))
        planned = done
    tx.execute("UPDATE work SET steps=?, steps_done=? WHERE work_id=?", (planned, done, work_id))
    tx.execute(
        "INSERT INTO work_steps(work_id, number, said, at) VALUES (?, ?, ?, ?)",
        (work_id, done, _work_text(said, "said", notices), now()),
    )
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def take_work(tx: Tx, work_id: str, steps: Any = None, by: Any = None) -> WorkRecord:
    """An agent takes the record's task, MAP-049: it is in progress, keeps its kind, VIEW-035, records who took it, and
    waits no longer. A record taken or done cannot be taken again, so two agents never hold one task. A record with no
    condition, as the intake writes a drift finding, is taken as a ticket is."""
    row = _work_row(tx, work_id)
    condition = str(row["condition"])
    if row["done"] is not None:
        raise StoreError(f"This work record was done at {row['done']}.", "metaform map work open=true")
    if row["taken"] is not None:
        # The agent that took it and stopped resumes it with op=plan; any other finds open work with the list.
        raise StoreError(
            f"This task is already taken, by {row['taken_by'] or 'an agent'} at {row['taken']}. The agent "
            "that took it resumes with op=plan and op=step; any other agent finds open work with "
            "metaform map work open=true.",
            f"metaform map work op=plan id={work_id} steps=<n>",
        )
    if condition and condition not in TICKETS:
        raise StoreError(f"A {condition} has no task to take.", "metaform map work open=true")
    notices: list[Notice] = []
    tx.execute(
        "UPDATE work SET taken=?, taken_by=?, held=0, steps=COALESCE(?, steps) WHERE work_id=?",
        (now(), _work_text(by, "by", notices), _count(steps, notices), work_id),
    )
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def move_work(tx: Tx, work_id: str, column: Any, position: Any = None, by: Any = None) -> WorkRecord:
    """Put a ticket in a column of the board, and at a place in it, MAP-048: backlog holds it, to do frees it, doing
    takes it and done finishes it; a ticket moved back out of doing or done is open and untaken again."""
    row = _work_row(tx, work_id)
    if column not in COLUMNS:
        raise StoreError(f"{column!r} is not a column: backlog, todo, doing or done.", "metaform help map work")
    notices: list[Notice] = []
    if work_record(tx, row).column == column:
        pass  # Within a column only the order changes.
    elif column == "done":
        tx.execute("UPDATE work SET done=COALESCE(done, ?), held=0 WHERE work_id=?", (now(), work_id))
    elif column == "doing":
        tx.execute(
            "UPDATE work SET done=NULL, held=0, taken=COALESCE(taken, ?), taken_by=COALESCE(?, taken_by) "
            "WHERE work_id=?",
            (now(), _work_text(by, "by", notices), work_id),
        )
    else:
        tx.execute(
            "UPDATE work SET done=NULL, taken=NULL, taken_by=NULL, held=? WHERE work_id=?",
            (int(column == "backlog"), work_id),
        )
    del row
    moved = work_record(tx, _work_row(tx, work_id))
    others = [
        record
        for record in (
            work_record(tx, other)
            for other in tx.execute(
                "SELECT * FROM work WHERE work_id<>? ORDER BY position IS NULL, position, row", (work_id,)
            )
        )
        if record.column == moved.column
    ]
    at = len(others) if position is None else max(0, min(len(others), int(position)))
    for place, record in enumerate([*others[:at], moved, *others[at:]]):
        tx.execute("UPDATE work SET position=? WHERE work_id=?", (place, record.work_id))
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def finish_work(tx: Tx, work_id: str, resolution: Any = None) -> WorkRecord:
    """Mark a work record done, keeping its resolution beside it; a record already done keeps its first resolution."""
    notices: list[Notice] = []
    row = _work_row(tx, work_id)
    if row["done"] is not None:
        notices.append(Notice("work_id", f"This work record was done at {row['done']}; its resolution was kept."))
        return work_record(tx, row, tuple(notices))
    tx.execute(
        "UPDATE work SET done=?, resolution=? WHERE work_id=?",
        (now(), _work_text(resolution, "resolution", notices), work_id),
    )
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def _past_work(tx: Tx, target: Node) -> tuple[PastWork, ...]:
    """Completed work at this node, newest first, without loading the agent's log, MAP-051."""
    return tuple(
        PastWork(str(row["work_id"]), str(row["done"]))
        for row in tx.execute(
            "SELECT work_id, done FROM work WHERE target_kind=? AND target_id=? AND done IS NOT NULL "
            "ORDER BY done DESC, row DESC",
            (target.kind, target.id),
        )
    )


def ticket(tx: Tx, work_id: str, *, selection: Sequence[str] | None = None, raw: bool = False) -> Ticket:
    """One ticket by its id with the where read of its node and of each node it links, MAP-048."""
    res = tx.reads.resolver(selection, tx.toggled)
    row = tx.execute("SELECT * FROM work WHERE work_id=?", (work_id,)).fetchone()
    if row is None:
        raise StoreError(f"No work record has the id {work_id}.", "metaform map work open=true")
    record = work_record(tx, row)
    at = tx.reads.node_where(res, raw, Node.of(record.kind, record.id))
    linked = tuple(tx.reads.node_where(res, raw, Node.of(link.kind, link.id)) for link in record.links)
    # What is read before the task: the read_first items its node's read and its linked nodes' reads show, LAYER-021.
    first = tuple(
        item
        for read in (at, *linked)
        if read is not None
        for group in read.layers
        for item in group.items
        if item.read_first
    )
    return Ticket(record, at, linked, read_first=first)


def work(
    tx: Tx,
    node: Node | None = None,
    condition: str | None = None,
    open: bool | None = None,
    *,
    limit: int = LIMIT,
    after: str | None = None,
    joins: bool = False,
) -> Page[WorkRecord]:
    """The work records, in row order, by node, condition or whether open, STORE-042; not a context read, since a
    work record has no layer. With joins, an element's own records and those on the joins it receives or
    provides."""
    target = work_target(tx, node, []) if node is not None else None
    around = joins and target is not None and target[0] == "element"

    def fetch(cursor: str | None, count: int) -> list[Row]:
        where: list[str] = ["row > ?"]
        params: list[Any] = [int(cursor or 0)]
        if target is not None and around:
            where.append(f"(target_kind=? AND target_id=? OR target_kind='join' AND target_id IN ({JOINS_AT}))")
            params.extend((*target, *[target[1]] * 2))
        elif target is not None:
            where.append("target_kind=? AND target_id=?")
            params.extend(target)
        shown = {taken: kind for kind, taken in TAKEN.items()}
        if condition in shown:  # in-progress is a missing ticket taken, and fixing a broken one, VIEW-035
            where.append("condition=? AND taken IS NOT NULL")
            params.append(shown[condition])
        elif condition is not None:
            where.append("condition=?")
            params.append(condition)
        if open is not None:
            where.append("done IS NULL" if open else "done IS NOT NULL")
        return tx.execute(
            f"SELECT row AS key, * FROM work WHERE {' AND '.join(where)} ORDER BY row LIMIT ?", (*params, count)
        ).fetchall()

    return paged(fetch, lambda row: work_record(tx, row), limit, after)


def messages(
    tx: Tx,
    node: Node | None = None,
    kind: str | None = None,
    open: bool | None = None,
    *,
    limit: int = LIMIT,
    after: str | None = None,
) -> Page[Message]:
    """The questions and messages, oldest first, by node, kind or whether they still wait, MAP-050; not a context
    read, since a message has no layer."""
    target = work_target(tx, node, []) if node is not None else None

    def fetch(cursor: str | None, count: int) -> list[Row]:
        where: list[str] = ["row > ?"]
        params: list[Any] = [int(cursor or 0)]
        if target is not None:
            where.append("target_kind=? AND target_id=?")
            params.extend(target)
        if kind is not None:
            where.append("kind=?")
            params.append(kind)
        if open is not None:
            where.append("closed IS NULL" if open else "closed IS NOT NULL")
        return tx.execute(
            f"SELECT row AS key, * FROM messages WHERE {' AND '.join(where)} ORDER BY row LIMIT ?", (*params, count)
        ).fetchall()

    return paged(fetch, lambda row: message(tx, row), limit, after)


def reports(
    tx: Tx, kind: str | None = None, layer: str | None = None, *, limit: int = LIMIT, after: str | None = None
) -> Page[Report]:
    """The report, feedback and shape files of this metaform, oldest first, STORE-043."""
    if layer is not None:
        layer_id = tx.rows.layer(layer).layer_id
        found = tuple(
            report_record(tx, row)
            for row in tx.execute("SELECT * FROM reports WHERE layer_id=? ORDER BY kind, report_id", (layer_id,))
            if kind is None or row["kind"] == kind
        )
        return sliced(found, limit, after)

    def fetch(cursor: str | None, count: int) -> list[Row]:
        created, _, name = (cursor or "|").partition("|")
        return tx.execute(
            "SELECT created || '|' || report_id AS key, * FROM reports "
            "WHERE (created, report_id) > (?, ?) ORDER BY created, report_id LIMIT ?",
            (created, name, count),
        ).fetchall()

    return paged(
        fetch, lambda row: report_record(tx, row) if kind is None or row["kind"] == kind else None, limit, after
    )


def report(tx: Tx, name: str) -> Report | None:
    row = tx.execute("SELECT * FROM reports WHERE report_id=?", (name,)).fetchone()
    return None if row is None else report_record(tx, row)


def save_report(tx: Tx, name: str, run_id: str, kind: str, size: int, layer: str | None = None) -> Report:
    """Record one report, feedback or shape file, or its new size after an append, STORE-043."""
    if kind not in REPORT_KINDS:
        raise StoreError(f"{kind!r} is not report, feedback or shape.", "metaform help feedback")
    layer_id = tx.rows.layer(layer).layer_id if layer else None
    tx.execute(
        "INSERT INTO reports(report_id, run_id, layer_id, kind, created, size) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(report_id) DO UPDATE SET size=MAX(size, excluded.size)",
        (name, run_id, layer_id, kind, now(), size),
    )
    return report_record(tx, tx.execute("SELECT * FROM reports WHERE report_id=?", (name,)).fetchone())


def work_record(tx: Tx, row: Row, notices: tuple[Notice, ...] = ()) -> WorkRecord:
    """One work row as a record, with its object's address, or its join's two ends, when the object is current."""
    kind, thing = str(row["target_kind"]), str(row["target_id"])
    address = receiver = provider = None
    if kind == "join":
        receiver, provider = tx.views.join_ends(thing)
    elif kind == "element":
        address = tx.rows.node_address(kind, thing)
    said = tuple(
        Step(int(step["number"]), step["said"], str(step["at"]))
        for step in tx.execute(
            "SELECT number, said, at FROM work_steps WHERE work_id=? ORDER BY number, row", (str(row["work_id"]),)
        )
    )
    links = tuple(
        WorkLink(
            str(link["target_kind"]),
            str(link["target_id"]),
            tx.rows.node_address(str(link["target_kind"]), str(link["target_id"])),
        )
        for link in tx.execute(
            "SELECT target_kind, target_id FROM work_links WHERE work_id=? ORDER BY number", (str(row["work_id"]),)
        )
    )
    return WorkRecord(
        str(row["work_id"]),
        kind,
        thing,
        address,
        receiver,
        provider,
        str(row["condition"]),
        row["note"],
        row["task"],
        bool(row["held"]),
        bool(row["reviewed"]),
        str(row["created"]),
        row["done"],
        row["resolution"],
        notices,
        row["steps"],
        int(row["steps_done"] or 0),
        said,
        row["taken"],
        row["taken_by"],
        row["position"],
        links,
    )


def message(tx: Tx, row: Row, notices: tuple[Notice, ...] = ()) -> Message:
    """One message row as a record, with its object's address or its join's two ends, as a work record has."""
    kind, thing = str(row["target_kind"]), str(row["target_id"])
    address = receiver = provider = None
    if kind == "join":
        receiver, provider = tx.views.join_ends(thing)
    elif kind == "element":
        address = tx.rows.node_address(kind, thing)
    try:
        read: Any = json.loads(row["suggestions"]) if row["suggestions"] else []
    except ValueError:
        read = []
    suggested = tuple(str(one) for one in cast(list[Any], read)) if isinstance(read, list) else ()
    held = tx.tables().get('question_work', {'message_id': str(row['message_id'])})
    return Message(
        str(row["message_id"]),
        str(row["kind"]),
        kind,
        thing,
        address,
        receiver,
        provider,
        row["text"],
        suggested,
        row["by"],
        str(row["created"]),
        row["closed"],
        row["answer"],
        notices,
        str(held['work_id']) if held is not None else None,
    )


def report_record(tx: Tx, row: Row) -> Report:
    layer_id = row["layer_id"]
    return Report(
        str(row["report_id"]),
        str(row["run_id"]),
        layer_id,
        tx.rows.layer_name(str(layer_id)) if layer_id else None,
        str(row["kind"]),
        str(row["created"]),
        int(row["size"]),
    )


def open_work(tx: Tx, kind: str, thing_id: str) -> tuple[str, ...]:
    """The conditions of an object's open work records, in row order, STORE-042; one lookup on `work_by_target`."""
    conditions = tuple(
        TAKEN.get(str(row[0]), str(row[0])) if row[1] else str(row[0])
        for row in tx.execute(
            "SELECT condition, taken FROM work WHERE target_kind=? AND target_id=? AND done IS NULL ORDER BY row",
            (kind, thing_id),
        )
    )
    # What waits for the user at the object is open at it too: a question not answered, a message not read, MAP-050.
    waiting = tuple(
        str(row[0])
        for row in tx.execute(
            "SELECT kind FROM messages WHERE target_kind=? AND target_id=? AND closed IS NULL ORDER BY row",
            (kind, thing_id),
        )
    )
    return conditions + waiting


def work_target(tx: Tx, node: Any, notices: list[Notice]) -> tuple[str, str]:
    """The kind and identity id a work record attaches to: the current element at an address, or the object with the
    id given. A node that names no current object is kept as written, with a notice,
    BASE-044."""
    if not isinstance(node, Node):
        raise StoreError(
            f"{node!r} is not a node: write element:<address or id> or join:<id>.", "metaform help map work"
        )
    kind, ident = node.kind, node.id
    if kind == "type":
        notices.append(
            Notice(
                "node",
                f"{node} is a type address, which no work record attaches to; it was stored as "
                "given, as an element node.",
            )
        )
        kind = "element"
    if kind == "element":
        current = tx.rows.current_element(ident)
        if current is not None:
            return kind, str(current["element_id"])
    elif tx.rows.target_current("join", ident):
        return kind, ident
    notices.append(
        Notice(
            "node",
            f"No current {kind} is at {ident}; the work record was stored as given and will "
            "show once one is recorded there.",
        )
    )
    return kind, ident


def answer(tx: Tx, item_id: str, state: Any, link: Node | None = None) -> ChallengeState | Outcome:
    """Record a challenge's answer beside the critic's layer, STORE-040."""
    if state == "plan":
        return Outcome(
            (
                Notice(
                    "answer",
                    "plan comes only from metaform map approve, which a person runs; nothing "
                    "was written. Answer A, B or C.",
                ),
            )
        )
    if state not in ANSWERS:
        raise StoreError(f"{state!r} is not an answer: use A, B or C.", f"metaform map answer {item_id} A")
    if tx.rows.kind_of(item_id) != "item":
        raise StoreError(f"{item_id} is not a challenge.", "metaform map layers")
    _, found = tx.rows.own_row("item", item_id)
    notices: list[Notice] = []
    if found.kind != "layer":
        notices.append(
            Notice(
                "challenge",
                f"{item_id} is in {found.name}, which is not a blind-spot layer; the answer was stored as given.",
            )
        )
    existing = tx.execute("SELECT state FROM challenge_states WHERE item_id=?", (item_id,)).fetchone()
    if existing is not None and existing[0] == "plan":
        notices.append(
            Notice("challenge", f"Challenge {item_id} was already approved as a plan; this answer was stored as given.")
        )
    link_kind: str | None = None
    link_id: str | None = None
    if state == "C":
        if link is None:
            notices.append(
                Notice(
                    "link",
                    "A C answer names the element or join that already handles the challenge; "
                    "give it with link=element:<address>. The answer was stored without it.",
                )
            )
        else:
            link_kind, link_id = tx.rows.node_at(link, found, "link", notices)
    stamp = now()
    tx.execute(
        "INSERT INTO challenge_states(item_id, state, link_kind, link_id, answered) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(item_id) DO UPDATE SET state=excluded.state, link_kind=excluded.link_kind, "
        "link_id=excluded.link_id, answered=excluded.answered",
        (item_id, state, link_kind, link_id, stamp),
    )
    # `state` is one of ANSWERS, checked above.
    return ChallengeState(
        item_id,
        cast(Answer, state),
        Node.of(link_kind, link_id) if link_kind and link_id else None,
        stamp,
        None,
        tuple(notices),
    )


def approve(tx: Tx, item_id: str) -> ChallengeState:
    """A person approves a B answer; it becomes a plan with the element and join it carries, STORE-040."""
    existing = tx.execute("SELECT state, answered FROM challenge_states WHERE item_id=?", (item_id,)).fetchone()
    if existing is None or existing[0] != "B":
        state = "open" if existing is None else existing[0]
        raise StoreError(
            f"Challenge {item_id} is {state}; only a challenge answered B is approved.",
            f"metaform map answer {item_id} B",
        )
    item, found = tx.rows.own_row("item", item_id)
    stamp = now()
    tx.execute("UPDATE challenge_states SET state='plan', approved=? WHERE item_id=?", (stamp, item_id))
    if item["target_kind"] == "element":
        element_id = str(item["target_id"])
        added = tx.execute(
            "SELECT 1 FROM elements WHERE element_id=? AND layer_id=? AND op='add'", (element_id, found.layer_id)
        ).fetchone()
        if added is not None:
            tx.execute(
                "INSERT OR IGNORE INTO plans(element_id, join_id, layer_id, source, item_id) VALUES (?, ?, ?, ?, ?)",
                (element_id, _join_in_layer(tx, element_id, found.layer_id), found.layer_id, "approved", item_id),
            )
    return ChallengeState(item_id, "plan", None, str(existing[1]), stamp)


def _join_in_layer(tx: Tx, element_id: str, layer_id: str) -> str | None:
    """The first join of the layer that holds the element, or else the first it receives."""
    for sql in (("SELECT c.join_id FROM join_elements e JOIN current_joins c ON c.row = e.join_row JOIN joins j "
                "ON j.row = c.row WHERE e.element_id=? AND j.layer_id=? ORDER BY c.row LIMIT 1"),
                ("SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row "
                "WHERE c.receiver=? AND j.layer_id=? ORDER BY c.row LIMIT 1")):
        row = tx.execute(sql, (element_id, layer_id)).fetchone()
        if row is not None:
            return str(row[0])
    return None


def add_plan(tx: Tx, layer: str, element: Any, join: str | None) -> Plan:
    """An agent adds a plan directly; it needs no approval, STORE-040."""
    found = tx.rows.layer(layer)
    notices: list[Notice] = []
    element_id = tx.rows.element_at(element, found, "element", notices)
    join_id: str | None = None
    if join:
        kind, join_id = tx.rows.node_at(Node("join", join), found, "join", notices)
        if (
            not tx.rows.target_current(kind, join_id)
            and not tx.execute("SELECT 1 FROM join_ids WHERE join_id=?", (join_id,)).fetchone()
        ):
            join_id = None
    tx.execute(
        "INSERT INTO plans(element_id, join_id, layer_id, source, item_id) VALUES (?, ?, ?, ?, NULL) "
        "ON CONFLICT(element_id) DO UPDATE SET join_id=excluded.join_id, layer_id=excluded.layer_id, "
        "source='direct', item_id=NULL",
        (element_id, join_id, found.layer_id, "direct"),
    )
    return Plan(element_id, join_id, found.layer_id, found.name, "direct", None, tuple(notices))


FEATURE_TABLES = (
    Table.from_sql(
        "challenge_states",
        """
CREATE TABLE IF NOT EXISTS challenge_states(
  item_id   TEXT PRIMARY KEY,
  state     TEXT NOT NULL CHECK(state IN ('A','B','C','plan')),
  link_kind TEXT CHECK(link_kind IN ('element','join')),
  link_id   TEXT,
  answered  TEXT NOT NULL,
  approved  TEXT
);
CREATE INDEX IF NOT EXISTS challenge_states_by_state ON challenge_states(state);
""",
        exchange=True,
        on_remove=(("item", "item_id", "delete"),),
    ),
    Table.from_sql(
        "plans",
        """
CREATE TABLE IF NOT EXISTS plans(
  element_id TEXT PRIMARY KEY REFERENCES element_ids(element_id),
  join_id    TEXT REFERENCES join_ids(join_id),
  layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
  source     TEXT NOT NULL CHECK(source IN ('direct','approved')),
  item_id    TEXT
);
CREATE INDEX IF NOT EXISTS plans_by_layer ON plans(layer_id);
""",
        exchange=True,
        on_remove=(("layer", "layer_id", "delete"),),
    ),
    Table.from_sql(
        "work",
        """
CREATE TABLE IF NOT EXISTS work(
  row         INTEGER PRIMARY KEY,
  work_id     TEXT NOT NULL UNIQUE,
  target_kind TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  condition   TEXT NOT NULL,
  note        TEXT,
  task        TEXT,
  held        INTEGER NOT NULL DEFAULT 0,
  reviewed    INTEGER NOT NULL DEFAULT 0,
  created     TEXT NOT NULL,
  done        TEXT,
  resolution  TEXT,
  steps       INTEGER,
  steps_done  INTEGER NOT NULL DEFAULT 0,
  taken       TEXT,
  taken_by    TEXT,
  position    INTEGER
);
CREATE INDEX IF NOT EXISTS work_by_target ON work(target_kind, target_id, row);
CREATE INDEX IF NOT EXISTS work_by_condition ON work(condition, row);
CREATE INDEX IF NOT EXISTS work_by_done ON work(done, row);
""",
        exchange=True,
    ),
    Table.from_sql(
        "work_links",
        """
CREATE TABLE IF NOT EXISTS work_links(
  work_id     TEXT NOT NULL REFERENCES work(work_id),
  number      INTEGER NOT NULL,
  target_kind TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  PRIMARY KEY(work_id, number)
);
""",
        exchange=True,
    ),
    Table.from_sql(
        "work_steps",
        """
CREATE TABLE IF NOT EXISTS work_steps(
  row     INTEGER PRIMARY KEY,
  work_id TEXT NOT NULL REFERENCES work(work_id),
  number  INTEGER NOT NULL,
  said    TEXT,
  at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS work_steps_by_work ON work_steps(work_id, number);
""",
        exchange=True,
    ),
    Table.from_sql(
        "messages",
        """
CREATE TABLE IF NOT EXISTS messages(
  row         INTEGER PRIMARY KEY,
  message_id  TEXT NOT NULL UNIQUE,
  target_kind TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  kind        TEXT NOT NULL,
  text        TEXT,
  suggestions TEXT,
  by          TEXT,
  created     TEXT NOT NULL,
  closed      TEXT,
  answer      TEXT
);
CREATE INDEX IF NOT EXISTS messages_by_target ON messages(target_kind, target_id, row);
CREATE INDEX IF NOT EXISTS messages_by_closed ON messages(closed, row);
""",
        exchange=True,
    ),
    Table.from_sql(
        "reports",
        """
CREATE TABLE IF NOT EXISTS reports(
  report_id TEXT PRIMARY KEY,
  run_id    TEXT NOT NULL,
  layer_id  TEXT REFERENCES layers(layer_id),
  kind      TEXT NOT NULL CHECK(kind IN ('report','feedback','shape')),
  created   TEXT NOT NULL,
  size      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS reports_by_layer ON reports(layer_id, kind);
CREATE INDEX IF NOT EXISTS reports_by_time ON reports(created, report_id);
""",
        exchange=False,
        on_remove=(("layer", "layer_id", "null"),),
    ),
)


def ask(tx: Tx, node: Node, text: Any, *, suggestions: Any = None, by: Any = None,
        work: str | None = None) -> Message:
    if work is not None:
        _work_row(tx, work)
    asked = add_message(tx, node, "question", text, suggestions=suggestions, by=by)
    if work is not None:
        tx.tables().insert('question_work', {'message_id': asked.message_id, 'work_id': work})
        asked = dataclasses.replace(asked, work_id=work)
    return asked


def tell(tx: Tx, node: Node, text: Any, *, by: Any = None) -> Message:
    return add_message(tx, node, "message", text, by=by)


def decorate(tx: Tx, record: Any) -> Any:
    """What map's features contribute to a native DAO record."""
    if isinstance(record, Element):
        plan = tx.execute("SELECT 1 FROM plans WHERE element_id=?", (record.element_id,)).fetchone()
        return dataclasses.replace(
            record, state="plan" if plan else None, open_work=open_work(tx, "element", record.element_id)
        )
    if isinstance(record, Join):
        plan = any(
            row is not None and row[0] == record.join_id
            for row in (
                tx.execute("SELECT join_id FROM plans WHERE element_id=?", (end,)).fetchone()
                for end in (*(held.element_id for held in record.elements), record.receiver)
            )
        )
        return dataclasses.replace(
            record, state="plan" if plan else None, open_work=open_work(tx, "join", record.join_id)
        )
    if isinstance(record, Item):
        state = tx.execute("SELECT state FROM challenge_states WHERE item_id=?", (record.item_id,)).fetchone()
        return dataclasses.replace(record, state=str(state[0]) if state else None)
    if isinstance(record, Provenance):
        refs = tuple(
            Ref(str(row[0]), str(row[1]))
            for row in tx.execute(
                "SELECT kind, report_id FROM reports WHERE layer_id=? ORDER BY kind, report_id", (record.layer_id,)
            )
        )
        return dataclasses.replace(record, refs=refs)
    if isinstance(record, Where):
        if record.kind == "join":
            assert record.join is not None
            target = Node("join", record.join.join_id)
        else:
            assert record.element is not None
            target = Node("element", record.element.element_id)
        pending = work(tx, target, open=True, limit=0).results
        waiting = messages(tx, target, open=True, limit=0).results
        return dataclasses.replace(record, work=pending, messages=waiting, past_work=_past_work(tx, target))
    return record


def item_write(tx: Tx, target: Node, answers: list[Any], fields: dict[str, Any], notices: list[Notice]) -> None:
    if fields.get("task"):
        for answer in answers:
            ticket = add_work(tx, target, fields.get("condition"), task=answer)
            notices += ticket.notices
            notices.append(
                Notice(
                    "task",
                    f"task is not stored on the item; it added the ticket {ticket.work_id} at "
                    f"{target.kind}:{target.id}.",
                )
            )


def legacy_upgrade(db: DataConnection, found: str) -> None:
    """The map feature's historical layouts, adopted without changing ticket identities."""
    if int(found) < 10:
        for shown, kind in (("in-progress", "missing"), ("fixing", "broken")):
            db.execute("UPDATE work SET condition=?, taken=COALESCE(taken, created) WHERE condition=?", (kind, shown))
    moved = db.execute("SELECT 1 FROM temp.sqlite_master WHERE name='subtype_moves'").fetchone()
    if int(found) < 19 and moved is not None:
        # Layout 19, Rich 2026-10-04: a subtype join is gone and its element is held by the join; what was at the
        # subtype join is at that element.
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, kind, ident in (("work", "target_kind", "target_id"), ("work_links", "target_kind", "target_id"),
                                   ("messages", "target_kind", "target_id"),
                                   ("challenge_states", "link_kind", "link_id")):
            if table in present:
                db.execute(f"UPDATE {table} SET {kind}='element', {ident}=(SELECT element_id FROM temp.subtype_moves m "
                           f"WHERE m.join_id={table}.{ident}) WHERE {kind}='join' AND {ident} IN "
                           "(SELECT join_id FROM temp.subtype_moves)")


def legacy_fold(db: DataConnection, correction: str, intake: str) -> None:
    for table in ("reports", "plans"):
        db.execute(f"UPDATE {table} SET layer_id=? WHERE layer_id=?", (intake, correction))


TABLES = Tables(
    version=6,
    legacy_upgrade=legacy_upgrade,
    legacy_fold=legacy_fold,
    tables=(*FEATURE_TABLES, Table(
        'glyphs', place='metaform', key=('work_id',),
        columns=(Column('work_id', required=True), Column('glyph', required=True)),
    ), Table(
        # each ticket's preferred agent and the person's hold, which hides it from agents and automatic starts
        'ticket_settings', place='metaform', key=('work_id',),
        columns=(Column('work_id', required=True), Column('agent'), Column('hold', 'int', default=0)),
    ), Table(
        'eligible', place='metaform', key=('work_id',),
        columns=(Column('work_id', required=True), Column('agents', 'json', required=True)),
    ), Table(
        'question_work', place='metaform', key=('message_id',),
        columns=(Column('message_id', required=True), Column('work_id', required=True)),
        indexes=(Index(('work_id',)),),
    )),
)


DATA = Data(
    operations={
        **{
            fn.__name__: Operation(fn, write=True)
            for fn in (
                add_work,
                edit_work,
                move_message,
                move_work,
                take_work,
                plan_work,
                step_work,
                finish_work,
                answer,
                approve,
                add_plan,
                save_report,
                ask,
                tell,
            )
        },
        "reply": Operation(close_message, write=True),
        "reopen": Operation(reopen_message, write=True),
        **{fn.__name__: Operation(fn, retained=True) for fn in (work, messages, ticket, reports, report)},
    },
    decorate=decorate,
    item_write=item_write,
)
