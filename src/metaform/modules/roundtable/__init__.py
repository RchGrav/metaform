"""roundtable: a discussion among models at an Address, where only real contributions are kept, BASE-066.

The person or their head agent opens a table at an Address with an opening message and its seats; the seats speak
in turn, round robin, in a fixed order, each at most 512 characters, and a submission enters the discussion only
when Jev finds it new, valuable, relevant and worth keeping, each at roundtable_keep or above. A vetoed submission
is shown to every seat as its verdict, the four questions with their nouls and the link to its text. The table ends
after a full round that kept nothing, or when its chair ends it, and one model writes the report into
docs/roundtables/.

The parts: `store` the tables, `seats` who sits and a model's turn through OpenRouter, `judge` Jev's four nouls,
`render` every text a seat, the head agent, the review and the report read, `chair` who may chair and how turns
reach the head agent, `runner` the detached process that runs a table.
"""
from __future__ import annotations

import time
from typing import Any, cast

from metaform import settings
from metaform.module import Context, Module, Noun, Resource, Stop, Verb

from . import chair, render, runner, seats, store
from .render import LIMIT, said

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a table runs a process of its own and calls models; a sandboxed agent sits at one as a seat

WATCH = 8.0  # seconds the person counts as watching after the page's last renewal
WAIT_MOST = 600  # seconds an agent seat may wait for its turn in one call

settings.number('roundtable_keep', 83, min=0, max=100, person_only=True,
                help='The percentage each of Jev\'s four nouls must reach for a submission to enter the discussion.')
settings.number('roundtable_pause', 5, min=0, max=60, person_only=True,
                help='Seconds after each turn, while the person watches the table, to hold, comment, continue or end.')
settings.number('roundtable_agent_wait', 300, min=10, max=3600, person_only=True,
                help='Seconds an agent seat has to submit on its turn before the turn passes with no submission.')
settings.text('roundtable_reporter', 'anthropic/claude-opus-5.5', person_only=True,
              help='The OpenRouter model that writes the report when a table ends.')


def number_of(ctx: Context) -> int:
    return int(ctx.nouns['discussion'])


def text_of(ctx: Context, noun: str = 'text') -> str:
    given: Any = ctx.nouns.get(noun) or []
    if isinstance(given, (list, tuple)):
        return ' '.join(str(word) for word in cast(list[Any], given)).strip()
    return str(given).strip()


def open_table(ctx: Context) -> dict[str, Any]:
    """Open a table at an Address and start its runner; the caller chairs it."""
    who = chair.caller(ctx, 'open a roundtable')
    held = store.own(ctx.require_store())
    address = str(ctx.nouns['address'])
    if ctx.require_store().element(address) is None:
        raise Stop(f'No element {address} in the map.', f'metaform map where {address}')
    opening = text_of(ctx, 'opening')
    if not opening:
        raise Stop('A table opens with its opening message.', f'metaform roundtable open {address} -- "<opening>"')
    chosen = seats.chosen(ctx.nouns.get('seats'))
    if seats.missing_key(chosen):
        raise Stop(f'{seats.KEY} is not set, and a model seat is called through OpenRouter.',
                   f'set {seats.KEY} in the environment Metaform runs in')
    subject = render.slug(str(ctx.nouns.get('subject') or opening))
    number = store.opened(held, {'address': address, 'subject': subject, 'opening': opening, 'chair': who['chair'],
                                 'chair_work': who.get('work'), 'chair_session': who.get('session')}, chosen)
    pid = runner.spawn(ctx, number)
    return {'discussion': number, 'address': address, 'subject': subject, 'chair': who['chair'],
            'seats': [seat['id'] for seat in chosen], 'runner': pid, 'privacy': said('privacy'),
            'next': ctx.calls(f'metaform roundtable status {number}')}


def open_one(ctx: Context) -> dict[str, Any]:
    """The table, refused once it has ended."""
    found = store.discussion(ctx.require_store(), number_of(ctx))
    if found['state'] == 'ended':
        raise Stop(f'Roundtable {found["number"]} has ended.', f'metaform roundtable status {found["number"]}')
    return found


