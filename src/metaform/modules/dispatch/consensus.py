"""Consensus mode, VIEW-043: when every open ticket waits on an unanswered question, voting agents settle the
questions they agree on, and only a write-in, a comment or a tie waits for the person.

The agent starter runs it while Autostart agents is checked: tickets without an unanswered question get agents, and
only when every open ticket is frozen does it vote. The voter is the `voter` prompt of resources/prompts.xml. The
coordinator is Rich's logic, carried into the code below as written:

    #! AXIOM/2.0 name=coordinator
    @STATE_INIT: {Tickets} := <<DATA: [tickets]>>   {Cap} := min(|voters|, 8)
    @CONSTRAINT:
      !> Max 5 agents open. One vote per agent per ticket. No fabricated votes. Late votes discarded.
      +> Refill free slots at once with open, unblocked tickets. Voters never see counts.
    @CONDITION (TICKET):
      ?IF ( blocked ) -> BLOCKED
      :ELSE ?IF ( comment ) -> HALTED
      :ELSE ?IF ( write-in ) -> CLOSED
      :ELSE ?IF ( votes>=3 AND leader*100 > 66*votes ) -> CLOSED
      :ELSE ?IF ( votes>=4 AND leader*2 > votes ) -> CLOSED
      :ELSE ?IF ( votes>={Cap} ) -> CLOSED, most votes wins (tie -> TIE_REVIEW)
      :ELSE -> OPEN
    @ROUTER: @MATCH ( any OPEN ticket ) -> [TRUE] Run | [*] YIELD results
    @EXECUTE_PIPELINE (Run): @LOOP (max=|Tickets|*8): fill slots, oldest OPEN first -> record votes -> re-run TICKET
      -> refill. YIELD results + counts.
    @VERIFY: Agents <= 5? No duplicate or fabricated votes? Each CLOSED meets its rule? Else RECURSE(max=3), then HALT.

How its words are read here, each a choice recorded in VIEW-043: a frozen ticket is an open ticket with an unanswered
question, and it is voted on by its oldest one; "all tickets are frozen" means every ticket available to be selected,
so tickets in motion, taken by an agent, do not hold consensus mode back; blocked is a frozen ticket an agent has taken; |voters| is
`dispatch_agents`; a write-in is an answer that is none of the question's choices, and it ends voting on the ticket for
the person to read; a comment is anything else a voter says about a ticket; a winning choice is written as the
question's answer at once, so the ticket goes back to work; a write-in, a comment and a tie go to the person on the
web, and the coordinator does not see that ticket again. Each pass of the loop is one run of the agent starter, which
the server makes after every change; a voter's votes are a change.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Mapping, Sequence
from importlib import metadata
from pathlib import Path
from typing import Any, cast

from metaform import axiom
from metaform.data import Message, Node, Store, WorkRecord
from metaform.module import Context, Stop

from .signals import own_store

MAX_OPEN = 5  # Max 5 agents open
CAP_LIMIT = 8  # {Cap} := min(|voters|, 8)
PASSES = 8  # @LOOP (max=|Tickets|*8)
OPEN, BLOCKED, CLOSED, HALTED, TIE_REVIEW = 'OPEN', 'BLOCKED', 'CLOSED', 'HALTED', 'TIE_REVIEW'
SETTLED = (CLOSED, HALTED, TIE_REVIEW)  # seen only through the web from now on
CHOICE, WRITE_IN, COMMENT = 'choice', 'write-in', 'comment'


# ------------------------------------------------------------------------------------------------ the rule

def decide(*, blocked: bool, comment: bool, write_in: str | None, counts: Mapping[str, int],
           cap: int) -> tuple[str, str | None, str]:
    """@CONDITION (TICKET), in its order: the state, the winning answer if any, and the rule that settled it."""
    if blocked:
        return BLOCKED, None, 'blocked'
    if comment:
        return HALTED, None, 'comment'
    if write_in is not None:
        return CLOSED, write_in, 'write-in'
    votes = sum(counts.values())
    leader = max(counts.values(), default=0)
    first = next((choice for choice, count in counts.items() if count == leader), None)
    if votes >= 3 and leader * 100 > 66 * votes:
        return CLOSED, first, 'more than 66% of at least 3 votes'
    if votes >= 4 and leader * 2 > votes:
        return CLOSED, first, 'a majority of at least 4 votes'
    if votes >= cap:
        if sum(1 for count in counts.values() if count == leader) > 1:
            return TIE_REVIEW, None, f'a tie at {votes} votes'
        return CLOSED, first, f'the most of {votes} votes'
    return OPEN, None, ''


def cap(voters: int) -> int:
    return min(voters, CAP_LIMIT)


def tally(votes: Iterable[Mapping[str, Any]]) -> tuple[dict[str, int], str | None, bool]:
    """A ticket's choice counts, its first write-in, and whether any voter commented, from its recorded votes."""
    counts: dict[str, int] = {}
    write_in: str | None = None
    comment = False
    for vote in sorted(votes, key=lambda row: int(row['seq'])):
        if vote['kind'] == CHOICE:
            counts[vote['choice']] = counts.get(vote['choice'], 0) + 1
        elif vote['kind'] == WRITE_IN and write_in is None:
            write_in = vote['choice']
        elif vote['kind'] == COMMENT:
            comment = True
    return counts, write_in, comment


