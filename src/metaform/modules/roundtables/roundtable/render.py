"""How a table's turns read: to a seat on its turn, to the chair, to an A2A follower, in the review, in the record the
report is written from and in the export. Every word is a prompt of `resources/prompts.xml`.

Every seat has a system message (`system`), fixed for the table's life and first in every request: the table's rules,
which seat it is and the opening. A turn that entered, an accepted submission or a comment, reads as its text. A
vetoed turn reads as one short line, the same everywhere: `T28 Opus vetoed (not new) [0.61, 0.87, 0.95, 0.88]`, the
seat by its short name, the questions it failed in words and its four scores. A turn with no submission reads to a
seat as one line with no error in it; the chair's review keeps the reason. The link to a vetoed turn's text follows
only for a reader with a tool that reads it. A seat's own reply, once judged, stays in its conversation as what entered
of it or as one line saying it was vetoed (`own`).

A Roundtable 2 table speaks in its own sequence (`topic_view`): a seat's first turn is the first topic; each later
turn of a topic is the status of the seat's previous contribution, told only now, and the other seats' contributions
since its last turn, labeled by model, a vetoed one left out and a turn with no submission one line with no error in
it; a later topic opens with the status and its own text, in a context begun again.
"""
from __future__ import annotations

import contextlib
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from . import config, store
from .prompts import said
from .store import NOULS, VETO, nouls

LIMIT = 512  # default reply length, including historical discussions without a saved limit
PASS = re.compile(r'\W*(?:T\d+\W*)?pass\W*', re.IGNORECASE)  # PASS alone, perhaps labeled or marked up


def passed(text: str) -> bool:
    """Whether a reply is a pass: PASS alone, which is recorded and never judged."""
    return PASS.fullmatch(text) is not None


def turn(number: int) -> str:
    return f'T{number:02d}'


def link(discussion: int, number: int) -> str:
    return f'roundtable://discussion{discussion}/submission{number}'


def who(row: Mapping[str, Any]) -> str:
    """Who a turn is credited to: its seat by its short name, or the chair for a comment."""
    if row['kind'] == 'chair':
        return said('name_chair')
    return str(row.get('name') or row['seat'])


def entered(row: Mapping[str, Any]) -> bool:
    """Whether the turn entered the discussion: an accepted submission or a comment."""
    return bool(row['accepted']) or row['kind'] in ('chair', 'carry', 'handoff')


def outcome(row: Mapping[str, Any]) -> str:
    """kept, vetoed, none, pass, comment, unjudged for a submission the table ended before Jev judged, or over512
    for a turn the first version refused unjudged for its length, in a table imported from it."""
    if row['kind'] == 'chair':
        return 'comment'
    if row['kind'] in ('carry', 'handoff'):
        return str(row['kind'])
    if row.get('unjudged'):
        return 'unjudged'
    if row['kind'] in ('none', 'pass'):
        return str(row['kind'])
    if row.get('over512'):
        return 'over512'
    return 'kept' if row['accepted'] else 'vetoed'


def snapshot(names: Sequence[str], staged: bool = False, reply_limit: int = LIMIT,
             judging: bool | None = None) -> dict[str, Any]:
    """The rules and judgment criteria fixed when a discussion opens; for a Roundtable 2 table, `staged`, its rules
    are the discussion instructions every seat receives, its criteria Jev's two nouls for a submission, each with its
    own bar in `floors`. Completion is independent of judging."""
    from .judge import questions

    keep = config.keep()
    judging = config.value('judging') if judging is None else judging
    common = {'judging': judging, 'context_tokens': config.value('context_tokens'),
              'judging_context_tokens': config.value('judging_context_tokens'),
              'context_budgets': config.context_budgets()}
    if not judging:
        return {**common, 'rules': said('discussion_unjudged'), 'reply_limit': reply_limit}
    if staged:
        return {**common, 'rules': said('discussion_start'), 'reply_limit': reply_limit, 'keep': keep,
                'criteria': questions(VETO),
                'jev_model': config.value('jev_model'),
                'floors': {'new_context': config.floor('keep_new'), 'on_topic': config.floor('keep_on_topic')},
                'failed': {name: said(f'failed_{name}') for name in (*VETO, 'repeat')}}
    rules = said('rules', seats=', '.join(names), limit=reply_limit, keep=f'{keep:.2f}')
    return {**common, 'rules': rules, 'reply_limit': reply_limit,
            'keep': keep, 'criteria': questions(), 'jev_model': config.value('jev_model'),
            'failed': {name: said(f'failed_{name}') for name in NOULS}}


