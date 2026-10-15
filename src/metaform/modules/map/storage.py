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
    KINDS,
    LIMIT,
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
    reference,
    shown_open,
    sliced,
    status,
)
from metaform.data import (
    DataTx as Tx,
)

Row = DataRow
ANSWERS = ("A", "B", "C")
# The kinds of item map numbers at an address, MCP-037: a work record, and a question or message, by their own ids.
NUMBERED = ("work", "message")
WORK_FIELDS = ("condition", "kind", "note", "task", "held", "reviewed")
REPORT_KINDS = ("report", "feedback", "shape")


def joins_at(tx: Tx, element_id: str) -> list[str]:
    """The current joins an element receives or holds, STORE-046."""
    return sorted(set(tx.base.joins_received(element_id)) | set(tx.base.joins_holding(element_id)))


def _work_text(value: Any, field: str, notices: list[Notice]) -> str | None:
    """A note, task or resolution: text, or anything else kept as JSON text with a notice, BASE-044."""
    if value is None or isinstance(value, str):
        return value
    notices.append(Notice(field, f"{field} is not text; it was stored as JSON text."))
    return json.dumps(value, ensure_ascii=False)


def _shown(condition: str, task: str | None) -> None:
    """Refuse an open record shown nowhere, MAP-046's amendment of 2026-10-15: one with neither a task nor a trouble,
    broken or missing marker, and not a stage drawn on its node. Every writer of a work record comes through here."""
    if not shown_open(condition, task):
        raise StoreError(
            "A record with neither a task nor a trouble, broken or missing marker is not work, and nothing would "
            "show it." + (f" {condition} is a part's normal state." if condition in ("ok", "built") else ""),
            "give a task; a note alone goes beside the map, and the page sets a part's stage",
        )


def _condition(value: Any, notices: list[Notice]) -> str:
    """The condition as given; a missing one is stored as empty text, since the column is never null, BASE-044."""
    if value in CONDITIONS:
        return str(value)
    if value is None or value in ("", "none"):
        return ""  # a plain task: the part's state is not in question, MAP-046
    # The conditions are a closed list, so a word outside it is refused, checking an entry is not
    # judging the agent's reasoning, and a mark stored under a word no reader knows is lost.
    raise StoreError(
        f"{value!r} is not a condition. A part's condition is one of {', '.join(CONDITIONS)}, or none.",
        "send the condition again with one of those words",
    )


def _kind(value: Any) -> str:
    """A ticket's kind, from a closed list as the condition is; none is a plain task, stored as empty text."""
    if value is None or value in ("", "none"):
        return ""
    if value in KINDS:
        return str(value)
    raise StoreError(
        f"{value!r} is not a kind of ticket. A ticket is {', '.join(KINDS)}, or none for a plain task.",
        "send the kind again with one of those words",
    )


def _building(tx: Tx, work_id: str) -> None:
    """A ticket taken at a part whose open state record says unbuilt starts its building: that record becomes
    under-construction. Nothing else of the part's state is set by a ticket, so finishing one never
    marks the part built."""
    row = _work_row(tx, work_id)
    if row["task"]:
        _ticket_changed(tx, *(str(found["work_id"]) for found in tx.execute(
            "SELECT work_id FROM work WHERE target_kind=? AND target_id=? AND done IS NULL AND condition='unbuilt' "
            "AND (task IS NULL OR task='')", (row["target_kind"], row["target_id"]))))
        tx.execute(
            "UPDATE work SET condition='under-construction' WHERE target_kind=? AND target_id=? AND done IS NULL "
            "AND condition='unbuilt' AND (task IS NULL OR task='')",
            (row["target_kind"], row["target_id"]),
        )


def _work_row(tx: Tx, work_id: str) -> Any:
    row = tx.execute("SELECT * FROM work WHERE work_id=?", (work_id,)).fetchone()
    if row is None:
        raise StoreError(f"No work record has the id {work_id}.", "metaform map work")
    return row


def _ticket_changed(tx: Tx, *work_ids: str) -> None:
    """The tickets this write changes, said on its `map.changed`, so a dispatch runner reads only its own, BASE-053."""
    for work_id in work_ids:
        tx.concern(work_id=work_id, kind="ticket")


