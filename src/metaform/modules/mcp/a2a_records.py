"""What A2A keeps beside the tickets it opens, P004 and P005, in the mcp module's own tables at project level, STORE-045.

`a2a_tasks` holds one row per ticket a message opened at the Address its contextId named: the message's id, so a
client that sends the same message again is answered with the ticket it opened instead of a second one, as A2A asks of
a retried send; that Address; and who sent it. The ticket itself is the task: its state, steps and resolution are read
from the work record every time, never copied here.

`a2a_asks` holds a message that named no Address. A2A lets the agent give the context, so Metaform answers with a task
of its own id in a context of its own id, in `input_required`, offering the Addresses that fit, and keeps the work
here until the client's reply on that task names one; the ticket opened then is recorded in `work_id`, and the task
reads as that ticket from then on. A question the client cancels is kept with `cancelled` set.

`a2a_push` holds the push notification configurations clients set on a task, with the credentials Metaform presents to
their webhook. A2A asks that a configuration last until its task ends or the client deletes it, so it is kept in the
project's database and the server watches its task again after a restart.

All three live in the project's own database, which a clear of the project's metaforms keeps, so a task stays readable
for as long as its ticket does. Nothing here imports the A2A SDK: the module loads without it, and only the HTTP server
reaches it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, cast

from metaform.data import Column, Index, Store, Table, Tables

TASKS = Table('a2a_tasks', place='project', key=('work_id',), columns=(
    Column('work_id', required=True), Column('message_id', required=True), Column('context_id', required=True),
    Column('caller'), Column('created', required=True), Column('seq', 'int', required=True)),
    indexes=(Index(('message_id',)), Index(('seq',))))
ASKS = Table('a2a_asks', place='project', key=('task_id',), columns=(
    Column('task_id', required=True), Column('context_id', required=True), Column('message_id', required=True),
    Column('text', required=True), Column('title'), Column('kind'), Column('caller'), Column('candidates', 'json'),
    Column('work_id'), Column('answer_id'), Column('cancelled'), Column('created', required=True),
    Column('seq', 'int', required=True)),
    indexes=(Index(('message_id',)), Index(('answer_id',)), Index(('context_id',)), Index(('seq',))))
PUSH = Table('a2a_push', place='project', key=('work_id', 'config_id'), columns=(
    Column('work_id', required=True), Column('config_id', required=True), Column('url', required=True),
    Column('token'), Column('scheme'), Column('credentials'), Column('owner'), Column('created', required=True)))
TABLES = Tables(version=2, tables=(TASKS, ASKS, PUSH), compatible_from=1)  # 2 only adds a2a_asks


@dataclass(frozen=True)
class Sent:
    """A ticket a message opened: its work id, the message's id, the Address of its contextId and who sent it."""
    work_id: str
    message_id: str
    context_id: str
    caller: str | None
    created: str


@dataclass(frozen=True)
class Ask:
    """A message that named no Address: the task Metaform gave it, the work it says and the Addresses offered, and
    once the client chose one, the ticket opened there."""
    task_id: str
    context_id: str
    message_id: str
    text: str
    title: str | None = None
    kind: str | None = None
    caller: str | None = None
    candidates: list[dict[str, str]] = field(default_factory=list[dict[str, str]])
    work_id: str | None = None
    cancelled: str | None = None
    created: str = ''


@dataclass(frozen=True)
class Push:
    """One push notification configuration on a task: where to call and the credentials to present there."""
    work_id: str
    config_id: str
    url: str
    token: str | None
    scheme: str | None
    credentials: str | None
    owner: str | None


def _own(project: str) -> Store:
    return Store(project, module='mcp')


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _sent(row: Any) -> Sent:
    return Sent(str(row['work_id']), str(row['message_id']), str(row['context_id']), row['caller'],
                str(row['created']))


def _ask(row: Any) -> Ask:
    candidates: Any = row['candidates']
    return Ask(str(row['task_id']), str(row['context_id']), str(row['message_id']), str(row['text']), row['title'],
               row['kind'], row['caller'], cast(list[dict[str, str]], candidates) if isinstance(candidates, list)
               else [], row['work_id'], row['cancelled'], str(row['created']))


def _push(row: Any) -> Push:
    return Push(str(row['work_id']), str(row['config_id']), str(row['url']), row['token'], row['scheme'],
                row['credentials'], row['owner'])


