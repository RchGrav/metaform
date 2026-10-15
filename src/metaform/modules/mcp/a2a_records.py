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
# What Metaform sends out, MCP-040 to MCP-043: the Agent Card each peer served when it was last read, and one row per
# exchange, a message sent to a peer about an Address and the task the peer opened for it.
PEERS = Table('a2a_peers', place='project', key=('name',), columns=(
    Column('name', required=True), Column('url', required=True), Column('card', 'json', required=True),
    Column('read', required=True)))
EXCHANGES = Table('a2a_exchanges', place='project', key=('exchange_id',), columns=(
    Column('exchange_id', required=True), Column('peer', required=True), Column('peer_task_id'),
    Column('address', required=True), Column('sender'), Column('work_id'), Column('state', required=True),
    Column('said'), Column('text', required=True), Column('seen', 'json'), Column('created', required=True),
    Column('updated', required=True), Column('seq', 'int', required=True), Column('asked'), Column('sending')),
    indexes=(Index(('peer', 'peer_task_id')), Index(('address',)), Index(('state',)), Index(('seq',))))
# 2 only adds a2a_asks, 3 only a2a_peers and a2a_exchanges, 4 only a2a_exchanges' `asked`, the open question at the
# Address whose answer goes back to the peer, 5 only its `sending`, when a sender claimed that answer; each may be
# empty, so every earlier version still reads the rest.
TABLES = Tables(version=5,tables=(TASKS, ASKS, PUSH, PEERS, EXCHANGES), compatible_from=1)


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


# ---------------------------------------------------------------------------------------------------- outbound

@dataclass(frozen=True)
class Exchange:
    """One message sent to a peer about an Address, MCP-043: the peer and the task it opened, the Address and the
    ticket it belongs to, the agent instance that sent it, the task's state in the status vocabulary of work with the
    peer's last word on it, what of the task was already written at the Address, the open question there whose
    answer goes back to the peer, `asked`, a message id of the map, and when a sender claimed that answer, `sending`."""
    exchange_id: str
    peer: str
    address: str
    text: str
    state: str = 'submitted'
    peer_task_id: str | None = None
    sender: str | None = None
    work_id: str | None = None
    said: str | None = None
    seen: list[str] = field(default_factory=list[str])
    created: str = ''
    updated: str = ''
    asked: str | None = None
    sending: str | None = None


def _exchange(row: Any) -> Exchange:
    seen: Any = row['seen']
    return Exchange(str(row['exchange_id']), str(row['peer']), str(row['address']), str(row['text']),
                    str(row['state']), row['peer_task_id'], row['sender'], row['work_id'], row['said'],
                    [str(one) for one in cast(list[Any], seen)] if isinstance(seen, list) else [],
                    str(row['created']), str(row['updated']), row['asked'], row['sending'])


def keep_card(project: str, name: str, url: str, card: dict[str, Any]) -> None:
    """The Agent Card a peer served, kept until a send fails with a version or interface error, MCP-040."""
    row = {'url': url, 'card': card, 'read': _now()}
    with _own(project).tables() as tx:
        if tx.update('a2a_peers', {'name': name}, row) is None:
            tx.insert('a2a_peers', {'name': name, **row})


def kept_card(project: str, name: str, url: str) -> dict[str, Any] | None:
    """The card kept for a peer, while the person still names it at the same URL."""
    with _own(project).tables(write=False) as tx:
        row = tx.get('a2a_peers', {'name': name})
    card: Any = row['card'] if row is not None and row['url'] == url else None
    return cast(dict[str, Any], card) if isinstance(card, dict) else None


def send(project: str, made: Exchange) -> Exchange:
    """Keep an exchange before its message leaves, so a reply after any restart finds it."""
    with _own(project).tables() as tx:
        stamp = _now()
        row = tx.insert('a2a_exchanges', {
            'exchange_id': made.exchange_id, 'peer': made.peer, 'peer_task_id': made.peer_task_id,
            'address': made.address, 'sender': made.sender, 'work_id': made.work_id, 'state': made.state,
            'said': made.said, 'text': made.text, 'seen': [], 'created': stamp, 'updated': stamp,
            'seq': time.time_ns()})
    return _exchange(row)