def _message_changed(tx: Tx, message_id: str) -> None:
    """A question or message this write changes, said on its `map.changed` with the ticket a question is linked to,
    the one whose agent waits on its answer, BASE-053."""
    linked = tx.tables().get("question_work", {"message_id": message_id})
    tx.concern(work_id=str(linked["work_id"]) if linked else None, kind="message")


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
    kind: Any = None,
    title: Any = None,
) -> WorkRecord:
    """Write the condition of an element or join as its own record, apart from the map, STORE-042; a ticket carries
    its kind beside it. It takes the next number at its node's address with its title, MCP-037: the title given, else
    the first line of its task or note."""
    notices: list[Notice] = []
    stage, ticket_kind = _condition(condition, notices), _kind(kind)  # both checked before anything is written
    stated = _work_text(task, "task", notices)
    _shown(stage, stated)
    target_kind, thing = work_target(tx, node, notices)
    _backfill(tx)
    work_id = new_id()
    tx.execute(
        "INSERT INTO work(work_id, target_kind, target_id, condition, note, task, held, reviewed, created, kind) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            work_id,
            target_kind,
            thing,
            stage,
            _work_text(note, "note", notices),
            stated,
            int(bool(held)),
            int(bool(reviewed)),
            now(),
            ticket_kind,
        ),
    )
    _link(tx, work_id, links, notices)
    _number(tx, "work", work_id, target_kind, thing, _titled(title, task, note))
    _ticket_changed(tx, work_id)
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
    before = _work_row(tx, work_id)
    _ticket_changed(tx, work_id)
    given = as_object(changes)
    if given is None:
        raise StoreError("The changes to a work record are an object of its fields.", "metaform help map work")
    for key in sorted(given):
        if key == "node":
            kind, thing = work_target(tx, given[key], notices)
            moved = (kind, thing) != (str(before["target_kind"]), str(before["target_id"]))
            tx.execute("UPDATE work SET target_kind=?, target_id=? WHERE work_id=?", (kind, thing, work_id))
            if moved:  # at a new address it takes the next number there, MCP-037; its old number is not reused
                _number(tx, "work", work_id, kind, thing)
            continue
        if key == "links":
            _link(tx, work_id, given[key], notices)
            continue
        if key == "title":
            _retitle(tx, "work", work_id, given[key])
            continue
        if key not in WORK_FIELDS:
            notices.append(Notice(key, f"A work record has no field {key}; it was not stored."))
            continue
        value: Any = given[key]
        if key == "condition":
            value = _condition(value, notices)
        elif key == "kind":
            value = _kind(value)
        elif key in ("held", "reviewed"):
            value = int(bool(value))
        else:
            value = _work_text(value, key, notices)
        tx.execute(f"UPDATE work SET {key}=? WHERE work_id=?", (value, work_id))
    after = _work_row(tx, work_id)
    if after["done"] is None:  # an edit never leaves an open record shown nowhere; the transaction rolls back
        _shown(str(after["condition"]), after["task"])
    return work_record(tx, after, tuple(notices))


def _message_row(tx: Tx, message_id: str) -> Any:
    row = tx.execute("SELECT * FROM messages WHERE message_id=?", (message_id,)).fetchone()
    if row is None:
        raise StoreError(f"No question or message has the id {message_id}.", "metaform map messages")
    return row


def add_message(tx: Tx, node: Any, kind: str, text: Any, *, suggestions: Any = None, by: Any = None,
                title: Any = None, why: Any = None) -> Message:
    """What an agent says to the user at a node, MAP-050: a question, with the answers it suggests, or a message.
    Nothing is refused: a question with no suggestions is stored, and the agent is told to suggest. It takes the next
    number at its node's address with its title, the first line of its text when none is given, and its why, MCP-037."""
    notices: list[Notice] = []
    target_kind, thing = work_target(tx, node, notices)
    _backfill(tx)
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
    _number(tx, "message", message_id, target_kind, thing, _titled(title, text), why)
    tx.concern(kind="message")  # a question asked for a ticket names it, in `ask`
    return message(tx, _message_row(tx, message_id), tuple(notices))


