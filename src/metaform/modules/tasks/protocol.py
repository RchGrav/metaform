"""Worktree rounds over ordinary project tickets: the unified worksheet a pair registers, their picks and scores at the
close, and event-driven rendezvous between the agents online."""
from __future__ import annotations

import functools
import os
import uuid
from collections.abc import Callable
from importlib import resources
from typing import Any, cast

from metaform import prompt_files
from metaform.data import Node, StoreError
from metaform.module import Context, Stop, context

from . import project_tickets, worktrees
from .board import CATEGORIES, Board


def board(ctx: Context) -> Board:
    return Board(ctx.require_store().project_id)


def actor(ctx: Context, supplied: Any = None) -> str:
    return str(ctx.identity.get('METAFORM_TASK') or os.environ.get('METAFORM_TASK') or supplied or '')


def agent_id(ctx: Context, given: Any) -> str:
    """An agent by its task id, or by the name the board shows for it: agents sign with their names, so a name given
    where an id is taken means the agent online with that name."""
    text = str(given or '')
    if not text:
        return text
    data = board(ctx)
    if data.worker(text) is not None:
        return text
    named = [str(worker['agent_id']) for worker in data.workers() if worker.get('name') == text]
    return named[0] if len(named) == 1 else text


def changed(ctx: Context, agents: list[str] | None = None, worktree: str | None = None,
            tickets: list[str] | None = None, *, wake: bool = False) -> None:
    ids = [agent for agent in agents or [] if agent]
    ctx.publish('map.changed', {'project': ctx.project, 'tables': ['tasks.board'], 'kinds': ['tasks.board'],
                'work_ids': list(tickets or []), 'worktree': worktree, 'agent_ids': ids, 'wake': wake})


def view(ctx: Context) -> dict[str, Any]:
    """The board an agent reads: every other agent online with its score and work, and the worktrees open on the
    project, claimed or free."""
    return {'agents': board(ctx).view(actor(ctx) or None), 'worktrees': open_worktrees(ctx)}


def open_worktrees(ctx: Context) -> list[dict[str, Any]]:
    """Every worktree with an open ticket: its tickets, and when claimed its holder, partner and progress."""
    stored = project_tickets.held(ctx)
    rows: list[tuple[str, str, bool, bool]]  # each open ticket's id, title, whether taken and whether held
    if stored is not None:
        rows = [(ident, str(one.get('title') or ''), bool(one.get('taken_by')), bool(one.get('held')))
                for ident, one in project_tickets.records(stored).items() if not one.get('done') and one.get('task')]
    else:
        store = ctx.require_store()
        records = [record for record in store.work(open=True, limit=0).results if record.task]
        titles: dict[str, Any] = store.numbers_of('work', [record.id for record in records]) if records else {}
        rows = [(record.id, titles.get(record.id, ('', None, None))[1] or '', record.taken is not None,
                 bool(record.held)) for record in records]
    ids = [row[0] for row in rows]
    names = worktrees.of(ctx, ids)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for ident, title, taken, held in rows:
        grouped.setdefault(names[ident], []).append({'ticket': ident, 'title': title, 'taken': taken, 'held': held})
    rounds = {round_['worktree']: round_ for round_ in board(ctx).rounds() if not round_['completed']}
    named = worktrees.agents_of(ctx, ids)
    listed: list[dict[str, Any]] = []
    for name, tickets in grouped.items():
        round_ = rounds.get(name)
        agents = list(dict.fromkeys(one for ticket in tickets for one in named[ticket['ticket']]))
        listed.append({'worktree': name, 'tickets': tickets, 'agents': agents,
                       'phrase': round_['phrase'] if round_ else tickets[0]['title'],
                       'holder': round_['holder'] if round_ else None,
                       'partner': round_.get('partner') if round_ else None,
                       **(Board.progress(round_) if round_ else {'checked': 0, 'total': 0})})
    return listed


def status(ctx: Context) -> dict[str, Any]:
    ident = str(ctx.nouns.get('agent_id') or actor(ctx))
    if not ident:
        raise Stop('Name the agent whose status is being updated.', 'metaform tasks board')
    fields = {key: ctx.nouns[key] for key in ('state', 'nodes', 'current', 'next', 'waiting_for') if key in ctx.nouns}
    try:
        board(ctx).patch(ident, fields)
    except KeyError:
        raise Stop(f'No agent {ident} is online.', 'metaform tasks board') from None
    except ValueError as error:
        raise Stop(str(error), 'metaform tasks status') from None
    changed(ctx, [ident])
    return {'agent_id': ident, 'updated': list(fields)}


