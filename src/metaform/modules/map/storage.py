"""Map's work queue, messages, challenges, plans and report records.

Tables and operations are owned here and installed through the public DAO.
Legacy physical names preserve existing stores and exchange documents.
"""

from __future__ import annotations

import dataclasses
import hashlib
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
    is_work,
    new_id,
    now,
    paged,
    reference,
    row_cursor,
    shown_open,
    sliced,
    status,
)
from metaform.data import (
    DataTx as Tx,
)

from . import ticket_history

Row = DataRow
ANSWERS = ("A", "B", "C")
# The kinds of item map numbers at an address, MCP-037: a work record, and a question or message, by their own ids.
NUMBERED = ("work", "message")
WORK_FIELDS = ("condition", "kind", "note", "task", "held", "reviewed")
REPORT_KINDS = ("report", "feedback", "shape")
CONVERSATION_TASKS = frozenset({"Conversation with the system agent", "Sessions from editors"})


def validate_hold_reason(value: Any) -> str:
    """Validate the newly supplied reason, independently of existing ticket notes or reasons."""
    if not isinstance(value, str) or not value.strip():
        raise StoreError("An explicit hold requires a nonblank hold_reason.",
                         "supply hold_reason explaining why this ticket must wait")
    return value.strip()


def _remember_hold(tx: Tx, work_id: str, reason: str) -> None:
    tables = tx.tables()
    if tables.update("ticket_settings", {"work_id": work_id}, {"hold_reason": reason}) is None:
        tables.insert("ticket_settings", {"work_id": work_id, "hold_reason": reason})
    tables.insert("hold_history", {"id": new_id(), "work_id": work_id, "reason": reason, "at": now()})


def remember_work_source(tx: Tx, work_id: str, text: str | None, *, interpretation: str | None = None,
                         provenance: Any = None, operation: str = 'revision') -> dict[str, Any]:
    """Retain exact source words separately from the operative task, without inferring authorship."""
    details = dict(provenance or {})
    source = details.pop('text', text)
    if source is not None and not isinstance(source, str):
        raise StoreError('Source text must be a string.', 'supply exact source text')
    tables = tx.tables()
    earlier = tables.rows('work_sources', {'work_id': work_id}, limit=0).results
    revision = hashlib.sha256((interpretation or '').encode()).hexdigest()
    made = tables.insert('work_sources', {'source_id': new_id(), 'work_id': work_id,
        'sequence': len(earlier) + 1, 'operation': operation, 'text': source,
        'interpretation': interpretation, 'task_revision': revision,
        'provenance': details or {'author': 'unknown'}, 'created': now()})
    return made


def work_sources(tx: Tx, work_id: str, source_id: str | None = None, *, contents: bool = True) -> tuple[dict[str, Any], ...]:
    """Addressable request/revision records, in publication order. Summaries contain no repeated source prose."""
    tables = tx.tables()
    if source_id:
        one = tables.get('work_sources', {'source_id': source_id})
        records = [one] if one is not None and one['work_id'] == work_id else []
    else:
        records = sorted(tables.rows('work_sources', {'work_id': work_id}, limit=0).results,
                         key=lambda one: one['sequence'])
    return tuple({**(one if contents else {key: one[key] for key in (
        'source_id', 'work_id', 'sequence', 'operation', 'task_revision', 'provenance', 'created')}),
        'read': f'metaform map work op=sources id={work_id} source_id={one["source_id"]}'} for one in records)


def set_work_hold(tx: Tx, work_id: str, *, hold: bool, hold_reason: Any = None) -> WorkRecord:
    """Set the explicit execution hold, retaining each deliberate reason after release."""
    row = _work_row(tx, work_id)
    if hold and row["task"] not in CONVERSATION_TASKS:
        _remember_hold(tx, work_id, validate_hold_reason(hold_reason))
    tables = tx.tables()
    if tables.update("ticket_settings", {"work_id": work_id}, {"hold": int(hold)}) is None:
        tables.insert("ticket_settings", {"work_id": work_id, "hold": int(hold)})
    _ticket_changed(tx, work_id)
    return work_record(tx, row)


def inherit_work_board(tx: Tx, work_id: str, owner_id: str) -> bool:
    """Place an implicitly filed generated ticket with its owner, preserving every explicit board choice."""
    row = _work_row(tx, work_id)
    _work_row(tx, owner_id)
    if row['done'] is not None:
        return False
    tables = tx.tables()
    current = tables.get('ticket_settings', {'work_id': work_id})
    # Historical explicit first-board edits also stored NULL. An existing row cannot prove implicit placement.
    if current is not None:
        return False
    owner: dict[str, Any] = tables.get('ticket_settings', {'work_id': owner_id}) or {}
    board = str(owner.get('board') or '')
    tables.insert('ticket_settings', {'work_id': work_id, 'board': board})
    _ticket_changed(tx, work_id)
    return True