# ------------------------------------------------------------------------------------------------ the voter's words

def render(queue: Sequence[Mapping[str, Any]]) -> str:
    """The open tickets a voter is given, oldest first, as data: no counts and no other votes."""
    blocks: list[str] = []
    for item in queue:
        lines = [f'id: {item["work_id"]}', f'node: {item.get("address") or ""}']
        if item.get('task'):
            lines.append(f'ticket: {item["task"]}')
        if item.get('note'):
            lines.append(f'note: {item["note"]}')
        lines.append(f'question: {item["question"]}')
        lines.append('choices:')
        lines.extend(f'  {at}. {choice}' for at, choice in enumerate(item['choices'], 1))
        blocks.append('\n'.join(lines))
    return '\n' + '\n\n'.join(blocks) + '\n'


LINE = re.compile(r'^\s*(?:[-*]\s+|\d+[.)]\s+)?`?([0-9a-f]{8,32})`?\s*[,:]\s*(.+?)\s*$')


def parse(text: str, queue: Sequence[Mapping[str, Any]]) -> list[tuple[str, str, str]]:
    """What a voter said, as (work id, kind, answer): an `id, choice` line naming a queued ticket is a choice when it is
    one of the ticket's choices, by its words or its number, and a write-in otherwise; a second line for a ticket is a
    double vote and is not counted; any other line that names a queued ticket is a comment on it. Nothing is made up
    for a ticket the voter did not answer, and text naming no queued ticket names nothing to count."""
    by_id = {item['work_id']: item for item in queue}

    def known(word: str) -> str | None:
        found = [work_id for work_id in by_id if work_id == word or (len(word) >= 8 and work_id.startswith(word))]
        return found[0] if len(found) == 1 else None

    said: list[tuple[str, str, str]] = []
    answered: set[str] = set()
    commented: set[str] = set()
    for raw in text.replace('\r', '').split('\n'):
        line = raw.strip().strip('`')
        if not line:
            continue
        matched = LINE.match(line)
        work_id = known(matched.group(1)) if matched else None
        if matched and work_id is not None:
            if work_id in answered:
                continue  # No double votes
            answered.add(work_id)
            answer = matched.group(2).strip().strip('"\'`').strip()
            choices: list[str] = list(by_id[work_id]['choices'])
            picked = next((choice for choice in choices if choice.casefold() == answer.casefold()), None)
            if picked is None and answer.isdigit() and 1 <= int(answer) <= len(choices):
                picked = choices[int(answer) - 1]
            said.append((work_id, CHOICE, picked) if picked is not None else (work_id, WRITE_IN, answer))
            continue
        for word in re.findall(r'[0-9a-f]{8,32}', line):
            named = known(word)
            if named is not None and named not in commented:
                commented.add(named)
                said.append((named, COMMENT, line))
    return said


# ------------------------------------------------------------------------------------------------ help me answer