def ticket(ctx: Context) -> dict[str, Any]:
    """A ticket for a pair, on its node, in the worktree the composer names or one of its own. The ticket may name
    the agents who work it, the first named claiming it and the next its partner; each one online is told. For a
    project held in the project store the ticket is a record of its tickets overlay at the element."""
    stored = project_tickets.held(ctx)
    name = str(ctx.nouns['node'])
    worktree = worktrees.named(str(ctx.nouns['worktree'])) if ctx.nouns.get('worktree') else None
    given: Any = ctx.nouns.get('agents') or []
    if not isinstance(given, list) or any(not isinstance(one, str) or not one.strip() for one in cast(list[Any], given)):
        raise Stop('agents is a list of agent names.', 'metaform tasks board')
    agents = list(dict.fromkeys(one.strip() for one in cast(list[str], given)))
    if stored is not None:
        ident = project_tickets.add(stored, name, str(ctx.nouns['summary']), str(ctx.nouns['text']))
    else:
        target = Node('join', name[5:]) if name.startswith('join:') else Node('element', name)
        ident = ctx.require_store().add_work(target, None, task=str(ctx.nouns['text']),
                                             title=str(ctx.nouns['summary'])).id
    if worktree is not None or agents:
        worktrees.assign(ctx, ident, worktree, agents)
    if worktree is not None:
        round_ = board(ctx).add_ticket(worktree, ident)
        if round_ is not None:  # written into a claimed worktree: the pair's, taken and counted with the rest
            if stored is not None:
                project_tickets.take(project_tickets.found(stored, project_tickets.records(stored), ident),
                                     str(round_['holder']))
            else:
                ctx.require_store().take_work(ident, by=str(round_['holder']))
            _sync_progress(ctx, round_)
            changed(ctx, [str(round_['holder']), str(round_.get('partner') or '')], worktree, round_['tickets'])
    told = _tell_named(ctx, ident, str(ctx.nouns['summary']), agents)
    return {'ticket': ident, 'summary': ctx.nouns['summary'], 'node': name, 'worktree': worktree or ident,
            'agents': agents, 'told': told}


def _tell_named(ctx: Context, ticket_id: str, summary: str, agents: list[str]) -> list[str]:
    """The agents a ticket names, each online one told of it; their ids."""
    if not agents:
        return []
    data = board(ctx)
    online = {str(worker['name']): str(worker['agent_id']) for worker in data.workers()}
    told = [online[name] for name in agents if name in online]
    for name in agents:
        if name in online:
            others = ', '.join(one for one in agents if one != name) or 'nobody else'
            data.enqueue(online[name], f'named:{ticket_id}:{online[name]}',
                         worded('ticket_named', ticket=ticket_id, summary=summary, others=others))
    if told:
        changed(ctx, told, None, [ticket_id], wake=True)
    return told


def tickets_of(ctx: Context, name: str) -> list[dict[str, Any]]:
    """The open tickets in a worktree: those the composer put there, and the ticket named for itself."""
    listed: list[dict[str, Any]] = []
    own = worktrees.of(ctx, [name])[name] == name  # a ticket put in another worktree is not claimable by its own id
    idents: list[str] = list(dict.fromkeys([*worktrees.tickets(ctx, name), *([name] if own else [])]))
    stored = project_tickets.held(ctx)
    if stored is not None:
        found = project_tickets.records(stored)
        return [{'ticket': ident, 'taken': bool(one.get('taken_by')), 'taken_by': one.get('taken_by') or None,
                 'title': str(one.get('title') or '')}
                for ident in idents if (one := found.get(ident)) is not None and not one.get('done') and one.get('task')]
    store = ctx.require_store()
    for ident in idents:
        try:
            record = store.ticket(ident).work
        except StoreError:
            continue
        if record.done is None and record.task:
            listed.append({'ticket': ident, 'taken': record.taken is not None, 'taken_by': record.taken_by})
    titles: dict[str, Any] = store.numbers_of('work', [one['ticket'] for one in listed]) if listed else {}
    for one in listed:
        one['title'] = titles.get(one['ticket'], ('', None, None))[1] or ''
    return listed