def comment(ctx: Context) -> dict[str, Any]:
    """A comment of the chair's, entered inline at the next gap between turns, unjudged and with no limit."""
    who = chair.caller(ctx, 'comment at a roundtable')
    found = open_one(ctx)
    text = text_of(ctx)
    if not text:
        raise Stop('A comment says something.', f'metaform roundtable comment {found["number"]} -- "<comment>"')
    store.wait_comment(ctx.require_store(), found['number'], 'person' if who['chair'] == 'person' else 'head', text)
    runner.spawn(ctx, found['number'])
    return {'discussion': found['number'], 'comment': 'waiting for the next gap between turns'}


def hold(ctx: Context) -> dict[str, Any]:
    """Stop the table after the turn in flight, until it is continued."""
    chair.caller(ctx, 'hold a roundtable')
    found = open_one(ctx)
    if found['state'] == 'running':
        found = store.change(ctx.require_store(), found['number'], state='held', reason=said('held_by_chair'))
    return status_of(ctx, found)


def resume(ctx: Context) -> dict[str, Any]:
    """Go on: a held table runs again, judging first a submission Jev left unjudged; in a pause, the next turn
    starts now."""
    chair.caller(ctx, 'continue a roundtable')
    found = open_one(ctx)
    changes: dict[str, Any] = {'go': True}
    if found['state'] == 'held':
        changes.update(state='running', reason=None)
    found = store.change(ctx.require_store(), found['number'], **changes)
    runner.spawn(ctx, found['number'])
    return status_of(ctx, found)


def end(ctx: Context) -> dict[str, Any]:
    """End the table: its report is written; on an ended table whose report failed, it is asked for again."""
    chair.caller(ctx, 'end a roundtable')
    number = number_of(ctx)
    found = store.discussion(ctx.require_store(), number)
    if found['state'] == 'ended' and found['report']:
        return status_of(ctx, found)
    reason = found['reason'] if found['state'] == 'ended' else said('ended_by_chair')
    found = store.change(ctx.require_store(), number, state='ending', reason=reason)
    runner.spawn(ctx, number)
    return status_of(ctx, found)


def watch(ctx: Context) -> dict[str, Any]:
    """The person is watching the table, for a few seconds more: the page renews it while the table is open on it,
    and while it holds, each turn is followed by roundtable_pause seconds for the person's controls."""
    chair.person(ctx, 'watch a roundtable')
    found = store.change(ctx.require_store(), number_of(ctx), watched=time.time() + WATCH)
    return {'discussion': found['number'], 'watched_until': found['watched'], 'state': found['state']}


def status_of(ctx: Context, found: dict[str, Any]) -> dict[str, Any]:
    held = store.seats(ctx.require_store(), found['number'])
    turn = held[int(found['position'])]['id'] if found['state'] in ('running', 'held') and held else None
    latest = store.submissions(ctx.require_store(), found['number'])
    return {'discussion': found['number'], 'address': found['address'], 'subject': found['subject'],
            'state': found['state'], 'reason': found['reason'], 'chair': found['chair'], 'round': found['round'],
            'turn_of': turn, 'latest': latest[-1]['number'] if latest else 0, 'report': found['report'],
            **({'report_error': found['report_error']} if found['report_error'] else {}),
            'runner': 'running' if runner.alive(found) else 'stopped',
            'seats': [{'seat': seat['id'], 'kind': seat['kind'], 'kept': seat['kept'], 'taken': seat['taken']}
                      for seat in held]}


def status(ctx: Context) -> dict[str, Any]:
    """A table: its state, whose turn it is, and each seat's submissions kept against turns taken."""
    return status_of(ctx, store.discussion(ctx.require_store(), number_of(ctx)))


def list_tables(ctx: Context) -> dict[str, Any]:
    """The project's tables, newest first."""
    return {'discussions': [{'discussion': row['number'], 'address': row['address'], 'subject': row['subject'],
                             'state': row['state'], 'chair': row['chair'], 'created': row['created'],
                             'report': row['report']}
                            for row in reversed(store.discussions(ctx.require_store()))]}


def read(ctx: Context) -> dict[str, Any]:
    """Every turn after a cursor, each as every seat sees it and with its nouls, for the person's surfaces."""
    number = number_of(ctx)
    found = store.discussion(ctx.require_store(), number)
    rows = store.submissions(ctx.require_store(), number, int(ctx.nouns.get('since') or 0))
    turns = [{'number': row['number'], 'turn': render.turn(int(row['number'])), 'seat': render.who(row),
              'kind': row['kind'], 'entered': render.entered(row), 'shown': render.entry(row),
              'nouls': store.nouls(row), 'over512': row['over512'], 'link': render.link(number, int(row['number']))}
             for row in rows]
    return {'discussion': number, 'state': found['state'], 'opening': found['opening'], 'turns': turns,
            'latest': rows[-1]['number'] if rows else int(ctx.nouns.get('since') or 0)}