HELPERS = 3  # the agents a person asks to help answer one question; never started on their own
ADVICE = re.compile(r'^[ \t]*[*_#]*[ \t]*(meaning|answer|reason)[ \t]*[*_]*[ \t]*:[ \t]*[*_]*[ \t]*', re.IGNORECASE | re.MULTILINE)


def advise(text: str, choices: Sequence[str]) -> dict[str, str] | None:
    """A helper's reply as the three fields the `recommend` prompt asks for, `meaning:`, `answer:` and `reason:`, each
    running to the next: the answer is one of the choices, by its words or its number, or else a write-in. None when
    the reply gave no answer, so nothing is made up for it."""
    parts = ADVICE.split(text)
    fields = {parts[at].lower(): parts[at + 1].strip() for at in range(1, len(parts) - 1, 2)}
    answer = fields.get('answer', '').strip().strip('"\'`').strip()
    if not answer:
        return None
    numbered = re.match(r'^(\d+)[.)]?(?:\s+(.*))?$', answer)
    picked = next((choice for choice in choices if choice.casefold() == answer.casefold()), None)
    if picked is None and numbered and 1 <= int(numbered.group(1)) <= len(choices):
        picked = choices[int(numbered.group(1)) - 1]
    return {'kind': CHOICE if picked is not None else WRITE_IN, 'choice': picked if picked is not None else answer,
            'meaning': fields.get('meaning', ''), 'reason': fields.get('reason', '')}


def recommend(ctx: Context, store: Store, question: Message, record: WorkRecord | None) -> list[str]:
    """Help me answer: three helpers each read one open question and say what it means and what they would answer,
    for the person to decide. It is started only by the person, applies no answer and closes nothing. A question
    already being helped with keeps its helpers."""
    own = Store(store.project_id, module='dispatch')
    prefix = f'help:{question.id}:'
    running = [row['voter'] for row in running_voters(own) if str(row['round']).startswith(prefix)]
    if running:
        return running
    queue = [{'message_id': question.id, 'work_id': record.id if record else '',
              'address': record.address if record else '', 'task': record.task if record else '',
              'note': record.note if record else '', 'question': question.text or '',
              'choices': list(question.suggestions)}]
    round_id = prefix + secrets.token_hex(4)
    return [voter for voter in (launch(ctx, store, own, round_id, queue) for _ in range(HELPERS)) if voter]