def floors(held: Mapping[str, Any]) -> dict[str, float]:
    """The bar of each noul a captured table judges submissions on: its own when it has one, else `keep`."""
    own = cast(dict[str, Any], held.get('floors') or {})
    return {name: float(own.get(name, held['keep'])) for name in cast(dict[str, Any], held.get('criteria') or {})}


def captured(discussion: Mapping[str, Any]) -> dict[str, Any]:
    given = discussion.get('snapshot')
    return cast(dict[str, Any], given) if isinstance(given, dict) else {}


def session(discussion: Mapping[str, Any]) -> dict[str, Any] | None:
    """A session of roundtables' settings, fixed when it opened: its count, folder and the owner's messages."""
    found = captured(discussion).get('session')
    return cast(dict[str, Any], found) if isinstance(found, dict) else None


def said_done(text: str) -> bool:
    """Whether a reply says the seat is finished: the word done as its last word."""
    words = re.findall(r"[A-Za-z']+", text)
    return bool(words) and words[-1].casefold() == 'done'


def judging(discussion: Mapping[str, Any]) -> bool:
    return bool(captured(discussion).get('judging', True))


def continuation(discussion: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], discussion.get('continuation') or {})


def shared(discussion: Mapping[str, Any]) -> str:
    held = continuation(discussion)
    if not held or held.get('topic') != discussion.get('topic'):
        return ''
    notes = '\n\n'.join(f'{one["name"]} (seat {int(one["position"]) + 1}):\n{one["text"]}'
                        for one in held.get('notes', []))
    return said('continuation_context', summary=held['text'], notes=notes)


def reply_limit(discussion: Mapping[str, Any]) -> int:
    """The maximum reply length frozen with this discussion, or the historical default."""
    return int(captured(discussion).get('reply_limit', LIMIT))


def rules(names: Sequence[str], discussion: Mapping[str, Any] | None = None) -> str:
    """The table's rules, stated once before the opening question: the seats in speaking order, the limit, Jev's four
    questions and the bar, and how a veto is shown."""
    if discussion is not None:
        return str(captured(discussion).get('rules') or 'Discussion-time rules were not recorded.')
    return str(snapshot(names)['rules'])


def scores(row: Mapping[str, Any]) -> str:
    values = nouls(row)
    return '[' + ', '.join(f'{value:.2f}' for value in values) + ']' if values else '[]'


def failed(row: Mapping[str, Any]) -> list[str]:
    """The questions a judged turn fell below its bar on, by name: new, valuable, relevant, keep, or at a table with
    topics new_context and on_topic; `repeat` for a repeat the code caught before Jev was asked."""
    if row.get('repeat_of') is not None:
        return ['repeat']
    held = captured(store.discussion(int(row['discussion']))) if row.get('discussion') is not None else {}
    if not held:
        return []
    bars = floors(held)
    return [name for name in bars if row.get(name) is not None and float(row[name]) < bars[name]]


def failed_words(row: Mapping[str, Any]) -> str:
    """The questions a vetoed turn failed, in the words the table opened with, joined with commas."""
    held = captured(store.discussion(int(row['discussion']))) if row.get('discussion') is not None else {}
    if not held and row.get('repeat_of') is None:
        return 'failed criteria not recorded'
    words = cast(dict[str, str], held.get('failed') or {})
    return ', '.join(words.get(name) or said(f'failed_{name}') for name in failed(row))