def work_hold_history(tx: Tx, work_id: str) -> tuple[dict[str, Any], ...]:
    """Read every reason explicitly recorded for this ticket, including released holds."""
    _work_row(tx, work_id)
    tx.tables().get("hold_history", {"id": ""})
    return tuple(dict(row) for row in tx.execute(
        'SELECT id, work_id, reason, at FROM "map.hold_history" WHERE work_id=? ORDER BY rowid', (work_id,)))


def held_work(tx: Tx) -> tuple[dict[str, Any], ...]:
    """Read open executable holds and their recorded explanations on this base."""
    tx.tables().get("ticket_settings", {"work_id": ""})
    rows = tx.execute(
        'SELECT w.*, s.hold, s.hold_reason, s.board FROM work w '
        'LEFT JOIN "map.ticket_settings" s ON s.work_id=w.work_id '
        "WHERE w.done IS NULL AND COALESCE(w.outcome, '') NOT IN ('cancelled', 'superseded', 'failed') "
        'AND (w.held<>0 OR COALESCE(s.hold, 0)<>0) '
        "AND COALESCE(w.task, '') NOT IN (?, ?) ORDER BY w.row", tuple(sorted(CONVERSATION_TASKS)))
    return tuple({'id': str(row['work_id']), 'task': row['task'], 'note': row['note'], 'held': bool(row['held']),
                  'map': {'hold': bool(row['hold']), 'hold_reason': row['hold_reason'], 'board': row['board'] or ''}}
                 for row in rows if is_work(row['condition'], row['task']))


def unhold_all_work(tx: Tx) -> int:
    """Release open executable tickets on this base without moving or rewriting their context."""
    changed = [row['id'] for row in held_work(tx)]
    for work_id in changed:
        tx.execute("UPDATE work SET held=0 WHERE work_id=?", (work_id,))
        tx.tables().update("ticket_settings", {"work_id": work_id}, {"hold": 0})
    _ticket_changed(tx, *changed)
    return len(changed)


def unhold_reviewed_work(tx: Tx, preview: list[dict[str, Any]]) -> dict[str, int]:
    """Validate reviewed work inside the same write transaction that releases its holds."""
    actual = held_work(tx)
    fields = ('id', 'task', 'note', 'held', 'map')
    expected = [{key: row.get(key) for key in fields} for row in preview]
    if sorted(expected, key=lambda row: str(row['id'])) != sorted(actual, key=lambda row: str(row['id'])):
        return {'changed': 0, 'review_changed': len(actual)}
    return {'changed': unhold_all_work(tx), 'review_changed': 0}


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


def _ticket_changed(tx: Tx, *work_ids: str, kind: str = "ticket") -> None:
    """The tickets this write changes, said on its `map.changed`, so a dispatch runner reads only its own, BASE-053.
    `kind` says what changed: `ticket` for anything that can decide whether it starts or ends, `note` for its words
    alone, its note, title, links or reviewed mark, and `step` for its plan and steps, so the agent starter, which
    starts nothing for words or steps, reads nothing for them (UX review round 1, runaway F3). A record done says
    `done` beside `ticket`, so what acts on a ticket's end alone, dispatch's plan report, reads nothing for any
    other change (code.dispatcher.agent#10)."""
    for work_id in work_ids:
        tx.concern(work_id=work_id, kind=kind)


def _next_work_row(tx: Tx, table: str) -> int:
    """Keep raw ticket and step row identities available for a later board restore."""
    key = f"map.row.{table}"
    held = tx.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    current = int(tx.execute(f"SELECT COALESCE(MAX(row), 0) FROM {table}").fetchone()[0])
    number = max(current, int(held[0]) if held else 0) + 1
    tx.execute("INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, str(number)))
    return number


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
    hold_reason: Any = None,
    provenance: Any = None,
) -> WorkRecord:
    """Write the condition of an element or join as its own record, apart from the map, STORE-042; a ticket carries
    its kind beside it. It takes the next number at its node's address with its title, MCP-037: the title given, else
    the first line of its task or note."""
    notices: list[Notice] = []
    stage, ticket_kind = _condition(condition, notices), _kind(kind)  # both checked before anything is written
    stated = _work_text(task, "task", notices)
    reason = validate_hold_reason(hold_reason) if held and stated not in CONVERSATION_TASKS else None
    _shown(stage, stated)
    target_kind, thing = work_target(tx, node, notices)
    _backfill(tx)
    work_id = new_id()
    # a new ticket is placed last in its column, so the first move in a column of new tickets has no places to write
    # but its own; a column holding tickets with no place leaves it unplaced, last in the order made, as they are
    # (independent check of the UX recheck fix, 2026-10-17: the first drop into a new To do named every card)
    last = tx.execute(
        "SELECT CASE WHEN COUNT(*) > COUNT(position) THEN NULL ELSE COALESCE(MAX(position) + 1, 0) END FROM work "
        "WHERE done IS NULL AND taken IS NULL AND held=?",
        (int(bool(held)),),
    ).fetchone()[0]
    tx.execute(
        "INSERT INTO work(row, work_id, target_kind, target_id, condition, note, task, held, reviewed, created, kind, "
        "position) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _next_work_row(tx, "work"),
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
            last,
        ),
    )
    remember_work_source(tx, work_id, stated, interpretation=stated, provenance=provenance, operation="original")
    _link(tx, work_id, links, notices)
    if reason is not None:
        _remember_hold(tx, work_id, reason)
    _number(tx, "work", work_id, target_kind, thing, _titled(title, task, note))
    _ticket_changed(tx, work_id)
    _ticket_changed(tx, work_id, kind="filed")  # new on the board: dispatch's `board.changed` reads it, no other change
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