def advice(store: Store, message_id: str) -> dict[str, Any]:
    """What the helpers said about one question: each one's plain meaning, answer and reason, the count for each
    choice, the answer most of them chose, and how many are still reading it."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        said = sorted((dict(row) for row in tx.rows('advice', {'message_id': message_id}, limit=0).results),
                      key=lambda row: int(row['seq']))
    counts: dict[str, int] = {}
    for row in said:
        if row['kind'] == CHOICE:
            counts[row['choice']] = counts.get(row['choice'], 0) + 1
    best = max(counts.values(), default=0)
    leading = [row['choice'] for row in said if row['kind'] == CHOICE and counts[row['choice']] == best]
    reading = sum(1 for row in running_voters(own) if str(row['round']).startswith(f'help:{message_id}:'))
    return {'advice': [{key: row[key] for key in ('voter', 'kind', 'choice', 'meaning', 'reason', 'at')} for row in said],
            'counts': counts, 'recommendation': leading[0] if leading else (said[0]['choice'] if said else None),
            'reading': reading}


# ------------------------------------------------------------------------------------------------ the coordinator

def frozen(open_work: Sequence[WorkRecord], waiting: Mapping[str, list[Message]]) -> list[WorkRecord]:
    """The open tickets that wait on an unanswered question; an exclude record is no ticket."""
    return [record for record in open_work if record.condition != 'exclude' and record.id in waiting]


def all_frozen(open_work: Sequence[WorkRecord], waiting: Mapping[str, list[Message]]) -> bool:
    """Every ticket that could be picked up is frozen, and one is: no agent can be started. A ticket in motion, taken
    by an agent, is not available to be selected, so it neither counts against this nor stops it; voters fill the free
    slots while those agents go on working."""
    tickets = [record for record in open_work if record.condition != 'exclude' and not record.taken]
    return bool(tickets) and all(record.id in waiting for record in tickets)


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _alive(row: Mapping[str, Any]) -> bool:
    from . import command_line
    words = command_line(int(row['pid'] or 0)) if row.get('pid') else []
    return any(words[at:at + 3] == ['dispatch', 'vote', row['voter']] for at in range(len(words)))


def running_voters(own: Store) -> list[dict[str, Any]]:
    """The voters running now; a voter whose process has gone is marked ended."""
    with own.tables(write=False) as tx:
        rows = [dict(row) for row in tx.rows('voters', {'state': 'running'}, limit=0).results]
    alive: list[dict[str, Any]] = []
    for row in rows:
        if _alive(row) or (row.get('pid') is None and time.time() - float(row['seq']) / 1000 < 30):
            alive.append(row)
        else:
            with own.tables() as tx:
                tx.update('voters', {'voter': row['voter']}, {'state': 'ended', 'how': 'its process had ended'})
    return alive


def end_mode(own: Store, how: str) -> None:
    """Mode ended: the voters halt, and their late votes are discarded."""
    from . import end_group
    for row in running_voters(own):
        if row.get('pid'):
            end_group(int(row['pid']))
        with own.tables() as tx:
            tx.update('voters', {'voter': row['voter']}, {'state': 'ended', 'how': how})
    with own.tables() as tx:
        mode = tx.get('mode', {'name': 'consensus'})
        if mode is not None and not mode['ended']:
            tx.update('mode', {'name': 'consensus'}, {'ended': _now()})


def _round(own: Store, tickets: int) -> dict[str, Any]:
    created = False
    with own.tables() as tx:
        mode = tx.get('mode', {'name': 'consensus'})
        if mode is None or mode['ended']:
            fresh = {'name': 'consensus', 'round': secrets.token_hex(8), 'started': _now(), 'ended': None,
                     'tickets': tickets}
            if mode is None:
                tx.insert('mode', fresh)
            else:
                tx.update('mode', {'name': 'consensus'}, fresh)
            created = True
            result = fresh
        else:
            result = dict(mode)
    if created:
        from metaform.module import context

        from .signals import publish
        publish(context('dispatch', Path(own.project().path), project=own.project_id), 'consensus-started',
                session_id='consensus:' + str(result['round']), tickets=tickets, round=result['round'])
    return result


def _settle(store: Store, own: Store, record: WorkRecord, question: Message, state: str, winner: str | None,
            rule: str, counts: Mapping[str, int]) -> None:
    """A settled ticket: a winning choice answers its question, so the ticket goes back to work; a write-in, a comment
    or a tie is told to the person at the ticket's node, the voter's words with it."""
    node = Node.of(record.node_kind, record.node_id)
    shown = ', '.join(f'{choice}: {count}' for choice, count in counts.items()) or 'no votes for a choice'
    if state == CLOSED and rule != 'write-in' and winner is not None:
        store.reply(question.id, winner)
        store.tell(node, f'Consensus answered question {question.id} on work {record.id} with "{winner}", '
                         f'by {rule} ({shown}).', by='consensus')
    elif state == CLOSED:
        store.tell(node, f'Consensus voting ended on question {question.id} on work {record.id}: a voter '
                         f'wrote in its own answer, for you to read: "{winner}". Votes so far: {shown}.', by='consensus')
    elif state == HALTED:
        with own.tables(write=False) as tx:
            said = [row['choice'] for row in tx.rows('votes', {'message_id': question.id}, limit=0).results
                    if row['kind'] == COMMENT]
        store.tell(node, f'Consensus voting stopped on question {question.id} on work {record.id}: a voter '
                         f'commented, for you to read: "{said[0] if said else ""}". Votes so far: {shown}.',
                   by='consensus')
    else:
        store.tell(node, f'Consensus voting tied on question {question.id} on work {record.id} ({shown}); '
                         'it waits for your answer.', by='consensus')
    with own.tables() as tx:
        tx.update('consensus', {'message_id': question.id},
                  {'state': state, 'winner': winner, 'rule': rule, 'tally': json.dumps(dict(counts)),
                   'closed': _now()})
    if not (state == CLOSED and rule != 'write-in' and winner is not None):
        from metaform.module import context

        from .signals import publish
        publish(context('dispatch', Path(store.project().path), project=store.project_id), 'consensus-review',
                work_id=record.id, key=question.id, message_id=question.id,
                reason=rule, state=state)


def coordinate(ctx: Context, store: Store, tickets: Sequence[WorkRecord], waiting: Mapping[str, list[Message]],
               workers: int) -> dict[str, Any]:
    """One pass of the coordinator: record what the votes settle, then fill the free slots with voters."""
    from . import ticket as read_ticket
    own = own_store(store)
    mode = _round(own, len(tickets))
    voters = int(ctx.setting('dispatch_agents'))
    limit = cap(voters)
    candidates: list[tuple[WorkRecord, Message]] = []
    with own.tables() as tx:
        for record in tickets:
            question = waiting[record.id][0]
            row = tx.get('consensus', {'message_id': question.id})
            if row is None:
                tx.insert('consensus', {'message_id': question.id, 'work_id': record.id, 'state': OPEN,
                                        'round': mode['round'], 'opened': _now(), 'seq': time.time_ns()})
            elif row['state'] in SETTLED:
                continue
            candidates.append((record, question))
    settled: list[dict[str, Any]] = []
    still: list[tuple[WorkRecord, Message]] = []
    for record, question in candidates:
        with own.tables(write=False) as tx:
            votes = [dict(row) for row in tx.rows('votes', {'message_id': question.id}, limit=0).results]
        counts, write_in, comment = tally(votes)
        state, winner, rule = decide(blocked=bool(read_ticket(store, record.id).taken), comment=comment,
                                     write_in=write_in, counts=counts, cap=limit)
        if state in SETTLED:
            _settle(store, own, record, question, state, winner, rule, counts)
            settled.append({'work_id': record.id, 'message_id': question.id, 'state': state,
                            'answer': winner, 'rule': rule, 'counts': counts})
        elif state == OPEN:
            still.append((record, question))
    if not still:
        end_mode(own, 'no open ticket is left to vote on')
        return {'mode': 'consensus', 'settled': settled, 'voters': []}
    active = running_voters(own)
    with own.tables(write=False) as tx:
        made = len(tx.rows('voters', {'round': mode['round']}, limit=0).results)
    free = max(0, MAX_OPEN - workers - len(active))
    free = min(free, max(0, int(mode['tickets'] or len(tickets)) * PASSES - made))
    queue = [{'work_id': record.id, 'message_id': question.id, 'address': record.address,
              'task': record.task, 'note': record.note, 'question': question.text or '',
              'choices': list(question.suggestions)}
             for record, question in sorted(still, key=lambda pair: (pair[1].created, pair[0].created))]  # ties keep board order
    started = [launch(ctx, store, own, mode['round'], queue) for _ in range(free)]
    return {'mode': 'consensus', 'settled': settled, 'voters': [voter for voter in started if voter]}


def results(store: Store) -> list[dict[str, Any]]:
    """Every question consensus voted on, newest first, for the person to review: the question and its choices, how
    many votes each choice got, every write-in and comment in the voter's own words, and what came of it."""
    own = own_store(store)
    with own.tables(write=False) as tx:
        rows = [dict(row) for state in (OPEN, CLOSED, HALTED, TIE_REVIEW)
                for row in tx.rows('consensus', {'state': state}, limit=0).results]
        votes = {row['message_id']: [dict(vote) for vote in tx.rows('votes', {'message_id': row['message_id']},
                                                                      limit=0).results] for row in rows}
    asked = {message.id: message for message in store.messages(None, 'question', None, limit=0).results}
    shown: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda row: int(row['seq']), reverse=True):
        message = asked.get(row['message_id'])
        cast_votes = votes.get(row['message_id'], [])
        counts, _, _ = tally(cast_votes)
        applied = row['state'] == CLOSED and row['rule'] != 'write-in'
        shown.append({
            'message_id': row['message_id'], 'work_id': row['work_id'], 'state': row['state'],
            'outcome': ('answered' if applied else 'written in' if row['state'] == CLOSED else
                        'halted by a comment' if row['state'] == HALTED else 'tied' if row['state'] == TIE_REVIEW
                        else 'voting'),
            'rule': row['rule'] or '', 'answer': row['winner'],
            'question': message.text if message else '', 'address': message.address if message else None,
            'choices': [{'choice': choice, 'votes': counts.get(choice, 0)}
                        for choice in (list(message.suggestions) if message else counts)],
            'said': [{'kind': vote['kind'], 'text': vote['choice']} for vote in cast_votes if vote['kind'] != CHOICE],
            'votes': len(cast_votes), 'closed': row['closed'],
            'still_applied': bool(applied and message is not None and message.closed is not None
                                  and message.answer == row['winner'])})
    return shown