def short(row: Mapping[str, Any]) -> str:
    """A turn's one short line, the same in every view, record, export and report."""
    at, seat = turn(int(row['number'])), who(row)
    kind = outcome(row)
    if kind == 'vetoed':
        return said('verdict', turn=at, seat=seat, failed=failed_words(row), scores=scores(row))
    if kind == 'kept':
        return said('short_kept', turn=at, seat=seat, scores=scores(row))
    if kind == 'none':
        return said('verdict_none', turn=at, seat=seat, reason=row['reason'] or '')
    if kind == 'pass':
        return said('short_pass', turn=at, seat=seat)
    if kind == 'unjudged':
        return said('short_unjudged', turn=at, seat=seat)
    if kind == 'over512':
        return said('short_over512', turn=at, seat=seat)
    if kind in ('carry', 'handoff'):
        return f'{at} {seat}: {kind}'
    return said('short_comment', turn=at, seat=seat)


def entry(row: Mapping[str, Any], links: bool = False) -> str:
    """One turn as a reader of the discussion sees it: the text that entered, or its short line, a turn with no
    submission with no error in it; a veto's link to its text after it only for a reader with a tool that reads it."""
    if entered(row):
        return said('turn_entry', turn=turn(int(row['number'])), seat=who(row), text=row['text'])
    if outcome(row) == 'none':
        return said('others_none', seat=who(row))
    line = short(row)
    if links and outcome(row) == 'vetoed':
        line += '\n' + said('verdict_link', link=link(int(row['discussion']), int(row['number'])))
    return line


def tidy(text: str) -> str:
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def system(discussion: Mapping[str, Any], names: Sequence[str], name: str) -> str:
    """A seat's system message, fixed for the table's life and first in every request: the table's rules, which
    seat it is among the seats in speaking order, and the opening; at a table with topics the opening first."""
    text = said('seat_system_topics' if discussion.get('stage') else 'seat_system', opening=discussion['opening'],
                rules=rules(names, discussion), seat=name, seats=', '.join(names),
                reply_length=notes_line(discussion) + said('reply_length', limit=reply_limit(discussion)))
    if session(discussion):
        text += '\n\n' + said('session_coordinator')
        row = next((one for one in store.seats(int(discussion['number'])) if one['name'] == name), None)
        profile = store.profile(f'{row["agent"] or row["kind"]}/{row["model"] or row["id"]}') if row else None
        text += '\n\n' + said('session_profile',
                             score='unscored' if not profile or profile['score'] is None
                             else f'{float(profile["score"]):g}',
                             ratings=int(profile['ratings']) if profile else 0,
                             sessions=int(profile['sessions']) if profile else 0)
    return tidy(text)


def notes_line(discussion: Mapping[str, Any]) -> str:
    """The paragraph before the reply limit naming the table's notes folder; empty for a table with no folder."""
    if not discussion.get('folder') or discussion.get('number') is None or session(discussion):
        return ''  # a session's seats are told about its folder in the owner's opening message
    return said('notes_folder', folder=str(config.notes(str(discussion['folder']), int(discussion['number'])))) + '\n\n'


def own(row: Mapping[str, Any]) -> str:
    """A seat's own judged reply as its conversation keeps it: what entered of it, or one line saying it was
    vetoed and why."""
    if entered(row):
        return str(row['text'])
    return said('own_vetoed', turn=turn(int(row['number'])), failed=failed_words(row))


def seat_view(rows: Sequence[Mapping[str, Any]], first: bool, links: bool = False, limit: int = LIMIT) -> str:
    """What a seat receives on its turn: on its first, every turn before its own; on each later turn, only the turns
    since its last reply. The limit closes it."""
    turns = '\n\n'.join(entry(row, links) for row in rows)
    if first:
        return tidy(said('seat_first', turns=turns, limit=limit))
    return tidy(said('seat_next', turns=turns or said('nothing_since'), limit=limit))