WORDS_ONLY = frozenset({"note", "title", "links", "reviewed"})  # an edit of these changes no start, `_ticket_changed`


def edit_work(tx: Tx, work_id: str, changes: Any, *, provenance: Any = None) -> WorkRecord:
    """Change a work record's fields, attachment or reference links in place, preserving its identity and progress."""
    notices: list[Notice] = []
    before = _work_row(tx, work_id)
    given = as_object(changes)
    if given is None:
        raise StoreError("The changes to a work record are an object of its fields.", "metaform help map work")
    if given.get("held") and given.get("task", before["task"]) not in CONVERSATION_TASKS:
        _remember_hold(tx, work_id, validate_hold_reason(given.get("hold_reason")))
    _ticket_changed(tx, work_id, kind="note" if given and set(given) <= WORDS_ONLY else "ticket")
    for key in sorted(given):
        if key == "hold_reason":
            continue
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
    if provenance is not None or 'task' in given and after['task'] != before['task']:
        # Legacy records gain a truthful pre-edit snapshot. No author or original user wording is invented.
        if not work_sources(tx, work_id, contents=False):
            remember_work_source(tx, work_id, before['task'], interpretation=before['task'], operation='snapshot')
        remember_work_source(tx, work_id, after['task'], interpretation=after['task'], provenance=provenance)
    if after["done"] is None:  # an edit never leaves an open record shown nowhere; the transaction rolls back
        _shown(str(after["condition"]), after["task"])
    return work_record(tx, after, tuple(notices))