def worksheet(ctx: Context) -> dict[str, Any]:
    """Read a worktree's worksheet, or register it: the holder's claim of the worktree, which takes every open ticket
    in it and sets the unified checklist, each item for a ticket, an agent and nodes when it says so. The git worktree
    is made only when the composer put the tickets in one; a ticket claimed by its own id is worked in the project
    folder."""
    name = worktrees.named(str(ctx.nouns['worktree']))
    data = board(ctx)
    if 'items' not in ctx.nouns:
        return data.round(name) or {'worktree': name, 'items': [],
                                    'tickets': [one['ticket'] for one in tickets_of(ctx, name)]}
    holder = str(ctx.nouns.get('holder') or actor(ctx))
    if not holder:
        raise Stop('Give the worksheet holder identifier.', 'metaform tasks board')
    tickets = tickets_of(ctx, name)
    if not tickets:
        raise Stop(f'No open ticket is in worktree {name}.', 'metaform tasks board')
    items = cast(list[str | dict[str, Any]], ctx.nouns['items'])
    if not items:
        raise Stop('A worksheet needs at least one item.', 'metaform tasks worksheet')
    for item in items:  # an item's agent by name or id, as the board shows it
        if isinstance(item, dict) and item.get('agent'):
            item['agent'] = agent_id(ctx, item['agent'])
    nodes = cast(list[str], ctx.nouns.get('nodes') or [])
    held = data.round(name)
    if held and not held['completed'] and holder != str(held['holder']):
        raise Stop(f'{name} is held by {held["holder"]}: pair with them (tasks pair) or message them; only the holder '
                   'registers its worksheet again.', 'metaform tasks board')
    # Each ticket's own owner, not only the worksheet's holder: a ticket another agent claimed directly is theirs, and
    # a worksheet over it is refused before anything is claimed or saved (review of 2026-11-18, F6).
    # The project store's claim is exclusive; the old store's take is shared participation, so it is checked there only.
    by = actor(ctx) or holder
    stored = project_tickets.held(ctx)
    owned = [one for one in tickets if one.get('taken_by') and one['taken_by'] not in (by, holder)] \
        if stored is not None else []
    if owned:
        said = ', '.join(f"{one['ticket']} is taken by {one['taken_by']}" for one in owned)
        raise Stop(f'{said}: a worksheet '
                   'takes only tickets that are free or already yours. Pair with the holder (tasks pair) or message '
                   'them.', 'metaform tasks board')
    # Before the round in the project store, whose claims can be given back if the round is not made; the old store's
    # take cannot be undone, so its tickets are taken after the round, as before.
    claimed = _claim(ctx, stored, tickets, by, []) if stored is not None else []
    try:
        # before the round, so a git refusal leaves nothing claimed; none for a ticket worked in the project folder
        made = worktrees.create(ctx.folder, name) if worktrees.assigned(ctx, name) else None
        result = data.set_round(name, str(tickets[0]['title'] or ''), holder, items, nodes,
                                agent_id(ctx, ctx.nouns.get('partner')) or None,
                                [one['ticket'] for one in tickets])
    except ValueError as error:
        _release(stored, claimed, by)
        raise Stop(str(error), 'metaform tasks worksheet') from None
    except BaseException:
        _release(stored, claimed, by)
        raise
    passed: list[dict[str, str]] = []  # an old-store ticket the worksheet could not take, with why
    if stored is None:
        _claim(ctx, None, tickets, by, passed)
    _sync_progress(ctx, result)
    changed(ctx, [holder], name, result['tickets'])
    if passed:
        result = {**result, 'not_taken': passed}
    if made is None:
        return {**result, 'folder': str(ctx.folder), 'branch': None}
    return {**result, 'folder': made['folder'], 'branch': made['branch'],
            **({'notice': made['notice']} if made.get('notice') else {})}