# ----------------------------------------------------------------------------------------------- Roundtable 2

def status(row: Mapping[str, Any] | None, limit: int = LIMIT) -> str:
    """The status of a seat's previous contribution, told at its next turn: entered, truncated, vetoed and why, no
    submission, or a pass; nothing new when it was told already."""
    if row is None:
        return said('status_nothing')
    at, kind = turn(int(row['number'])), outcome(row)
    if kind in ('none', 'pass'):
        return said(f'status_{kind}', turn=at)
    if kind == 'vetoed' and row.get('repeat_of') is not None:
        return said('status_repeat', turn=at, earlier=turn(int(row['repeat_of'])))
    if kind == 'vetoed':
        return said('status_vetoed_truncated' if row['truncated'] else 'status_vetoed', turn=at,
                    failed=failed_words(row), limit=limit)
    return said('status_kept_truncated' if row['truncated'] else 'status_kept', turn=at, limit=limit)


def labeled(rows: Sequence[Mapping[str, Any]]) -> str:
    """Other seats' contributions, labeled by model: what entered as its text, a turn with no submission or a pass as
    one line with no error in it; a vetoed one did not enter and is left out."""
    lines = [entry(row) if entered(row) else said(f'others_{outcome(row)}', seat=who(row))
             for row in rows if entered(row) or outcome(row) in ('none', 'pass')]
    return '\n\n'.join(lines) or said('no_contributions')


def topic_view(topic: str, own: Mapping[str, Any] | None, others: Sequence[Mapping[str, Any]],
               first: bool, spoken: bool, digest: str = '', limit: int = LIMIT) -> str:
    """What a seat receives on a discussion turn of a Roundtable 2 table: on its first turn at the table the topic,
    the opening and the discussion instructions being in its system message; on its first turn of a later topic, or
    in a context begun again, the status of its previous contribution and the topic; on each later turn of a topic,
    `spoken`, the status alone. The digest of earlier topics comes before the topic whenever the topic is given. The
    other seats' contributions on the topic since its last turn and the limit close each."""
    turns = labeled(others)
    if first:
        return tidy(said('topic_first', digest=digest, topic=topic, turns=turns, limit=limit))
    if not spoken:
        return tidy(said('topic_open', status=status(own, limit), digest=digest, topic=topic, turns=turns, limit=limit))
    return tidy(said('next_turn', status=status(own, limit), turns=turns, limit=limit))


def idea_lines(ideas: Sequence[Mapping[str, Any]]) -> str:
    return '\n'.join(said('idea_line', id=one['id'], title=one['name'], summary=one['summary']) for one in ideas)


def stage_lines(rows: Sequence[Mapping[str, Any]], stage: str) -> str:
    """Every seat's answer to one stage, labeled by model: a ranking as its ids, best first, or why it could not be
    read; an explanation as its text; no submission as one line."""
    lines: list[str] = []
    for row in (one for one in rows if one['stage'] == stage):
        if stage == 'ranking' and row.get('ranking'):
            lines.append(said('stage_entry', seat=row['name'], text=', '.join(row['ranking'])))
        elif stage == 'ranking' and row['text']:
            lines.append(said('stage_unread', seat=row['name'], error=row['error'] or ''))
        elif row['text']:
            lines.append(said('stage_entry', seat=row['name'], text=row['text']))
        else:
            lines.append(said('others_none', seat=row['name']))
    return '\n\n'.join(lines)


def topic_heading(topic: Mapping[str, Any]) -> str:
    return said('record_topic', number=int(topic['topic']) + 1, title=topic['title'])