def close_message(tx: Tx, message_id: str, answer: Any = None, *, agent: bool = False) -> Message:
    """The user answered a question or read a message. One already closed keeps its first answer. With `agent`, the
    call came over an agent's surface, MCP, and an open question linked to a ticket is refused: it is a dispatched
    agent's permission request, which only the person answers, on the page or the command line, BASE-052; checked in
    the same transaction as the write, so no answer slips in between."""
    notices: list[Notice] = []
    row = _message_row(tx, message_id)
    if row["closed"] is not None:
        notices.append(Notice("id", f"This was closed at {row['closed']}; its answer was kept."))
        return message(tx, row, tuple(notices))
    if agent and row["kind"] == "question" and tx.tables().get('question_work', {'message_id': message_id}):
        raise StoreError(
            f"Question {message_id} is linked to a ticket: an agent's permission request waits on it, and only the "
            "person answers it.",
            f'the person answers it on the page, or with metaform map reply {message_id} answer="..." on the command '
            "line",
        )
    _message_changed(tx, message_id)
    tx.execute(
        "UPDATE messages SET closed=?, answer=? WHERE message_id=?",
        (now(), _work_text(answer, "answer", notices), message_id),
    )
    return message(tx, _message_row(tx, message_id), tuple(notices))


def move_message(tx: Tx, message_id: str, node: Node) -> Message:
    """Move a question or message to another node, keeping its identity, suggestions, answer and closed state."""
    row = _message_row(tx, message_id)
    notices: list[Notice] = []
    kind, thing = work_target(tx, node, notices)
    _message_changed(tx, message_id)
    tx.execute("UPDATE messages SET target_kind=?, target_id=? WHERE message_id=?", (kind, thing, message_id))
    if (kind, thing) != (str(row["target_kind"]), str(row["target_id"])):
        _number(tx, "message", message_id, kind, thing)  # the next number at its new address, MCP-037
    return message(tx, _message_row(tx, message_id), tuple(notices))