def launch(ctx: Context, store: Store, own: Store, round_id: str, queue: list[dict[str, Any]]) -> str | None:
    """Start one voter as a process detached from the terminal, its queue recorded with it."""
    import shutil

    from . import AGENTS, argv, group_options
    agent = str(ctx.setting('dispatch_agent'))
    if agent not in AGENTS or shutil.which(argv(str(ctx.setting(f'dispatch_{agent}')))[0]) is None:
        return None
    voter = secrets.token_hex(8)
    with own.tables() as tx:
        tx.insert('voters', {'voter': voter, 'round': round_id, 'agent': agent, 'state': 'running',
                             'queue': json.dumps(queue), 'started': _now(), 'seq': time.time_ns() // 1_000_000})
    log = os.path.join(tempfile.gettempdir(), f'metaform-vote-{voter}.log')
    try:
        with open(log, 'ab') as written:
            process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'vote', voter,
                                        '--project', store.project_id],
                                       cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written,
                                       stderr=written, **group_options())
    except OSError as error:
        with own.tables() as tx:
            tx.update('voters', {'voter': voter}, {'state': 'ended', 'how': f'it did not start: {error}'})
        return None
    with own.tables() as tx:
        tx.update('voters', {'voter': voter}, {'pid': process.pid})
    return voter