def seat_row(ctx: Context) -> tuple[dict[str, Any], dict[str, Any]]:
    """The table and the agent seat named."""
    found = store.discussion(ctx.require_store(), number_of(ctx))
    named = seats.parse(str(ctx.nouns['seat']))['id']
    held = next((seat for seat in store.seats(ctx.require_store(), found['number']) if seat['id'] == named), None)
    if held is None or held['kind'] != 'agent':
        raise Stop(f'{named} is not an agent seat at roundtable {found["number"]}.',
                   f'metaform roundtable status {found["number"]}')
    if held['session'] and ctx.session and held['session'] != ctx.session:  # MCP-042: one agent answers for a seat
        raise Stop(f'{named} is answered by another agent session.', f'metaform roundtable status {found["number"]}')
    return found, held


def mine(held: dict[str, Any]) -> bool:
    """Whether it is the seat's turn and its submission is still to come."""
    return bool(held['pending']) and not held['reply']


def turn(ctx: Context) -> dict[str, Any]:
    """An agent seat's turn: the discussion as it sees it, only what happened since its last reply; with wait, up to
    that many seconds for its turn to come."""
    found, held = seat_row(ctx)
    end = time.time() + min(int(ctx.nouns.get('wait') or 0), WAIT_MOST)
    while not mine(held) and found['state'] != 'ended' and time.time() < end:
        time.sleep(0.5)
        found, held = seat_row(ctx)
    if not mine(held):
        return {'discussion': found['number'], 'seat': held['id'], 'your_turn': False, 'state': found['state'],
                'next': ctx.calls(f'metaform roundtable turn {found["number"]} {held["id"]} wait=300')}
    return {'discussion': found['number'], 'seat': held['id'], 'your_turn': True, 'turn': held['pending'],
            'next': ctx.calls(f'metaform roundtable submit {found["number"]} {held["id"]} -- "<at most {LIMIT} '
                              'characters>"')}


def submit(ctx: Context) -> dict[str, Any]:
    """An agent seat's submission on its turn; over the limit, it is told once and may send it again."""
    found, held = seat_row(ctx)
    if not mine(held):
        raise Stop(f'It is not {held["id"]}\'s turn at roundtable {found["number"]}.',
                   f'metaform roundtable turn {found["number"]} {held["id"]} wait=300')
    text = text_of(ctx)
    if not text:
        raise Stop('A submission says something.', f'metaform roundtable submit {found["number"]} {held["id"]} -- '
                                                    '"<text>"')
    changes: dict[str, Any] = {'session': held['session'] or ctx.session}
    if len(text) > LIMIT and int(held['tries']) == 0:
        store.seat_change(ctx.require_store(), found['number'], held['position'], tries=1, **changes)
        return {'discussion': found['number'], 'seat': held['id'], 'submitted': False,
                'retry': said('over_limit', length=len(text), limit=LIMIT)}
    store.seat_change(ctx.require_store(), found['number'], held['position'],
                      reply={'text': text, 'over512': len(text) > LIMIT}, **changes)
    return {'discussion': found['number'], 'seat': held['id'], 'submitted': True,
            'next': ctx.calls(f'metaform roundtable turn {found["number"]} {held["id"]} wait=300')}


def submission(ctx: Context) -> str:
    """The text a seat submitted, and nothing else."""
    return str(store.submission(ctx.require_store(), number_of(ctx), int(ctx.nouns['submission']))['text']) + '\n'


def review(ctx: Context) -> str:
    """The full review: the four questions and the array's order, then every submission in short form."""
    number = number_of(ctx)
    found = store.discussion(ctx.require_store(), number)
    return render.review(found, store.submissions(ctx.require_store(), number),
                         int(ctx.setting('roundtable_keep')) / 100)


def run(ctx: Context) -> dict[str, Any]:
    """The table's runner, started detached by open, continue, comment and end."""
    return runner.Table(ctx, number_of(ctx)).run()