def retarget_work(tx: Tx, old: str, new: str) -> dict[str, int]:
    """Move every work record, question and message at element `old` to element `new`, and every ticket's reference
    link to it, when the base renames or merges `old` into `new`, LAYER-025: each keeps its id, progress and text, and
    takes the next number at its new address, MCP-037. Done records move too, so the part's history moves with it."""
    moved = {"work": 0, "messages": 0, "links": 0}
    for table, key, kind in (("work", "work_id", "work"), ("messages", "message_id", "message")):
        found = [str(row[key]) for row in tx.execute(
            f"SELECT {key} FROM {table} WHERE target_kind='element' AND target_id=?", (old,))]
        tx.execute(f"UPDATE {table} SET target_id=? WHERE target_kind='element' AND target_id=?", (new, old))
        for ident in found:
            _number(tx, kind, ident, "element", new)
        if table == "work":
            _ticket_changed(tx, *found)
        moved[table] = len(found)
    moved["links"] = tx.execute(
        "UPDATE work_links SET target_id=? WHERE target_kind='element' AND target_id=?", (new, old)).rowcount
    return moved


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
    _ticket_changed(tx, work_id, kind="step")
    tx.execute("UPDATE work SET steps=? WHERE work_id=?", (count, work_id))
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def worksheet_progress(tx: Tx, work_id: str, total: int, checked: int) -> WorkRecord:
    """Project a worksheet's current checklist counts without altering its provenance or completed-step log."""
    if type(total) is not int or type(checked) is not int or not 0 <= checked <= total:
        raise StoreError("Worksheet progress needs integer counts with 0 <= checked <= total.",
                         "give the checklist total and number checked")
    _work_row(tx, work_id)
    _ticket_changed(tx, work_id, kind="step")
    tx.execute("UPDATE work SET steps=?, steps_done=? WHERE work_id=?", (total, checked, work_id))
    return work_record(tx, _work_row(tx, work_id))


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
    _ticket_changed(tx, work_id, kind="step")
    tx.execute("UPDATE work SET steps=?, steps_done=? WHERE work_id=?", (planned, done, work_id))
    tx.execute(
        "INSERT INTO work_steps(row, work_id, number, said, at) VALUES (?, ?, ?, ?, ?)",
        (_next_work_row(tx, "work_steps"), work_id, done, _work_text(said, "said", notices), now()),
    )
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def take_work(tx: Tx, work_id: str, steps: Any = None, by: Any = None) -> WorkRecord:
    """An agent takes the record's task, MAP-049: it is in progress, keeps its kind, VIEW-035, records who took it, and
    waits no longer. Peers may participate in already taken work while its first taker remains recorded. Finished
    work cannot be taken. A record with no condition is taken as a ticket is."""
    row = _work_row(tx, work_id)
    if row["done"] is not None:
        raise StoreError(f"This work record was done at {row['done']}.", "metaform map work open=true")
    if row["taken"] is not None:
        return work_record(tx, row, (Notice("taken", "Peer participation keeps the recorded first taker and progress."),))
    notices: list[Notice] = []
    _ticket_changed(tx, work_id)
    tx.execute(
        "UPDATE work SET taken=?, taken_by=?, held=0, steps=COALESCE(?, steps) WHERE work_id=?",
        (now(), _work_text(by, "by", notices), _count(steps, notices), work_id),
    )
    _building(tx, work_id)
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def move_work(tx: Tx, work_id: str, column: Any, position: Any = None, by: Any = None, kept: bool = False,
              hold_reason: Any = None) -> WorkRecord:
    """Put a ticket in a column of the board, and at a place in it, MAP-048: backlog holds it, to do frees it, doing
    takes it and done finishes it; a ticket moved back out of doing or done is open and untaken again. `kept` leaves
    every place as it is, the ticket's own too: a reservation given back to To do and taken at once, in one atomic
    block, changes no other ticket, so its event names it alone (UX recheck 2026-10-17, b410f6a5); a ticket given
    back where it waited keeps its own stored place, which `position`, a place counted from the top, is not once the
    column has a gap."""
    row = _work_row(tx, work_id)
    if column not in COLUMNS:
        raise StoreError(f"{column!r} is not a column: backlog, todo, doing or done.", "metaform help map work")
    if column == "backlog" and row["task"] not in CONVERSATION_TASKS:
        _remember_hold(tx, work_id, validate_hold_reason(hold_reason))
    notices: list[Notice] = []
    _ticket_changed(tx, work_id)
    reopened = row["done"] is not None and column != "done"
    if column in ("todo", "backlog"):
        # given back, its fix has not held or is not yet given: no landed fix is kept, nor its resolution
        tx.execute("UPDATE work SET resolution=NULL WHERE work_id=?", (work_id,))
        tx.tables().update("ticket_settings", {"work_id": work_id}, {"landed": None})
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
    if column == "done":
        _epic_closed(tx, work_id)
    elif reopened:
        _epic_reopened(tx, work_id)
    if kept:
        return work_record(tx, _work_row(tx, work_id), tuple(notices))
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
        (str(other["work_id"]), other["position"])
        for other in tx.execute(
            f"SELECT work_id, position FROM work WHERE work_id<>? AND {same} ORDER BY position IS NULL, position, row",
            (work_id,),
        )
    ]
    at = len(others) if position is None else max(0, min(len(others), int(position)))
    # Only the places that change are written and said: a ticket taken back to its own place in a column whose order
    # holds changes no other, so its event names it alone and a page reads one ticket (UX recheck 2026-10-17, b410f6a5)
    # A place is an order, not a count: a ticket keeps its place while it still sorts below the one above it, so a
    # drop at the end, or above a gap an agent's take left, writes the moved ticket alone; unplaced tickets below it
    # sort after every placed one, in the order made, and keep no place (independent check, 2026-10-17)
    placed = [*others[:at], (work_id, None), *others[at:]]
    above: int | None = None  # the place of the ticket above, None at the top
    for index, (ident, held) in enumerate(placed):
        if ident != work_id:
            if held is not None and (above is None or held > above):
                above = held
                continue
            if held is None and index > at:
                break
            _ticket_changed(tx, ident)  # its place in the column
        place = 0 if above is None else above + 1
        tx.execute("UPDATE work SET position=? WHERE work_id=?", (place, ident))
        above = place
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def finish_work(tx: Tx, work_id: str, resolution: Any = None, why: Any = None, outcome: str = "completed",
                proven: bool = False) -> WorkRecord:
    """Mark a work record done, keeping its resolution beside it, the why of that resolution with its number, MCP-037,
    and how it ended, `outcome`: a terminal state of the one status vocabulary, completed unless the person cancelled
    it or it failed, so a cancelled ticket never reads as completed, P232; a record already done keeps its first
    resolution and outcome. Resolved work closes directly. Delivery receipts, commits, publication and activation
    never gate closure. `proven` remains accepted for callers using the former proof API."""
    ended = status.known(outcome, "map work op=done id=<id>")
    if ended not in status.TERMINAL:
        raise StoreError(f"A work record ends {', '.join(status.TERMINAL)}, not {ended}.", "map work op=done id=<id>")
    notices: list[Notice] = []
    row = _work_row(tx, work_id)
    if row["done"] is not None:
        notices.append(Notice("id", f"This work record was done at {row['done']}; its resolution was kept."))
        return work_record(tx, row, tuple(notices))
    if isinstance(why, str) and why.strip():
        tables = tx.tables()
        if tables.get("numbered", {"kind": "work", "item_id": work_id}) is not None:
            tables.update("numbered", {"kind": "work", "item_id": work_id}, {"why": why.strip()})
    _ticket_changed(tx, work_id)
    tx.concern(work_id=work_id, kind="done")  # beside `ticket`: heard by what acts on a ticket's end alone
    tx.execute(
        "UPDATE work SET done=?, resolution=?, outcome=? WHERE work_id=?",
        (now(), _work_text(resolution, "resolution", notices), ended, work_id),
    )
    _epic_closed(tx, work_id)
    return work_record(tx, _work_row(tx, work_id), tuple(notices))