def record(own: Store, voter: str, queue: Sequence[Mapping[str, Any]], said: Sequence[tuple[str, str, str]]) -> int:
    """Keep a voter's votes: one per voter per ticket, and none for a ticket no longer open, since late votes are
    discarded. Returns how many were kept."""
    message_of = {item['work_id']: item['message_id'] for item in queue}
    kept = 0
    with own.tables() as tx:
        for work_id, kind, answer in said:
            message_id = message_of[work_id]
            row = tx.get('consensus', {'message_id': message_id})
            if row is None or row['state'] != OPEN:
                continue
            if tx.get('votes', {'message_id': message_id, 'voter': voter}) is not None:
                continue
            tx.insert('votes', {'message_id': message_id, 'voter': voter, 'work_id': work_id, 'kind': kind,
                                'choice': answer, 'at': _now(), 'seq': time.time_ns()})
            kept += 1
    return kept


# ------------------------------------------------------------------------------------------------ one voter

def advised(own: Store, voter: str, item: Mapping[str, Any], text: str) -> int:
    """Keep one helper's advice on a question, once; returns how many were kept."""
    found = advise(text, list(item['choices']))
    if found is None:
        return 0
    with own.tables() as tx:
        if tx.get('advice', {'message_id': item['message_id'], 'voter': voter}) is not None:
            return 0
        tx.insert('advice', {'message_id': item['message_id'], 'voter': voter, **found, 'at': _now(),
                             'seq': time.time_ns()})
    return 1