def reopen_message(tx: Tx, message_id: str) -> Message:
    """A question answered by mistake waits again, with its suggestions and no answer, MAP-050. Only a question is
    reopened; one already open is left as it is."""
    row = _message_row(tx, message_id)
    if row["kind"] != "question":
        raise StoreError("Only a question is reopened; this is a message.", "metaform map messages kind=question")
    if row["closed"] is None:
        return message(tx, row, (Notice("id", "This question is open; it was left as it is."),))
    _message_changed(tx, message_id)
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
    _ticket_changed(tx, work_id)
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
    _ticket_changed(tx, work_id)
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
    notices: list[Notice] = []
    _ticket_changed(tx, work_id)
    tx.execute(
        "UPDATE work SET taken=?, taken_by=?, held=0, steps=COALESCE(?, steps) WHERE work_id=?",
        (now(), _work_text(by, "by", notices), _count(steps, notices), work_id),
    )
    _building(tx, work_id)
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def move_work(tx: Tx, work_id: str, column: Any, position: Any = None, by: Any = None) -> WorkRecord:
    """Put a ticket in a column of the board, and at a place in it, MAP-048: backlog holds it, to do frees it, doing
    takes it and done finishes it; a ticket moved back out of doing or done is open and untaken again."""
    row = _work_row(tx, work_id)
    if column not in COLUMNS:
        raise StoreError(f"{column!r} is not a column: backlog, todo, doing or done.", "metaform help map work")
    notices: list[Notice] = []
    _ticket_changed(tx, work_id)
    if work_record(tx, row).column == column:
        pass  # Within a column only the order changes.
    elif column == "done":
        tx.execute("UPDATE work SET done=COALESCE(done, ?), held=0 WHERE work_id=?", (now(), work_id))
    elif column == "doing":
        tx.execute(
            "UPDATE work SET done=NULL, outcome=NULL, held=0, taken=COALESCE(taken, ?), taken_by=COALESCE(?, taken_by) "
            "WHERE work_id=?",
            (now(), _work_text(by, "by", notices), work_id),
        )
        _building(tx, work_id)  # moved to doing on the board is taken, as take_work takes it
    else:
        tx.execute(
            "UPDATE work SET done=NULL, outcome=NULL, taken=NULL, taken_by=NULL, held=? WHERE work_id=?",
            (int(column == "backlog"), work_id),
        )
    del row
    moved = work_record(tx, _work_row(tx, work_id))
    # the tickets of the same column, by id only: the column is a condition on three columns, WorkRecord.column,
    # so the whole table need not be rebuilt as records to find them. Found by review, 2026-10-06.
    same = {
        "done": "done IS NOT NULL",
        "doing": "done IS NULL AND taken IS NOT NULL",
        "backlog": "done IS NULL AND taken IS NULL AND held=1",
        "todo": "done IS NULL AND taken IS NULL AND held=0",
    }[moved.column]
    others = [
        str(other["work_id"])
        for other in tx.execute(
            f"SELECT work_id FROM work WHERE work_id<>? AND {same} ORDER BY position IS NULL, position, row",
            (work_id,),
        )
    ]
    at = len(others) if position is None else max(0, min(len(others), int(position)))
    _ticket_changed(tx, *others)  # their places in the column
    for place, ident in enumerate([*others[:at], work_id, *others[at:]]):
        tx.execute("UPDATE work SET position=? WHERE work_id=?", (place, ident))
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def finish_work(tx: Tx, work_id: str, resolution: Any = None, why: Any = None, outcome: str = "completed") -> WorkRecord:
    """Mark a work record done, keeping its resolution beside it, the why of that resolution with its number, MCP-037,
    and how it ended, `outcome`: a terminal state of the one status vocabulary, completed unless the person cancelled
    it or it failed, so a cancelled ticket never reads as completed, P232; a record already done keeps its first
    resolution and outcome."""
    ended = status.known(outcome, "map work op=done id=<id>")
    if ended not in status.TERMINAL:
        raise StoreError(f"A work record ends {', '.join(status.TERMINAL)}, not {ended}.", "map work op=done id=<id>")
    notices: list[Notice] = []
    row = _work_row(tx, work_id)
    if row["done"] is not None:
        notices.append(Notice("id", f"This work record was done at {row['done']}; its resolution was kept."))
        return work_record(tx, row, tuple(notices))
    _ticket_changed(tx, work_id)
    tx.execute(
        "UPDATE work SET done=?, resolution=?, outcome=? WHERE work_id=?",
        (now(), _work_text(resolution, "resolution", notices), ended, work_id),
    )
    if isinstance(why, str) and why.strip():
        tables = tx.tables()
        if tables.get("numbered", {"kind": "work", "item_id": work_id}) is not None:
            tables.update("numbered", {"kind": "work", "item_id": work_id}, {"why": why.strip()})
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
    at = tx.reads.node_where(res, raw, Node.of(record.node_kind, record.node_id))
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
    kind: str | None = None,
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
            held = joins_at(tx, target[1])
            marks = ', '.join('?' for _ in held) or "''"
            where.append(f"(target_kind=? AND target_id=? OR target_kind='join' AND target_id IN ({marks}))")
            params.extend((*target, *held))
        elif target is not None:
            where.append("target_kind=? AND target_id=?")
            params.extend(target)
        if condition is not None:
            where.append("condition=?")
            params.append(condition)
        if kind is not None:
            where.append("kind=?")
            params.append("" if kind == "none" else kind)
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
        str(row["kind"] or ""),
        (row["outcome"] or "completed") if row["done"] is not None else None,
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
        str(row[0])
        for row in tx.execute(
            "SELECT condition FROM work WHERE target_kind=? AND target_id=? AND done IS NULL ORDER BY row",
            (kind, thing_id),
        )
        if row[0]
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
        added = any(version.op == 'add' and version.layer_id == found.id
                    for version in tx.base.versions.get(element_id, ()))
        if added:
            tx.execute(
                "INSERT OR IGNORE INTO plans(element_id, join_id, layer_id, source, item_id) VALUES (?, ?, ?, ?, ?)",
                (element_id, _join_in_layer(tx, element_id, found.layer_id), found.layer_id, "approved", item_id),
            )
    return ChallengeState(item_id, "plan", None, str(existing[1]), stamp)


def _join_in_layer(tx: Tx, element_id: str, layer_id: str) -> str | None:
    """The first join of the layer that holds the element, or else the first it receives."""
    for held in (tx.base.joins_holding(element_id), tx.base.joins_received(element_id)):
        found = [(version.seq, join_id) for join_id in held
                 if (version := tx.base.current(join_id)) is not None and version.layer_id == layer_id]
        if found:
            return min(found)[1]
    return None