def _claim(ctx: Context, stored: str | None, tickets: list[dict[str, Any]], by: str,
           passed: list[dict[str, str]]) -> list[str]:
    """Claim each free ticket for `by`; the ids claimed. In the project store, `stored`, a claim is exclusive and at
    the revision read, and a refusal part way gives back the claims this call made and stops, so no ticket is left
    claimed for a worksheet that was not made. In the old store a take is shared participation, made after the round,
    and a ticket it cannot take is passed over, rather than failing a worksheet already made: one finished since it
    was listed silently, any other named in `passed` with why."""
    found = project_tickets.records(stored) if stored is not None else {}
    claimed: list[str] = []
    try:
        for one in tickets:
            if one['taken']:
                continue
            if stored is not None:
                project_tickets.take(project_tickets.found(stored, found, one['ticket']), by)
            else:
                try:
                    ctx.require_store().take_work(one['ticket'], by=by)
                except Exception as error:  # noqa: BLE001  after the round: said, never a failure of it
                    if not _done_since(ctx, str(one['ticket'])):  # one finished since it was listed: nothing to take
                        passed.append({'ticket': str(one['ticket']), 'why': str(error)})
                    continue
            claimed.append(str(one['ticket']))
    except BaseException:
        _release(stored, claimed, by)
        raise
    return claimed


def _done_since(ctx: Context, ticket: str) -> bool:
    """Whether an old-store ticket is done now."""
    try:
        return ctx.require_store().ticket(ticket).work.done is not None
    except Exception:  # noqa: BLE001  read after a take that failed, maybe for the same cause: not known done, and
        return False  # the take's own error is what not_taken says


def _release(stored: str | None, claimed: list[str], by: str) -> None:
    """Give back the claims a worksheet made when it was not made after all: each ticket still held by `by` is
    freed. Only the project store's tickets: the old store's take is a shared participation with nothing to undo."""
    if stored is None or not claimed:
        return
    found = project_tickets.records(stored)
    for ident in claimed:
        one = found.get(ident)
        if one is not None and one.get('taken_by') == by:
            project_tickets.change(one, {'taken_by': None}, exact=True)


def pair(ctx: Context) -> dict[str, Any]:
    name, partner = str(ctx.nouns['worktree']), agent_id(ctx, ctx.nouns['partner'])
    try:
        result = board(ctx).pair(name, partner)
    except KeyError as missing:
        raise Stop(f'No worksheet or agent {missing.args[0]}.', 'metaform tasks board') from None
    changed(ctx, [str(result['holder']), partner], name, result['tickets'])
    return result


def check(ctx: Context) -> dict[str, Any]:
    name = str(ctx.nouns['worktree'])
    try:
        result = board(ctx).check(name, str(ctx.nouns['item']), bool(ctx.nouns.get('done', True)))
    except KeyError as missing:
        raise Stop(f'No worksheet or item {missing.args[0]}.', 'metaform tasks worksheet') from None
    _sync_progress(ctx, result)
    completed = _close(ctx, name)
    changed(ctx, [str(result['holder']), str(result.get('partner') or '')], name, result['tickets'])
    return {**result, 'completed': completed}


def rate(ctx: Context) -> dict[str, Any]:
    """A reviewer's pick at the close of a worktree: the agent it rates, with stars of five in each category and the
    bonus, or alone=true when there was no one to rate. Each participant picks before the worktree's tickets close."""
    name = str(ctx.nouns['worktree'])
    data = board(ctx)
    current = data.round(name)
    if current is None:
        raise Stop(f'No worksheet for worktree {name}.', 'metaform tasks worksheet')
    reviewer = actor(ctx, ctx.nouns.get('reviewer'))
    if not reviewer:
        raise Stop('Identify the reviewer.', 'metaform tasks board')
    alone = bool(ctx.nouns.get('alone'))
    target = '' if alone else agent_id(ctx, ctx.nouns.get('target'))
    if not alone and not target:
        target = str((current.get('partner') if reviewer == current['holder'] else current['holder']) or '')
        if not target or target == reviewer:
            raise Stop('Name the agent you rate with target=<id>, or rate alone=true.', 'metaform tasks board')
    scores = cast(dict[str, Any], ctx.nouns.get('scores') or {})
    if not alone and not scores:
        raise Stop(f'Give stars 0 to 5 in each category, {", ".join(CATEGORIES)}, or rate alone=true.',
                   'metaform tasks rate')
    try:
        rating = data.rate(name, reviewer, target or None, scores, bonus=bool(ctx.nouns.get('bonus')), alone=alone)
    except ValueError as error:
        raise Stop(str(error), 'metaform tasks rate') from None
    completed = _close(ctx, name)
    changed(ctx, [reviewer, target], name, current['tickets'])
    return {'worktree': name, 'reviewer': reviewer, 'target': target or None, 'alone': alone,
            'points': rating['points'], 'recorded': True, 'completed': completed}