def complete_delivery(tx: Tx, work_id: str) -> WorkRecord:
    """Close staged work, including faults, after dispatch records successful delivery."""
    row = _work_row(tx, work_id)
    settings = tx.tables().get("ticket_settings", {"work_id": work_id})
    if row["done"] is not None or settings is None or not settings["landed"]:
        return work_record(tx, row)
    return finish_work(tx, work_id, row["resolution"], proven=True)



def remove_work(tx: Tx, work_id: str) -> dict[str, Any]:
    """Delete a ticket for good: its row, its steps, links, plans and reports, and what the map module keeps on it, its
    glyph, settings, eligible agents, order, question links and number. Its node stays, and a question it carried stays
    as the node's. Said on `map.changed` as a change to the ticket, so every page drops its card. The person's own act,
    2026-10-20: a ticket could be cancelled, which kept it in the Archive, but never deleted."""
    row = _work_row(tx, work_id)
    record = work_record(tx, row, ())
    _remove_work_rows(tx, [work_id])
    return {"removed": work_id, "address": record.address, "task": record.task}


def _remove_work_rows(tx: Tx, work_ids: Sequence[str]) -> None:
    """One deletion path for individual tickets and board wipes, including unloaded owners' declared rows."""
    from metaform.data import delete_work_rows
    _ticket_changed(tx, *work_ids)
    # Stores created before the high-water marks must reserve their rows before deletion too.
    for table in ("work", "work_steps"):
        _next_work_row(tx, table)
    tables = tx.tables()
    for work_id in work_ids:
        tables.delete("numbered", {"kind": "work", "item_id": work_id})
    delete_work_rows(tx.db, work_ids)


def board_snapshot(tx: Tx, name: str) -> dict[str, Any]:
    """Capture ticket-owned store rows before a board is wiped."""
    from metaform.data import export_work_rows
    board = tx.tables().get("boards", {"name": name}) if name else None
    if name and board is None:
        raise StoreError(f"There is no board named {name!r}.", "metaform map boards")
    found = tx.execute('SELECT w.* FROM work w LEFT JOIN "map.ticket_settings" s ON s.work_id=w.work_id '
                       "WHERE COALESCE(s.board, '')=? ORDER BY w.row", (name,)).fetchall()
    work_ids = [str(row["work_id"]) for row in found]
    columns = dict.fromkeys(("backlog", "todo", "doing", "done"), 0)
    for row in found:
        column = "done" if row["done"] else "doing" if row["taken"] else "backlog" if row["held"] else "todo"
        columns[column] += 1
    selected = set(work_ids)
    numbered = [dict(row) for row in tx.tables().rows("numbered", {"kind": "work"}, limit=0).results
                if row["item_id"] in selected]
    return {"name": name, "board": dict(board) if board else None, "base": tx.base_id, "work_ids": work_ids,
            "columns": columns, "rows": export_work_rows(tx.db, work_ids), "numbered": numbered}


def wipe_board_rows(tx: Tx, snapshot: dict[str, Any]) -> None:
    """Remove only backed-up tickets, refusing a board changed during session shutdown."""
    current = board_snapshot(tx, str(snapshot["name"]))
    if set(current["work_ids"]) != set(snapshot["work_ids"]):
        raise StoreError("The board changed while its sessions stopped. Its backup is kept. Wipe it again.",
                         "metaform map boards")
    _remove_work_rows(tx, snapshot["work_ids"])
    if snapshot["name"]:
        tx.tables().delete("boards", {"name": snapshot["name"]})
    tx.concern(kind="board-wipe")