def add_plan(tx: Tx, layer: str, element: Any, join: str | None) -> Plan:
    """An agent adds a plan directly; it needs no approval, STORE-040."""
    found = tx.rows.layer(layer)
    notices: list[Notice] = []
    element_id = tx.rows.element_at(element, found, "element", notices)
    join_id: str | None = None
    if join:
        kind, join_id = tx.rows.node_at(Node("join", join), found, "join", notices)
        if not tx.rows.target_current(kind, join_id) and tx.base.kinds.get(str(join_id)) != 'join':
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
  element_id TEXT PRIMARY KEY,
  join_id    TEXT,
  layer_id   TEXT NOT NULL,
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
  position    INTEGER,
  kind        TEXT NOT NULL DEFAULT '',
  outcome     TEXT
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
  layer_id  TEXT,
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
        work: str | None = None, title: Any = None, why: Any = None) -> Message:
    if work is not None:
        _work_row(tx, work)
    asked = add_message(tx, node, "question", text, suggestions=suggestions, by=by, title=title, why=why)
    if work is not None:
        tx.tables().insert('question_work', {'message_id': asked.id, 'work_id': work})
        tx.concern(work_id=work, kind="message")
        asked = dataclasses.replace(asked, work_id=work)
    return asked


def tell(tx: Tx, node: Node, text: Any, *, by: Any = None, title: Any = None) -> Message:
    return add_message(tx, node, "message", text, by=by, title=title)


# ------------------------------------------------------------------------------------------------ item numbers

def _first(text: Any) -> str | None:
    """The first line of a text that holds something, stripped: the title an item takes when none is given."""
    if not isinstance(text, str):
        return None
    return next((line.strip() for line in text.splitlines() if line.strip()), None)


def _titled(title: Any, *texts: Any) -> str | None:
    """An item's title: the one given, else the first line of the first of its texts that has one."""
    if isinstance(title, str) and title.strip():
        return title.strip()
    return next((found for found in (_first(text) for text in texts) if found), None)


def _number(tx: Tx, kind: str, item_id: str, target_kind: str, thing: str, title: str | None = None,
            why: Any = None) -> int | None:
    """Give an item the next number at the address of the node it is at, MCP-037: an element's address, a join's
    receiver's. A node with no current address takes none. An item numbered before keeps its title and why, and moves
    to the new number at its new address."""
    address = tx.rows.node_address(target_kind, thing)
    if address is None:
        return None
    number = tx.number(address)
    tables = tx.tables()
    key = {"kind": kind, "item_id": item_id}
    if tables.update("numbered", key, {"address": address, "number": number}) is None:
        tables.insert("numbered", {**key, "address": address, "number": number, "title": title,
                                   "why": why.strip() if isinstance(why, str) and why.strip() else None})
    return number


def _retitle(tx: Tx, kind: str, item_id: str, title: Any) -> None:
    if isinstance(title, str) and title.strip():
        tables = tx.tables()
        if tables.get("numbered", {"kind": kind, "item_id": item_id}) is not None:
            tables.update("numbered", {"kind": kind, "item_id": item_id}, {"title": title.strip()})


def _backfill(tx: Tx) -> None:
    """Number the work records and messages written before items were numbered, once, in the order they were made,
    each titled from the first line of its task, note or text, MCP-037. Map tables version 10 adds the numbers; the
    addresses come from the map, so this runs in the first map transaction that writes after the upgrade."""
    tables = tx.tables()
    if tables.get("numbering", {"name": "items"}) is not None:
        return
    found: list[tuple[str, int, str, str, str, str, str | None]] = []
    for row in tx.execute("SELECT row, work_id, target_kind, target_id, created, task, note FROM work"):
        if tables.get("numbered", {"kind": "work", "item_id": str(row["work_id"])}) is None:
            found.append((str(row["created"]), int(row["row"]), "work", str(row["work_id"]), str(row["target_kind"]),
                          str(row["target_id"]), _titled(None, row["task"], row["note"])))
    for row in tx.execute("SELECT row, message_id, target_kind, target_id, created, text FROM messages"):
        if tables.get("numbered", {"kind": "message", "item_id": str(row["message_id"])}) is None:
            found.append((str(row["created"]), int(row["row"]), "message", str(row["message_id"]),
                          str(row["target_kind"]), str(row["target_id"]), _titled(None, row["text"])))
    for _, _, kind, item_id, target_kind, thing, title in sorted(found, key=lambda one: one[:3]):
        _number(tx, kind, item_id, target_kind, thing, title)
    tables.insert("numbering", {"name": "items", "at": now()})


def items_numbered(tx: Tx) -> bool:
    """Whether the work records and messages written before numbering have been numbered, MCP-037."""
    return tx.tables().get("numbering", {"name": "items"}) is not None