def _sync_progress(ctx: Context, round_: dict[str, Any]) -> None:
    """Each ticket's steps follow its items, its own and the shared; at N/N the worksheet is appended to each. In the
    project store they are the ticket's steps and steps_done, each changed only when its count moved."""
    items = cast(list[dict[str, Any]], round_['items'])
    stored = project_tickets.held(ctx)
    if stored is not None:
        found = project_tickets.records(stored)
        for ticket_id in cast(list[str], round_['tickets']):
            progress = Board.progress(round_, ticket=ticket_id)
            one = project_tickets.found(stored, found, ticket_id)
            if (one.get('steps'), one.get('steps_done')) != (progress['total'], progress['checked']):
                project_tickets.change(one, {'steps': progress['total'], 'steps_done': progress['checked']})
        if items and all(item.get('done') for item in items):
            _append(ctx, round_)
        return
    store = ctx.require_store()
    with store.atomic():
        for ticket_id in cast(list[str], round_['tickets']):
            progress = Board.progress(round_, ticket=ticket_id)
            store.worksheet_progress(ticket_id, progress['total'], progress['checked'])
        if items and all(item.get('done') for item in items):
            _append(ctx, round_)


def _append(ctx: Context, round_: dict[str, Any]) -> None:
    """The completed items appended to each ticket, its own and the shared, once; a note written by others stays."""
    name = str(round_['worktree'])
    marker = f'Completed worksheet ({name})'
    stored = project_tickets.held(ctx)
    found = project_tickets.records(stored) if stored is not None else {}
    items = cast(list[dict[str, Any]], round_['items'])
    for ticket_id in cast(list[str], round_['tickets']):
        one = project_tickets.found(stored, found, ticket_id) if stored is not None else None
        before_note = one.get('note') if one is not None else ctx.require_store().ticket(ticket_id).work.note
        note = str(before_note or '')
        text = marker + '\n' + '\n'.join('[x] ' + str(item['text']) for item in items
                                         if item.get('ticket') in (None, ticket_id))
        if marker in note:
            before, _, tail = note.partition(marker)
            _, separator, after = tail.partition('\n\n')
            note = before + text + (separator + after if separator else '')
        else:
            note = '\n\n'.join(part for part in (note, text) if part)
        if one is not None:
            if note != str(before_note or ''):
                project_tickets.change(one, {'note': note})
        else:
            ctx.require_store().edit_work(ticket_id, {'note': note})


def _close(ctx: Context, name: str) -> bool:
    """The worktree closes when every item is checked and every participant has rated or said alone: its tickets are
    done, and with Full Auto on a git worktree the composer asked for is merged into the checked-out branch and
    removed."""
    data = board(ctx)
    round_ = data.round(name)
    if round_ is None:
        return False
    if round_['completed']:
        return True
    items = cast(list[dict[str, Any]], round_['items'])
    holder, partner = str(round_['holder']), str(round_.get('partner') or '')
    participants = {one for one in (holder, partner) if one}
    if not items or not all(item.get('done') for item in items):
        return False
    if not participants <= {str(rating['reviewer']) for rating in data.ratings(name)}:
        return False
    tickets = cast(list[str], round_['tickets'])
    resolution, why = 'Completed the registered worksheet.', f'Every participant rated at the close of worktree {name}.'
    stored = project_tickets.held(ctx)
    if stored is not None:  # one command per ticket: the project store has no transaction across elements
        _append(ctx, round_)
        found = project_tickets.records(stored)
        for ticket_id in tickets:
            one = project_tickets.found(stored, found, ticket_id)
            if not one.get('done'):
                project_tickets.change(one, project_tickets.finished(one, resolution, why))
    else:
        store = ctx.require_store()
        with store.atomic():
            _append(ctx, round_)
            for ticket_id in tickets:
                if not store.ticket(ticket_id).work.done:
                    store.finish_work(ticket_id, resolution, why)
    data.complete_round(name)
    if ctx.setting('tasks_full_auto') and worktrees.assigned(ctx, name):
        landed = worktrees.land(ctx.folder, name, f'{round_["phrase"]}\n\nWorktree {name}: {", ".join(tickets)}.')
        if not landed['merged']:
            found = project_tickets.records(stored) if stored is not None else {}
            for ticket_id in tickets:
                if stored is not None:
                    one = project_tickets.found(stored, found, ticket_id)
                    project_tickets.change(one, {'note': f'{one.get("note") or ""}\n\nNot merged: {landed["why"]}'})
                    continue
                store = ctx.require_store()
                note = str(store.ticket(ticket_id).work.note or '')
                store.edit_work(ticket_id, {'note': note + f'\n\nNot merged: {landed["why"]}'})
    wake_ids: list[str] = []
    for available in participants:
        for waiter in data.waiters(available):
            waiting = str(waiter['agent_id'])
            data.patch(waiting, {'waiting_for': None})
            data.enqueue(waiting, f'partner:{name}:{waiting}', worded('partner_finished', assignment=name))
            wake_ids.append(waiting)
    if open_worktrees(ctx):
        for agent in participants:
            data.enqueue(agent, f'complete:{name}:{agent}', worded('assignment_closed', assignment=name))
            wake_ids.append(agent)
    if wake_ids:
        changed(ctx, wake_ids, name, tickets, wake=True)
    return True