def topic_record(topic: Mapping[str, Any], stages: Sequence[Mapping[str, Any]]) -> list[str]:
    """What a topic's stages gave, for the record: the synthesis, the rankings and the host's summary."""
    own = [one for one in stages if int(one['topic']) == int(topic['topic'])]
    lines: list[str] = []
    for one in own:
        if one['stage'] == 'synthesis' and one['ideas']:
            lines.append(said('record_synthesis', seat=one['name'], text=one['text']))
    if any(one['stage'] == 'ranking' for one in own):
        lines.append(said('record_rankings', text=stage_lines(own, 'ranking')))
    for one in own:
        if one['stage'] == 'host_summary' and one['text']:
            lines.append(said('record_host', seat=one['name'], text=one['text']))
    return lines


def digest(number: int, before_topic: int) -> str:
    """The digest of a table's topics before `before_topic` (2.4): each as its heading, its synthesis and its host
    summary; a topic whose stages gave neither is left out, and with none at all the digest is empty."""
    stages = store.staged(number)
    parts: list[str] = []
    for topic in store.topics(number):
        if int(topic['topic']) >= before_topic:
            continue
        own = [one for one in stages if int(one['topic']) == int(topic['topic'])]
        lines = [said('record_synthesis', seat=one['name'], text=one['text']) for one in own
                 if one['stage'] == 'synthesis' and one['ideas']]
        lines += [said('record_host', seat=one['name'], text=one['text']) for one in own
                  if one['stage'] == 'host_summary' and one['text']]
        if lines:
            parts.append('\n\n'.join([topic_heading(topic), *lines]))
    return said('topic_digest', earlier='\n\n'.join(parts)) if parts else ''


def by_topic(rows: Sequence[Mapping[str, Any]], topics: Sequence[Mapping[str, Any]],
             line: Callable[[Mapping[str, Any]], str],
             stages: Sequence[Mapping[str, Any]] | None = None) -> list[str]:
    """Every turn as `line` gives it; under each topic's heading when the table has topics, followed, when `stages`
    is given, by what that topic's stages gave."""
    if not topics:
        return [line(row) for row in rows]
    lines: list[str] = []
    for topic in topics:
        lines.append(topic_heading(topic))
        lines += [line(row) for row in rows if row.get('topic') == topic['topic']]
        if stages is not None:
            lines += topic_record(topic, stages)
    return lines


def review(discussion: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], names: Sequence[str],
           topics: Sequence[Mapping[str, Any]] = ()) -> str:
    """The full review: the table, its rules once, then every turn's short line, under its topic's heading when the
    table has topics."""
    lines = [said('review_intro', discussion=discussion['number'], subject=discussion['subject'],
                  rules=rules(names, discussion))]
    lines += by_topic(rows, topics, short)
    return '\n'.join(lines) + '\n'


def record(discussion: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], names: Sequence[str],
           topics: Sequence[Mapping[str, Any]] = (), stages: Sequence[Mapping[str, Any]] = ()) -> str:
    """The whole record the report is written from: the rules, the opening, then every turn as the seats read it;
    for a table with topics, each topic's turns under its heading and then what its stages gave."""
    lines = [rules(names, discussion), said('record_opening', opening=discussion['opening'])]
    lines += by_topic(rows, topics, entry, stages)
    return said('report', record='\n\n'.join(lines), writing=writing(discussion))


def writing(discussion: Mapping[str, Any]) -> str:
    """How what the owner reads on its own is written, the host's summary and the final report: standalone, with no
    references, in the project's own writing rules, `docs/taste.md` in its folder when it has one, read each time."""
    taste = ''
    if discussion.get('folder'):
        with contextlib.suppress(OSError, UnicodeDecodeError):
            taste = (Path(str(discussion['folder'])) / 'docs' / 'taste.md').read_text(encoding='utf-8').strip()
    return said('writing_for_owner', taste=taste or said('taste_default'))


def slug(text: str, words: int = 6) -> str:
    """A file-name subject: the first words of the text, lowercase, joined by hyphens."""
    found = re.findall(r'[a-z0-9]+', text.lower())[:words]
    return '-'.join(found) or 'discussion'