def number_items(tx: Tx) -> None:
    """Number the work records and messages written before numbering, once, MCP-037."""
    _backfill(tx)


def numbers_of(tx: Tx, kind: str, item_ids: Sequence[str]) -> dict[str, tuple[str, str | None, str | None]]:
    """Each numbered item's reference `<address>#<n>`, title and why, by its id; an item with none is left out."""
    tables = tx.tables()
    found: dict[str, tuple[str, str | None, str | None]] = {}
    for item_id in item_ids:
        row = tables.get("numbered", {"kind": kind, "item_id": item_id})
        if row is not None:
            found[item_id] = (reference(row["address"], row["number"]), row["title"], row["why"])
    return found


def item_at(tx: Tx, address: str, number: int) -> dict[str, Any] | None:
    """The work record or message numbered `number` at `address`, as an item an agent reads, MCP-037: its kind,
    title, why, body and links. None when map holds none there."""
    rows = tx.tables().rows("numbered", {"address": address, "number": number}, limit=0).results
    if not rows:
        return None
    held = rows[0]
    if held["kind"] == "code":  # a link of the code layer, `code.py`: the symbol and the node whose purpose it serves
        try:
            found = tx.views.item_by_id(held["item_id"])
        except KeyError:
            return None
        if found.orphaned:
            return None
        value: dict[str, Any] = as_object(found.value) or {}
        parts = [f"{key}: {value[key]}" for key in ("symbol", "label", "file", "count", "state", "by") if value.get(key)]
        if value.get("files"):  # one decision naming several symbols, `code.py`: its files, then its first symbols
            parts.append("files: " + ", ".join(str(one) for one in value["files"]))
        parts += [f"{ref.key}: {ref.value}" for ref in found.refs if ref.key == "qn"]
        return {"kind": "code", "title": held["title"], "why": held["why"], "body": "\n".join(parts), "links": [],
                "id": found.id}
    if held["kind"] == "work":
        row = tx.execute("SELECT * FROM work WHERE work_id=?", (held["item_id"],)).fetchone()
        if row is None:
            return None
        record = work_record(tx, row)
        parts = [f"task: {record.task}" if record.task else None, f"note: {record.note}" if record.note else None,
                 f"condition: {record.condition}" if record.condition else None,
                 f"done {record.done}: {record.resolution or ''}".rstrip() if record.done else "open",
                 f"id: {record.id}"]
        links = [link.address or f"{link.kind}:{link.id}" for link in record.links]
        return {"kind": "work", "title": held["title"], "why": held["why"],
                "body": "\n".join(part for part in parts if part), "links": links, "id": record.id}
    row = tx.execute("SELECT * FROM messages WHERE message_id=?", (held["item_id"],)).fetchone()
    if row is None:
        return None
    said = message(tx, row)
    parts = [said.text or "", *(f"- {one}" for one in said.suggestions),
             (f"answered {said.closed}: {said.answer or ''}".rstrip() if said.closed else "waiting"), f"id: {said.id}"]
    return {"kind": said.kind, "title": held["title"], "why": held["why"],
            "body": "\n".join(part for part in parts if part), "links": [], "id": said.id}


def listed_items(tx: Tx, address: str, before: int | None = None, limit: int = 40) -> list[dict[str, Any]]:
    """The work records, messages and code links numbered at `address` below `before`, newest first, at most `limit`,
    as items are listed, MCP-037: each one's number, kind, title and why, from one read of the address's numbers. One
    whose record is gone is left out, as `item_at` leaves it out."""
    rows = sorted((row for row in tx.tables().rows("numbered", {"address": address}, limit=0).results
                   if before is None or row["number"] < before), key=lambda row: -row["number"])
    found: list[dict[str, Any]] = []
    for held in rows:
        if len(found) >= limit:
            break
        kind: str | None = None
        if held["kind"] == "code":
            try:
                kind = None if tx.views.item_by_id(held["item_id"]).orphaned else "code"
            except KeyError:
                kind = None
        elif held["kind"] == "work":
            row = tx.execute("SELECT 1 FROM work WHERE work_id=?", (held["item_id"],)).fetchone()
            kind = "work" if row is not None else None
        else:
            row = tx.execute("SELECT kind FROM messages WHERE message_id=?", (held["item_id"],)).fetchone()
            kind = str(row[0]) if row is not None else None
        if kind is not None:
            found.append({"number": int(held["number"]), "kind": kind, "title": held["title"], "why": held["why"]})
    return found