def flush(ctx: Context, assignment: dict[str, Any]) -> None:
    """Queued messages reach an idle agent as a wake. A working agent reads them on its next tasks tool call instead
    (`inbox`), so a message never waits for the end of a long turn. A row is marked delivered after its wake, so a
    failure between the two sends it again: at least once, never lost."""
    from .runtime import transport
    data = board(ctx)
    ident = str(assignment['task_id'])
    worker = data.worker(ident)
    if worker is not None and worker.get('state') == 'working':
        return
    for message in data.pending(ident):
        transport(ctx).wake(ctx, assignment, message['key'], message['text'])
        data.delivered(message['key'])


def inbox(ctx: Context, result: dict[str, Any]) -> dict[str, Any]:
    """The caller's queued messages, carried on the result of any tasks tool it calls and marked delivered: an agent
    in the middle of a long turn hears its partner at its next tool call."""
    ident = actor(ctx)
    if not ident:
        return result
    data = board(ctx)
    pending = data.pending(ident)
    if not pending:
        return result
    for message in pending:
        data.delivered(message['key'])
    return {**result, 'messages': [message['text'] for message in pending]}


def with_inbox(handler: Callable[[Context], dict[str, Any]]) -> Callable[[Context], dict[str, Any]]:
    """A tasks verb whose result carries the caller's inbox."""
    @functools.wraps(handler)
    def run(ctx: Context) -> dict[str, Any]:
        return inbox(ctx, handler(ctx))
    return run


def reconcile(ctx: Context, assignment: dict[str, Any], observed: dict[str, Any]) -> None:
    if assignment['name'] != 'project_agent':
        return
    data = board(ctx)
    ident = str(assignment['task_id'])
    if observed['state'] in ('completed', 'failed', 'cancelled'):
        _released(ctx, ident)
        data.remove(ident)
        changed(ctx, [ident])
        return
    worker = data.worker(ident)
    if worker is None:
        worker = data.register(ident, str(observed.get('name') or 'agent-' + ident[:8]), str(assignment['work_id']),
                               str(observed.get('session_id') or ''))
    fields = {'state': 'idle' if observed.get('idle') else 'working'}
    for key in ('name', 'context', 'session_id'):
        if observed.get(key) is not None:
            fields[key] = observed[key]
    if any(worker.get(key) != value for key, value in fields.items()):
        data.patch(ident, fields)
        changed(ctx, [ident])
    flush(ctx, assignment)


def worded(name: str, **fills: str) -> str:
    """A message of this module's resources, `resources/<name>.txt`, sent as written there through the prompt store as
    the task files are, `prompt.tasks:<name>.txt`, with its {...} fills; no words of it are written here."""
    source = resources.files(cast(str, __package__)) / 'resources' / f'{name}.txt'
    bindings = {f'{{{key}}}': value for key, value in fills.items()}
    return str(prompt_files.resolve_text(f'prompt.tasks:{name}.txt', source.read_bytes().decode('utf-8'),
                                         **bindings)['text']).rstrip('\n')