def restore_board_rows(tx: Tx, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Insert raw backup rows into this base, preserving subsequent work."""
    from metaform.data import insert_work_rows
    if tx.base_id != snapshot["base"]:
        raise StoreError("This backup belongs to another map.", "metaform map bases")
    existing = {str(row[0]) for row in tx.execute("SELECT work_id FROM work").fetchall()}
    restored = [str(one) for one in snapshot["work_ids"] if one not in existing]
    skipped = [str(one) for one in snapshot["work_ids"] if one in existing]
    board = snapshot["board"]
    if board and tx.tables().get("boards", {"name": board["name"]}) is None:
        tx.tables().insert("boards", board)
    insert_work_rows(tx.db, snapshot["rows"], restored)
    for row in snapshot["numbered"]:
        if row["item_id"] in restored:
            tx.tables().insert("numbered", row)
    _ticket_changed(tx, *restored)
    tx.concern(kind="board-restore")
    return {"restored": restored, "skipped": skipped}


def _epic_of(tx: Tx, work_id: str) -> str | None:
    """The epic a ticket belongs to, the `epic` its settings name, or None."""
    row = tx.tables().get("ticket_settings", {"work_id": work_id})
    return str(row["epic"]) if row is not None and row["epic"] else None


def _epic_closed(tx: Tx, work_id: str) -> None:
    """A child's done closes its epic once every child naming it is done, so the person's request reads finished and
    the epic's one worktree goes to review and merge once: completed when any child completed, else as its children
    ended. An epic closed by hand before then stays as it is."""
    epic = _epic_of(tx, work_id)
    if epic is None:
        return
    children = [str(row["work_id"]) for row in tx.tables().rows("ticket_settings", {"epic": epic}, limit=0).results]
    ended = tx.execute(
        f"SELECT done, outcome FROM work WHERE work_id IN ({', '.join('?' * len(children))})", children).fetchall()
    if not ended or any(row["done"] is None for row in ended):
        return
    held = tx.execute("SELECT done FROM work WHERE work_id=?", (epic,)).fetchone()
    if held is None or held["done"] is not None:
        return
    outcomes = {str(row["outcome"] or "completed") for row in ended}
    finish_work(tx, epic, f"Every one of its {len(ended)} child tickets is done.",
                outcome="completed" if "completed" in outcomes else min(outcomes))


def _epic_reopened(tx: Tx, work_id: str) -> None:
    """A child moved back out of Done reopens its epic, so the epic's worktree is reviewed and merged again only once
    every child is done again."""
    epic = _epic_of(tx, work_id)
    held = tx.execute("SELECT done FROM work WHERE work_id=?", (epic,)).fetchone() if epic else None
    if epic is not None and held is not None and held["done"] is not None:
        move_work(tx, epic, "todo", kept=True)


def prove_work(tx: Tx, work_id: str) -> WorkRecord:
    """Require delivery evidence for this fault ticket, retained through recurrence and reopen."""
    _work_row(tx, work_id)
    tables = tx.tables()
    if tables.update("ticket_settings", {"work_id": work_id}, {"proof": 1}) is None:
        tables.insert("ticket_settings", {"work_id": work_id, "proof": 1})
    return work_record(tx, _work_row(tx, work_id))






def _past_work(tx: Tx, target: Node) -> tuple[PastWork, ...]:
    """Completed work at this node, newest first, without loading the agent's log, MAP-051."""
    stored = tuple(
        PastWork(str(row["work_id"]), str(row["done"]))
        for row in tx.execute(
            "SELECT work_id, done FROM work WHERE target_kind=? AND target_id=? AND done IS NOT NULL "
            "ORDER BY done DESC, row DESC",
            (target.kind, target.id),
        )
    )
    address = tx.rows.node_address(target.kind, target.id)
    if address is None:
        return stored
    attachment = f'{target.kind}:{address if target.kind == "element" else target.id}'
    live = {str(row[0]) for row in tx.execute('SELECT work_id FROM work')}
    shed = (PastWork(record['item'], record['done'])
            for work_id, record in ticket_history.read(tx.project_id).tickets.items()
            if work_id not in live and record['target'] == attachment)
    return tuple(sorted((*stored, *shed), key=lambda record: record.done, reverse=True))


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


def work_snapshot(tx: Tx, work_id: str) -> str:
    """The ticket's persisted map state, kept in its completion commit and compared before shedding it."""
    from metaform.data import export_work_rows
    _work_row(tx, work_id)
    rows = [{'table': entry['table']['name'], 'rows': entry['rows']}
            for entry in export_work_rows(tx.db, [work_id]) if entry['module'] == 'map']
    numbered = tx.tables().get('numbered', {'kind': 'work', 'item_id': work_id})
    return json.dumps({'version': 1, 'rows': sorted(rows, key=lambda entry: entry['table']), 'numbered': numbered},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))


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
    ids: Sequence[str] | None = None,
    done_since: str | None = None,
    done_before: str | None = None,
) -> Page[WorkRecord]:
    """The work records, in row order, by node, condition or whether open, STORE-042; not a context read, since a
    work record has no layer. With joins, an element's own records and those on the joins it receives or
    provides. With ids, those tickets alone, as a page reads the ones a change named, VIEW-018. With done_since, the
    open records and those done at or after that time, as the board shows them; with done_before, those done before
    it, the board's archive (times as `home.now` writes them, so they compare as text)."""
    target = work_target(tx, node, []) if node is not None else None
    around = joins and target is not None and target[0] == "element"

    def fetch(cursor: str | None, count: int) -> list[Row]:
        where: list[str] = ["row > ?"]
        params: list[Any] = [row_cursor(cursor)]
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
        if ids is not None:
            where.append(f"work_id IN ({', '.join('?' for _ in ids) or 'NULL'})")
            params.extend(ids)
        if done_since is not None:
            where.append("(done IS NULL OR done >= ?)")
            params.append(done_since)
        if done_before is not None:
            where.append("done < ?")
            params.append(done_before)
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
        params: list[Any] = [row_cursor(cursor)]
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
    """The work records and messages numbered at `address` below `before`, newest first, at most `limit`,
    as items are listed, MCP-037: each one's number, kind, title and why, from one read of the address's numbers. One
    whose record is gone is left out, as `item_at` leaves it out."""
    rows = sorted((row for row in tx.tables().rows("numbered", {"address": address}, limit=0).results
                   if before is None or row["number"] < before), key=lambda row: -row["number"])
    found: list[dict[str, Any]] = []
    for held in rows:
        if len(found) >= limit:
            break
        kind: str | None = None
        if held["kind"] == "work":
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