def decorate(tx: Tx, record: Any) -> Any:
    """What map's features contribute to a native DAO record."""
    if isinstance(record, Element):
        plan = tx.execute("SELECT 1 FROM plans WHERE element_id=?", (record.id,)).fetchone()
        return dataclasses.replace(
            record, state="plan" if plan else None, open_work=open_work(tx, "element", record.id)
        )
    if isinstance(record, Join):
        plan = any(
            row is not None and row[0] == record.id
            for row in (
                tx.execute("SELECT join_id FROM plans WHERE element_id=?", (end,)).fetchone()
                for end in (*(held.element_id for held in record.elements), record.receiver)
            )
        )
        return dataclasses.replace(
            record, state="plan" if plan else None, open_work=open_work(tx, "join", record.id)
        )
    if isinstance(record, Item):
        state = tx.execute("SELECT state FROM challenge_states WHERE item_id=?", (record.id,)).fetchone()
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
            target = Node("join", record.join.id)
        else:
            assert record.element is not None
            target = Node("element", record.element.id)
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
                    f"task is not stored on the item; it added the ticket {ticket.id} at "
                    f"{target.kind}:{target.id}.",
                )
            )


def legacy_upgrade(db: DataConnection, found: str) -> None:
    """The map feature's historical layouts, adopted without changing ticket identities."""
    if int(found) < 10:
        for shown, kind in (("in-progress", "under-construction"), ("fixing", "broken")):
            db.execute("UPDATE work SET condition=?, taken=COALESCE(taken, created) WHERE condition=?", (kind, shown))
    # A store from any chassis layout before the stages, holds the old names; the module's own
    # version 8 upgrade does not run again once the version is recorded, so the names move here as well.
    db.execute("UPDATE work SET condition='unbuilt' WHERE condition='missing'")
    db.execute("UPDATE work SET condition='under-construction' WHERE condition='in-progress'")
    db.execute("UPDATE work SET condition='broken' WHERE condition='fixing'")
    db.execute("UPDATE work SET condition='' WHERE condition IN ('flawed', 'enhancement', 'exclude')")
    moved = db.execute("SELECT 1 FROM temp.sqlite_master WHERE name='subtype_moves'").fetchone()
    if int(found) < 19 and moved is not None:
        # Layout 19, a subtype join is gone and its element is held by the join; what was at the
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


def upgrade(tx: Any, found: int) -> None:
    """The map's own tables brought from an earlier version of this module."""
    if found < 8:
        # Version 8, a part's state is a stage, unbuilt, under-construction or built, or the fault
        # broken; missing read as a verdict and was put on working parts. flawed, enhancement and exclude were kinds
        # of ticket, never a part's state, so those records become plain tasks with their notes kept.
        renamed = {'missing': 'unbuilt', 'in-progress': 'under-construction', 'fixing': 'broken',
                   'flawed': '', 'enhancement': '', 'exclude': ''}
        for row in tx.rows('work', limit=0).results:
            if row['condition'] in renamed:
                tx.update('work', {'row': row['row']}, {'condition': renamed[row['condition']]})
    if 11 <= found < 14:
        # Version 13 names a SCIP symbol by its descriptors, as the other providers name theirs, and version 14 keys a
        # symbol by its file and qualified name and records the names a file's calls did not find: every file is read
        # again at the next map code-import, and the links the layer holds as items are taken into code_links then.
        for row in tx.rows('code_files', limit=0).results:
            tx.delete('code_files', {'layer_id': row['layer_id'], 'path': row['path']})