def exchange(project: str, exchange_id: str) -> Exchange | None:
    with _own(project).tables(write=False) as tx:
        row = tx.get('a2a_exchanges', {'exchange_id': exchange_id})
    return None if row is None else _exchange(row)


def exchanges(project: str, address: str | None = None, open_only: bool = False) -> list[Exchange]:
    """The project's exchanges, or those about one Address, newest first; with `open_only`, those whose task has
    not ended."""
    with _own(project).tables(write=False) as tx:
        found = tx.rows('a2a_exchanges', {'address': address} if address else None, limit=0).results
    made = [_exchange(row) for row in sorted(found, key=lambda row: -int(row['seq']))]
    return [one for one in made if one.state not in ('completed', 'failed', 'cancelled')] if open_only else made


def moved(project: str, exchange_id: str, *, state: str | None = None, said: str | None = None,
          peer_task_id: str | None = None, claims: tuple[str, ...] = ()) -> tuple[Exchange | None, bool, list[str]]:
    """Record what a peer told of an exchange's task in one transaction: its state and last word when they changed,
    and each of `claims`, the keys of the artifacts and questions not yet written at the Address. Returns the
    exchange, whether its state changed, and the claims this call took, so two followers of one task never write the
    same item twice."""
    with _own(project).tables() as tx:
        row = tx.get('a2a_exchanges', {'exchange_id': exchange_id})
        if row is None:
            return None, False, []
        before = _exchange(row)
        taken = [key for key in dict.fromkeys(claims) if key not in before.seen]
        change: dict[str, Any] = {}
        if state and state != before.state:
            change['state'] = state
        if said is not None and said != before.said:
            change['said'] = said
        if peer_task_id and peer_task_id != before.peer_task_id:
            change['peer_task_id'] = peer_task_id
        if taken:
            change['seen'] = [*before.seen, *taken]
        if not change:
            return before, False, []
        change['updated'] = _now()
        after = tx.update('a2a_exchanges', {'exchange_id': exchange_id}, change)
    return _exchange(after) if after is not None else before, 'state' in change, taken


def asking(project: str, exchange_id: str, was: str | None, now: str | None) -> bool:
    """Set the exchange's open question from `was` to `now` in one transaction, only while it is still `was`, so a
    question the peer asks meanwhile is never overwritten; any claim on sending the old one's answer goes with it.
    Returns whether it was set."""
    with _own(project).tables() as tx:
        row = tx.get('a2a_exchanges', {'exchange_id': exchange_id})
        if row is None or row['asked'] != was:
            return False
        tx.update('a2a_exchanges', {'exchange_id': exchange_id}, {'asked': now, 'sending': None, 'updated': _now()})
    return True


def sending(project: str, exchange_id: str, asked: str, stale: float) -> bool:
    """Claim sending the answer to the open question `asked` in one transaction, so of two that read it only one sends
    it. A claim older than `stale` seconds is free to take again: its sender died before the peer took the answer.
    Returns whether this call took it."""
    with _own(project).tables() as tx:
        row = tx.get('a2a_exchanges', {'exchange_id': exchange_id})
        free = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - stale))
        if row is None or row['asked'] != asked or (row['sending'] and row['sending'] >= free):
            return False
        tx.update('a2a_exchanges', {'exchange_id': exchange_id}, {'sending': _now(), 'updated': _now()})
    return True


def unsent(project: str, exchange_id: str, asked: str) -> None:
    """Let go of the claim on sending the answer to `asked`: the peer was not reached, and the next caller sends it."""
    with _own(project).tables() as tx:
        row = tx.get('a2a_exchanges', {'exchange_id': exchange_id})
        if row is not None and row['asked'] == asked:
            tx.update('a2a_exchanges', {'exchange_id': exchange_id}, {'sending': None, 'updated': _now()})