def record(project: str, work_id: str, message_id: str, context_id: str, caller: str | None) -> Sent:
    with _own(project).tables() as tx:
        row = tx.insert('a2a_tasks', {'work_id': work_id, 'message_id': message_id, 'context_id': context_id,
                                      'caller': caller, 'created': _now(), 'seq': time.time_ns()})
    return _sent(row)


def by_message(project: str, message_id: str) -> str | None:
    """The task a message with this id already made, so a retried send makes no second one: the ticket it opened,
    the question it was asked, or the question it answered."""
    with _own(project).tables(write=False) as tx:
        opened = tx.rows('a2a_tasks', {'message_id': message_id}, by=('message_id',), limit=1).results
        if opened:
            return str(opened[0]['work_id'])
        for column in ('message_id', 'answer_id'):
            asked = tx.rows('a2a_asks', {column: message_id}, by=(column,), limit=1).results
            if asked:
                return str(asked[0]['task_id'])
    return None


def sent(project: str, work_id: str) -> Sent | None:
    with _own(project).tables(write=False) as tx:
        row = tx.get('a2a_tasks', {'work_id': work_id})
    return None if row is None else _sent(row)


def every_sent(project: str) -> dict[str, Sent]:
    """Every ticket a message opened in the project, by work id, read at once for a listing."""
    with _own(project).tables(write=False) as tx:
        return {str(row['work_id']): _sent(row) for row in tx.rows('a2a_tasks', limit=0).results}


def ask(project: str, asked: Ask) -> Ask:
    with _own(project).tables() as tx:
        row = tx.insert('a2a_asks', {
            'task_id': asked.task_id, 'context_id': asked.context_id, 'message_id': asked.message_id,
            'text': asked.text, 'title': asked.title, 'kind': asked.kind, 'caller': asked.caller,
            'candidates': asked.candidates, 'created': _now(), 'seq': time.time_ns()})
    return _ask(row)


def asked(project: str, task_id: str) -> Ask | None:
    with _own(project).tables(write=False) as tx:
        row = tx.get('a2a_asks', {'task_id': task_id})
    return None if row is None else _ask(row)


def asks(project: str, context_id: str | None = None) -> list[Ask]:
    """The questions asked in the project, or in one context Metaform gave, oldest first."""
    with _own(project).tables(write=False) as tx:
        found = tx.rows('a2a_asks', {'context_id': context_id} if context_id else None, limit=0).results
    return [_ask(row) for row in sorted(found, key=lambda row: int(row['seq']))]


def opened(project: str, task_id: str, work_id: str, answer_id: str | None) -> None:
    """The client chose an Address for a question and its ticket is open: the task reads as that ticket now."""
    with _own(project).tables() as tx:
        tx.update('a2a_asks', {'task_id': task_id}, {'work_id': work_id, 'answer_id': answer_id})


def withdrawn(project: str, task_id: str) -> None:
    """The client cancelled a question before choosing an Address: no ticket is opened for it."""
    with _own(project).tables() as tx:
        tx.update('a2a_asks', {'task_id': task_id}, {'cancelled': _now()})


def set_push(project: str, push: Push) -> Push:
    """Add a configuration, or replace the one with the same id on the task."""
    row = {'url': push.url, 'token': push.token, 'scheme': push.scheme, 'credentials': push.credentials,
           'owner': push.owner}
    key = {'work_id': push.work_id, 'config_id': push.config_id}
    with _own(project).tables() as tx:
        if tx.update('a2a_push', key, row) is None:
            tx.insert('a2a_push', {**key, **row, 'created': _now()})
    return push


def pushes(project: str, work_id: str | None = None) -> list[Push]:
    """The configurations on one task, or on every task of the project."""
    with _own(project).tables(write=False) as tx:
        found = tx.rows('a2a_push', {'work_id': work_id} if work_id else None, limit=0).results
    return [_push(row) for row in found]


def delete_push(project: str, work_id: str, config_id: str | None = None) -> int:
    """Delete one configuration, or every one on the task; deleting what is not there deletes nothing."""
    with _own(project).tables() as tx:
        return tx.delete('a2a_push', {'work_id': work_id, **({'config_id': config_id} if config_id else {})})