def agent_name(value: Any) -> Any:
    """Keep the retired agent identifier readable at persisted and input boundaries."""
    return 'antigravity' if value == 'gemini' else value


def runtime_values(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize agent identities without changing runtime selections or decision evidence."""
    kept = dict(values)
    if 'agent' in kept:
        kept['agent'] = agent_name(kept['agent'])
    eligible = kept.get('eligible')
    if isinstance(eligible, list):
        kept['eligible'] = [agent_name(value) for value in cast(list[Any], eligible)]
    decision = kept.get('decision')
    if isinstance(decision, dict) and 'agent' in decision:
        kept['decision'] = {**decision, 'agent': agent_name(decision['agent'])}
    return kept


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
    if found < 23:
        for row in tx.rows('ticket_settings', limit=0).results:
            before = {field: row[field] for field in ('agent', 'decision')}
            after = runtime_values(before)
            if after != before:
                tx.update('ticket_settings', {'work_id': row['work_id']}, after)
        for row in tx.rows('eligible', limit=0).results:
            before = row['agents']
            if isinstance(before, list):
                after = [agent_name(value) for value in cast(list[Any], before)]
                if after != before:
                    tx.update('eligible', {'work_id': row['work_id']}, {'agents': after})


TABLES = Tables(
    # 10: the number, title and why of each work record and message at its address, MCP-037, in tables of their own,
    # so version 9 still reads and writes the store; 9: a ticket's kind beside the part's state; 8: a part's state is a
    # stage or broken; 7: no foreign keys; 11: the code layer's index, P167, in tables of their own, so version 9
    # still reads and writes the store; 12: how a done work record ended, completed, cancelled or failed, P232, in a
    # column version 9 never names, so it still reads and writes the store, and a record it closes reads as completed;
    # 13: the code layer's links in a table of their own, a symbol's provider form beside its qualified name, and the
    # file each edge reaches, P167, which version 9 never names; 14: a code symbol keyed by its file and qualified name,
    # a file's commit and unresolved names, and the provider a join's link is the code of, P167; 15: the project's
    # glossary terms, in a table of its own, so version 9 still reads and writes the store; 16: the code layer's four
    # tables dropped with map code-import and the other code-* verbs, code.analyzer.refactoring#1a (2026-10-15), and
    # an earlier version that still declares them makes them again, empty, so version 9 still reads the store; 17: the
    # tickets each ticket waits on, `after`, in a table of its own, read by dispatch's agent starter (UX review round 1,
    # 2026-10-17), so version 9 still reads and writes the store; 18: whether a ticket closes only with proof and when
    # its fix landed, `proof` and `landed` in ticket_settings, columns version 9 never names (code.scheduler.task#9,
    # 2026-10-19), so it still reads and writes the store; 19: the epic a ticket belongs to and how many agents work on
    # it at once, `epic` and `agents` in ticket_settings (code.dispatcher.agent#7a, 2026-10-19), columns version 9
    # never names; 20: the named board a ticket is on, `board` in ticket_settings, and the project's named boards with
    # each its own archive cutoff, `boards` (the person's need, 2026-10-20), a column and a table version 9 never names;
    # 21: their indexes, by board and by created; 22: nullable assignment model, effort and decision provenance,
    # which older versions never name; 23: the retired agent identity becomes antigravity in ticket runtime and
    # eligibility values, without changing any table layout; 24: latest explicit hold reason and retained reason
    # history, in nullable settings and a new table that earlier versions never name; 25: nullable Fast choice,
    # a text column earlier versions never name, with NULL inheriting and true/false explicit; 26: exact source
    # revisions apart from their task interpretations, in a new table older writers never name
    version=26,
    compatible_from=9,
    upgrade=upgrade,
    legacy_upgrade=legacy_upgrade,
    legacy_fold=legacy_fold,
    tables=(*FEATURE_TABLES, Table(
        'work_sources', place='metaform', key=('source_id',),
        columns=(Column('source_id', required=True), Column('work_id', required=True),
                 Column('sequence', 'int', required=True), Column('operation', required=True), Column('text'),
                 Column('interpretation'), Column('task_revision', required=True), Column('provenance', 'json'),
                 Column('created', required=True)),
        indexes=(Index(('work_id',)),),
    ), Table(
        'glyphs', place='metaform', key=('work_id',),
        columns=(Column('work_id', required=True), Column('glyph', required=True)),
    ), Table(
        # each ticket's preferred agent and the person's hold, which hides it from agents and automatic starts
        'ticket_settings', place='metaform', key=('work_id',),
        # and whether it closes only with proof, `proof`, and when its fix landed while it is watched, `landed`; the
        # epic it belongs to, `epic`, which closes once every child naming it is done and whose worktree its children
        # share; and how many agents work on it at once, `agents`, one when none is set
        # and the named board the ticket is on, `board`, none for the project's first board (2026-10-20)
        # and assignment runtime, `model`, `effort`, `decision`, which the person can change before the start
        columns=(Column('work_id', required=True), Column('agent'), Column('hold', 'int', default=0),
                 Column('proof', 'int', default=0), Column('landed'), Column('epic'), Column('agents', 'int'),
                 Column('board'), Column('model'), Column('effort'), Column('decision', 'json'), Column('hold_reason'), Column('fast')),
        indexes=(Index(('board',)),),
    ), Table(
        'hold_history', place='metaform', key=('id',),
        columns=(Column('id', required=True), Column('work_id', required=True), Column('reason', required=True),
                 Column('at', required=True)),
        indexes=(Index(('work_id',)),),
    ), Table(
        # the project's named boards besides its first: each with its own archive cutoff, `line`, the time before
        # which its done tickets are in its Archive; a ticket names its board in ticket_settings (the person's need,
        # 2026-10-20: work for a new effort moves to that effort's board instead of piling up on the one board)
        'boards', place='metaform', key=('name',),
        columns=(Column('name', required=True), Column('created', required=True), Column('line')),
        indexes=(Index(('created',)),),
    ), Table(
        'eligible', place='metaform', key=('work_id',),
        columns=(Column('work_id', required=True), Column('agents', 'json', required=True)),
    ), Table(
        # the tickets a ticket waits on, `after_work`: no agent starts it automatically until each is done
        'after', place='metaform', key=('work_id',),
        columns=(Column('work_id', required=True), Column('works', 'json', required=True)),
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
    ), Table(
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
                set_work_hold,
                inherit_work_board,
                unhold_all_work,
                unhold_reviewed_work,
                edit_work,
                remember_work_source,
                retarget_work,
                move_message,
                move_work,
                take_work,
                plan_work,
                worksheet_progress,
                step_work,
                finish_work,
                complete_delivery,
                remove_work,
                wipe_board_rows,
                restore_board_rows,
                prove_work,
                answer,
                approve,
                add_plan,
                save_report,
                ask,
                tell,
                number_items,
            )
        },
        "board_snapshot": Operation(board_snapshot),
        "reply": Operation(close_message, write=True),
        "reopen": Operation(reopen_message, write=True),
        **{fn.__name__: Operation(fn, retained=True) for fn in (work, messages, ticket, work_snapshot, work_sources, work_hold_history, held_work,
                                                                reports, report,
                                                                items_numbered, numbers_of, item_at, listed_items)},
    },
    decorate=decorate,
    item_write=item_write,
)