def handoff(ctx: Context) -> dict[str, Any]:
    """A project agent's place given to a new one on the same agent, started with the caller's handoff as its input:
    the newcomer, a fresh context at 100, takes the caller's worktrees, partners and waits, and the caller's own task
    ends. Project agents stay running and hand off rather than shut down and come back, which wastes context."""
    from . import definition
    from .runtime import SERVICE
    leaving = actor(ctx, ctx.nouns.get('agent_id'))
    if not leaving:
        raise Stop('Name the agent handing off with agent_id=<id>, or call from its own task session.',
                   'metaform tasks board')
    row = SERVICE.assignment(ctx, leaving)
    if row is None:
        raise Stop(f'No assigned agent {leaving}.', 'metaform tasks board')
    if board(ctx).worker(leaving) is None:  # before the newcomer starts, so none starts with no place to take
        raise Stop(f'No agent {leaving} is online.', 'metaform tasks board')
    locator = cast(dict[str, Any], row.get('locator') or {})
    nouns: dict[str, Any] = {'name': 'project_agent', 'text': str(ctx.nouns['text']),
                             'agent': locator.get('agent') or row.get('agent'), 'folder': row['cwd']}
    if row['payload'].get('node'):
        nouns['node'] = row['payload']['node']
    own = context('tasks', ctx.folder, project=ctx.project, nouns=nouns, surface=ctx.surface,
                  session=ctx.session, identity=ctx.identity)
    started = SERVICE.assign(own, 'project_agent', definition(own)['component'])
    arriving = str(started['task_id'])
    if started['state'] == 'completed':  # the replacement did not start: the caller keeps its place
        raise Stop('The replacement agent did not start, so your place stays yours; try again.', 'metaform tasks board')
    try:
        moved = board(ctx).handoff(leaving, arriving)
    except KeyError as missing:
        raise Stop(f'No agent {missing.args[0]} is online.', 'metaform tasks board') from None
    changed(ctx, [leaving, arriving], wake=True)
    try:
        SERVICE.finish(ctx, leaving, f'Handed off to {arriving}.')
        ended = True
    except (OSError, Stop):  # the places moved all the same; the caller's session ends on its own
        ended = False
    return {**moved, 'agent': started['agent'], 'state': started['state'], 'ended': ended}


def _released(ctx: Context, ident: str) -> None:
    """An agent gone offline mid-round has its pick recorded as alone, so the worktree can still close."""
    data = board(ctx)
    for round_ in data.rounds():
        name = str(round_['worktree'])
        if round_['completed'] or ident not in (round_['holder'], round_.get('partner')):
            continue
        if ident not in {str(rating['reviewer']) for rating in data.ratings(name)}:
            data.rate(name, ident, None, {}, alone=True)
        _close(ctx, name)


def event(ctx: Context, payload: dict[str, Any]) -> None:
    from .runtime import SERVICE
    if payload.get('project') != ctx.project or not payload.get('wake') or 'tasks.board' not in payload.get('tables', []):
        return
    for ident in payload.get('agent_ids', []):
        if ident and (assignment := SERVICE.assignment(ctx, str(ident))) is not None:
            try:
                flush(ctx, assignment)
            except (OSError, Stop):
                pass  # the durable outbox remains available after reconnect/startup


def message(ctx: Context) -> dict[str, Any]:
    """A message queued for an agent, delivered to its session. An ended agent is called back for it: its context is
    resumed in place, and the message reaches it once its session is on the board again."""
    from .runtime import SERVICE, TERMINAL
    ident = agent_id(ctx, ctx.nouns['agent_id'])
    assignment = SERVICE.assignment(ctx, ident)
    if assignment is None:
        raise Stop(f'No assigned agent {ident}.', 'metaform tasks board')
    sender = actor(ctx) or ctx.surface
    key = uuid.uuid4().hex
    board(ctx).log_message(key, sender, ident, str(ctx.nouns['text']))  # the run's log of messages
    board(ctx).enqueue(ident, key, worded('message_from', sender=sender, text=str(ctx.nouns['text'])))
    called = SERVICE.resume(ctx, ident) if assignment['state'] in TERMINAL else None
    changed(ctx, [ident], wake=True)
    return {'message': key, 'to': ident, 'from': sender, 'queued': True,
            **({'called_back': called} if called is not None else {})}