DISCUSSION = Noun('discussion', 'The table\'s number in this project.', kind='int')
SEAT = Noun('seat', 'The agent seat, agent:<name>, as the table was opened with it.')
TEXT = Noun('text', 'The text, every word after the nouns.', many=True)
OPEN_EXAMPLE = ('metaform roundtable open code.alarm seats=anthropic/claude-haiku-5.5,agent:me -- '
                '"How loud should the alarm be?"')
SEAT_LIST = 'A JSON list or a comma-separated list of seats: model ids such as anthropic/claude-haiku-5.5, or ' \
            'agent:<name> for an agent that submits its own turns.'

MODULE = Module(
    id='roundtable',
    summary='Hold a discussion among models at an Address, keeping only what Jev finds a real contribution.',
    purpose='Opens a roundtable at an Address: seats, models through OpenRouter or agents, speak in turn, each at '
            'most 512 characters, and Jev keeps only what is new, valuable, relevant and worth keeping. The person '
            'and their head agent chair it, and a report is written when it ends. Details: metaform help roundtable.',
    details='',
    tables=store.TABLES,
    verbs=(
        Verb('open', open_table, 'Open a roundtable at an Address with an opening message and its seats.',
             nouns=(Noun('address', 'The Address the discussion is about.'),
                    Noun('seats', SEAT_LIST + ' Every table names its seats.'),
                    Noun('subject', 'A few words naming the subject, for the report\'s file name; the opening\'s first '
                                    'words when none.', required=False),
                    Noun('opening', 'The opening message, every word after the nouns.', many=True)),
             examples=((OPEN_EXAMPLE, 'Opens a table with one model and one agent seat.'),),
             effect='write', open_world=True),
        Verb('comment', comment, 'Comment at a table, inline at the next gap between turns; unjudged, no limit.',
             nouns=(DISCUSSION, TEXT), effect='write'),
        Verb('hold', hold, 'Hold a table after the turn in flight until it is continued.', nouns=(DISCUSSION,),
             effect='write'),
        Verb('continue', resume, 'Continue a held table, or end the pause after a turn now.', nouns=(DISCUSSION,),
             effect='write', open_world=True),
        Verb('end', end, 'End a table; its report is written into docs/roundtables/.', nouns=(DISCUSSION,),
             effect='write', open_world=True),
        Verb('watch', watch, 'Say the person is watching a table, for a few seconds; the page renews it.',
             nouns=(DISCUSSION,), effect='write'),
        Verb('status', status, 'Read a table: its state, whose turn it is, each seat\'s kept against taken.',
             nouns=(DISCUSSION,), effect='read'),
        Verb('list', list_tables, 'List the project\'s tables, newest first.', effect='read'),
        Verb('read', read, 'Read a table\'s turns after a cursor, each as the seats see it, with its nouls.',
             nouns=(DISCUSSION, Noun('since', 'The last turn number already read; 0 for every turn.', kind='int',
                                     required=False)), effect='read'),
        Verb('turn', turn, 'As an agent seat, read your turn: what happened since your last reply.',
             nouns=(DISCUSSION, SEAT, Noun('wait', f'Seconds to wait for your turn, at most {WAIT_MOST}.',
                                           kind='int', required=False)), effect='read'),
        Verb('submit', submit, f'As an agent seat, submit your turn, at most {LIMIT} characters.',
             nouns=(DISCUSSION, SEAT, TEXT), effect='write'),
        Verb('submission', submission, 'Read the text one seat submitted, and nothing else.',
             nouns=(DISCUSSION, Noun('submission', 'The submission\'s number in its table.', kind='int')),
             effect='read'),
        Verb('review', review, 'Read the full review: every submission with its four nouls.', nouns=(DISCUSSION,),
             effect='read'),
        Verb('run', run, 'Run a table; started detached by open, and by continue, comment and end when it stopped.',
             nouns=(DISCUSSION,), surfaces=('cli',), effect='write', open_world=True),
    ),
    resources=(
        Resource('metaform://roundtable/discussion{discussion}/submission{submission}', 'A roundtable submission',
                 'The text a seat submitted at a roundtable, and nothing else, by the table\'s and the submission\'s '
                 'numbers.', 'submission'),
        Resource('metaform://roundtable/discussion{discussion}/review', 'A roundtable review',
                 'Every submission of a roundtable in short form: its turn, seat, whether it was kept, its four nouls '
                 'as [new, valuable, relevant, keep], and its link.', 'review'),
    ),
)