async def vote(ctx: Context) -> dict[str, Any]:
    """`metaform dispatch vote <voter>`: one voting agent's ACP session, given the voter prompt with its queue; what it
    says is counted when its turn ends."""
    import acp
    from acp.schema import (
        AllowedOutcome,
        ClientCapabilities,
        DeniedOutcome,
        FileSystemCapabilities,
        Implementation,
        McpServerStdio,
        PermissionOption,
        RequestPermissionResponse,
        ToolCallUpdate,
    )

    from . import READS, argv, prompt
    store = ctx.require_store()
    own = Store(store.project_id, module='dispatch')
    voter = str(ctx.nouns['voter'])
    with own.tables(write=False) as tx:
        row = tx.get('voters', {'voter': voter})
    if row is None:
        raise Stop(f'No voter {voter}.', 'metaform dispatch autostart')
    row = dict(row)
    queue: list[dict[str, Any]] = json.loads(row['queue'])
    command = argv(str(ctx.setting(f'dispatch_{row["agent"]}')))
    words: list[str] = []

    class Voter:
        async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
            data: dict[str, Any] = update.model_dump(mode='json', by_alias=True, exclude_none=True)
            if data.get('sessionUpdate') == 'agent_message_chunk':
                content: Any = data.get('content')
                held: dict[str, Any] = cast(dict[str, Any], content) if isinstance(content, dict) else {}
                words.append(str(held.get('text', '')))

        async def request_permission(self, session_id: str, tool_call: ToolCallUpdate,
                                     options: list[PermissionOption], **kwargs: Any) -> RequestPermissionResponse:
            """A voter reads the question and the specs and changes nothing."""
            allow = next((option for option in options if str(option.kind) == 'allow_once'), None)
            if allow is not None and str(tool_call.kind) in READS:
                return RequestPermissionResponse(outcome=AllowedOutcome(option_id=allow.option_id, outcome='selected'))
            reject = next((option for option in options if str(option.kind).startswith('reject')), None)
            if reject is not None:
                return RequestPermissionResponse(outcome=AllowedOutcome(option_id=reject.option_id,
                                                                        outcome='selected'))
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome='cancelled'))

    how = 'it voted'
    kept = 0
    from . import group_options
    process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                                                   stdout=asyncio.subprocess.PIPE, stderr=None,
                                                   cwd=store.project().path, env=dict(os.environ), limit=1 << 24,
                                                   **group_options())
    try:
        conn = acp.connect_to_agent(Voter(), process.stdin, process.stdout)  # pyright: ignore[reportArgumentType]
        try:
            version = metadata.version('metaform')
        except metadata.PackageNotFoundError:
            version = '0'
        await asyncio.wait_for(conn.initialize(
            protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(
                fs=FileSystemCapabilities(read_text_file=False, write_text_file=False), terminal=False),
            client_info=Implementation(name='metaform', title='Metaform', version=version)), 60)
        made = await asyncio.wait_for(conn.new_session(
            cwd=store.project().path,
            mcp_servers=[McpServerStdio(name='metaform', command=sys.executable,
                                        args=['-m', 'metaform', 'mcp', 'serve'], env=[])]), 60)
        helping = str(row['round']).startswith('help:')
        item = queue[0]
        text = prompt('recommend', question=str(item['question']), ticket=str(item.get('task') or item.get('note') or ''),
                      node=str(item.get('address') or ''),
                      choices='\n'.join(f'{at}. {choice}' for at, choice in enumerate(item['choices'], 1))) \
            if helping else prompt('voter', queue=render(queue))
        found = axiom.notices('voter', text)  # a flagged prompt is still sent, BASE-057
        if found:
            await ctx.publish_async('signal.raised', {'signal': axiom.SIGNAL, 'module': 'dispatch', 'voter': voter,
                                                      'notices': found})
        await conn.prompt(session_id=str(made.session_id), prompt=[acp.text_block(text)])
        if helping:
            kept = await asyncio.to_thread(advised, own, voter, queue[0], ''.join(words))
        else:
            kept = await asyncio.to_thread(record, own, voter, queue, parse(''.join(words), queue))
    except Exception as error:  # noqa: BLE001  a voter that fails votes nothing; its slot is refilled
        how = f'it failed: {error}'
    finally:
        if process.returncode is None:
            from . import end_group
            end_group(process.pid)
        with own.tables() as tx:
            tx.update('voters', {'voter': voter}, {'state': 'ended', 'how': how})
        active = await asyncio.to_thread(store.active_base)
        await ctx.publish_async('map.changed', {'project': store.project_id, 'tables': 'dispatch',
                                                'base_id': active.id if active is not None else None})
    return {'voter': voter, 'votes': kept, 'ended': how}