# The code layer's index, `code.py`: each file a provider was read for with its stamp, the hash of its bytes, the git
# commit it was read at and the names its calls did not find, the symbols it declares, each by its file and qualified
# name, the calls, imports, uses, bases and tests that start in it with the file each reaches, and the links that tie
# a symbol to the node whose purpose it provides for, at a join with the provider it is the code of when one is named.
# Kept under the code layer, so taking the layer off takes its index with it. A link an agent decided is also held by
# an item of the layer at its node, numbered, MCP-037, one item for each decision however many symbols it names;
# taking that item off takes its links.
CODE_TABLES = (Table(
    'code_files', place='metaform', key=('layer_id', 'path'),
    columns=(Column('layer_id', required=True), Column('path', required=True), Column('stamp'), Column('hash'),
             Column('provider'), Column('symbols', 'int', default=0), Column('read', required=True), Column('commit'),
             Column('unresolved', 'json')),
    on_remove=(('layer', 'layer_id', 'delete'),),
), Table(
    'code_symbols', place='metaform', key=('layer_id', 'path', 'qn'),
    columns=(Column('layer_id', required=True), Column('qn', required=True), Column('name', required=True),
             Column('label', required=True), Column('path', required=True), Column('start_line', 'int', default=0),
             Column('end_line', 'int', default=0), Column('symbol')),
    indexes=(Index(('layer_id', 'qn')),),
    on_remove=(('layer', 'layer_id', 'delete'),),
), Table(
    'code_edges', place='metaform', key=('layer_id', 'path', 'source', 'target_path', 'target', 'kind'),
    columns=(Column('layer_id', required=True), Column('source', required=True), Column('target', required=True),
             Column('kind', required=True), Column('path', required=True), Column('line', 'int', default=0),
             Column('target_path')),
    indexes=(Index(('layer_id', 'target', 'kind')), Index(('layer_id', 'path')), Index(('layer_id', 'target_path'))),
    on_remove=(('layer', 'layer_id', 'delete'),),
), Table(
    'code_links', place='metaform', key=('layer_id', 'node_kind', 'node_id', 'path', 'qn'),
    columns=(Column('layer_id', required=True), Column('node_kind', required=True), Column('node_id', required=True),
             Column('qn', required=True), Column('link_id', required=True), Column('name'), Column('label'),
             Column('path'), Column('state', required=True), Column('by'), Column('why'), Column('item_id'),
             Column('proposal', 'json'), Column('provider')),
    indexes=(Index(('link_id',)), Index(('layer_id', 'qn')), Index(('item_id',))),
    on_remove=(('layer', 'layer_id', 'delete'), ('item', 'item_id', 'delete')),
))


TABLES = Tables(
    # 10: the number, title and why of each work record and message at its address, MCP-037, in tables of their own,
    # so version 9 still reads and writes the store; 9: a ticket's kind beside the part's state; 8: a part's state is a
    # stage or broken; 7: no foreign keys; 11: the code layer's index, P167, in tables of their own, so version 9
    # still reads and writes the store; 12: how a done work record ended, completed, cancelled or failed, P232, in a
    # column version 9 never names, so it still reads and writes the store, and a record it closes reads as completed;
    # 13: the code layer's links in a table of their own, a symbol's provider form beside its qualified name, and the
    # file each edge reaches, P167, which version 9 never names; 14: a code symbol keyed by its file and qualified name,
    # a file's commit and unresolved names, and the provider a join's link is the code of, P167; 15: the project's
    # glossary terms, in a table of its own, so version 9 still reads and writes the store
    version=15,
    compatible_from=9,
    upgrade=upgrade,
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
    ), Table(
        # each work record's and message's number at its address, from the project's counter, with its title and why
        'numbered', place='metaform', key=('kind', 'item_id'),
        columns=(Column('kind', required=True), Column('item_id', required=True), Column('address', required=True),
                 Column('number', 'int', required=True), Column('title'), Column('why')),
        indexes=(Index(('address', 'number')),),
    ), Table(
        # `items` once the records written before numbering are numbered
        'numbering', place='metaform', key=('name',),
        columns=(Column('name', required=True), Column('at', required=True)),
    ), *CODE_TABLES, Table(
        # the project's glossary terms the person and agents add, edit or remove, `glossary.py`, in the project's own
        # database so a new intake keeps them; an element's own name is read from the map and kept here only when
        # edited or removed. A term added at a node holds its number there.
        'terms', place='project', key=('key',),
        columns=(Column('key', required=True), Column('term', required=True), Column('state', required=True),
                 Column('definition'), Column('why'), Column('source'), Column('address'), Column('number', 'int'),
                 Column('by'), Column('session'), Column('at', required=True)),
        indexes=(Index(('address', 'number')),),
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
                number_items,
            )
        },
        "reply": Operation(close_message, write=True),
        "reopen": Operation(reopen_message, write=True),
        **{fn.__name__: Operation(fn, retained=True) for fn in (work, messages, ticket, reports, report, items_numbered,
                                                                numbers_of, item_at, listed_items)},
    },
    decorate=decorate,
    item_write=item_write,
)
