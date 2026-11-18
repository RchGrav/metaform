"""The blind-spot critic of a project held in the project store (`metaform.project`): each blind spot the critic
raises is one record of the project's `challenges` overlay, at the element it concerns, and the person's answer and
approval are fields of that record.

Kickoff 2026-11-17, Phase 3, decision t-legacy-keep: every feature of the old store is kept and moved onto the project
store. In the old store a critic run is a blind-spot layer, its challenges are that layer's items and their answers
rows beside it (LAYER-014, LAYER-015, STORE-040). Here a run is named the same way, `blind_spot_<mode>_<stamp>`, and
each record carries it with `blinded`, the provenance the layer kept; `answer` holds A, B or C, then plan once a
person approves a B, with `link`, `answered` and `approved`. The overlay is defined beneath the project's overlay root
when `map critic` first runs there. Each change names the record it found, id and revision (F02).

The intake's `concerns` overlay is not reused: it holds the drift an intake met while tracing, marked missing,
broken or exclude, with evidence required, and has no place for an answer, a link or a run.

What has no faithful place there is refused by name. A link to a join, `join:<id>`: a want has no id in the store,
it is named by its holder and the element it wants (F13), so a C answer links the element that handles it. A run's
new elements and joins: the store has no layer to hold them apart from the map, so the critic describes what it would
add in its challenge, and an approved B becomes a plan with no element of its own.
"""
from __future__ import annotations

from datetime import UTC, datetime
from importlib import resources
from typing import Any, cast

from metaform import project as project_store
from metaform import prompt_files
from metaform.data import ChallengeState, Node, Notice, Outcome
from metaform.module import Stop

OVERLAY = 'challenges'
ANSWERS = ('A', 'B', 'C')


def definition(project: str) -> dict[str, object]:
    """The challenges overlay's definition in one project, whose paths its address examples are."""
    return {
        'description': ('The blind spots a critic run raised at this element: each record is one challenge, with the '
                        "person's answer once given."),
        'instruction': ('Add one record for each blind spot, at the element it concerns, naming the run map critic '
                        'gave. A blind spot about a want is written at the element holding the want, with want naming '
                        'the element wanted. answer, link, answered and approved are written by metaform map answer and '
                        'metaform map approve.'),
        'run': {'type': 'text', 'rule': 'The critic run that raised it, as map critic named the run.',
                'example': 'blind_spot_fast_20261117t093000z'},
        'blinded': {'type': 'boolean', 'rule': 'true when the critic was kept from the code (fast mode); false when it '
                                               'read the code (critic mode).', 'example': True},
        'challenge': {'type': 'text', 'rule': 'The blind spot: what the design overlooks, and how and why taking it up '
                                              'makes the project better.',
                      'example': 'Nothing recovers the timer loop when it hangs, so a dish is never rung.'},
        'want': {'type': 'address', 'rule': "When it concerns one of this element's wants: the wanted element's path.",
                 'example': f'{project}.code.masher.widget', 'optional': True},
        'answer': {'type': 'A | B | C | plan',
                   'rule': 'A not useful, B useful, C already handled; plan once a person approves a B. Left out while '
                           'open.', 'example': 'B', 'optional': True},
        'link': {'type': 'address', 'rule': 'For C: the path of the element that already handles it.',
                 'example': f'{project}.code.masher.widget', 'optional': True},
        'answered': {'type': 'text', 'rule': 'When it was answered, as a date and time.',
                     'example': '2026-11-17T09:30:00Z', 'optional': True},
        'approved': {'type': 'text', 'rule': 'When a person approved it as a plan, as a date and time.',
                     'example': '2026-11-17T09:45:00Z', 'optional': True},
    }


def _now() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def _local(project: str, path: str) -> str:
    """An element's address without the project's name, as the map verbs write it."""
    return path[len(project) + 1:] if path.startswith(project + '.') else path


def _records(project: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], project_store.overlay_records(project, OVERLAY) or [])


def _done(answer: dict[str, object]) -> None:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The challenge was not changed.'),
                   str(answer.get('remediation') or 'metaform help map answer'))


def has_challenges(project: str) -> bool:
    """Whether the project holds a challenge, so the verbs that read and answer them are listed over MCP."""
    return bool(_records(project))


def critic(project: str, sighted: bool) -> str:
    """One critic run: its name, the challenges overlay defined on the first run, and the critic prompt with the
    project's map and specification as one document."""
    drawn = project_store.drawn(project)
    if drawn is None:
        raise Stop(f"{project}'s map could not be read from the project store.", f'the project tool: {{"map": "{project}"}}')
    if not any(one.get('key') == OVERLAY for one in cast(list[dict[str, Any]], drawn['overlays'])):
        _done(project_store.run({'add': {f'{project}.overlay.{OVERLAY}': definition(project)}}))
    mode = 'critic' if sighted else 'fast'
    taken = {str(one.get('run')) for one in _records(project)}
    base = f'blind_spot_{mode}_{datetime.now(UTC).strftime("%Y%m%dt%H%M%Sz")}'
    name, count = base, 1
    while name in taken:
        count += 1
        name = f'{base}_{count}'
    document = project_store.specification_document(project)
    if document.get('status') == 'error':
        raise Stop(str(document.get('message')), f'the project tool: {{"map": "{project}"}}')
    folder = resources.files(__package__ or 'metaform.modules.map')
    return (prompt_files.required(folder, 'blind_spot_challenge') + '\n\n'
            + prompt_files.markdown(folder, f'critic_{mode}_in_store', run=name, project=project,
                                    blinded='false' if sighted else 'true',
                                    metaform=str(document.get('document') or '').strip()))


def challenges(project: str, run: str) -> str:
    """The answer prompt with each challenge of one critic run and its state, LAYER-015."""
    found = [one for one in _records(project) if one.get('run') == run]
    if not found:
        runs = sorted({str(one.get('run')) for one in _records(project)})
        raise Stop(f'No challenge of the run {run} is recorded in {project}.',
                   f"metaform map challenges layer=<run>, one of: {', '.join(runs)}" if runs else 'metaform map critic')
    lines: list[str] = []
    for one in found:
        where = f"element:{_local(project, str(one['element']))}"
        if one.get('want'):
            where += f" want:{_local(project, str(one['want']))}"
        lines.append(f"{one['record']}  {one.get('answer') or 'open'}  {where}  {one.get('challenge')}")
    # the store's own answer prompt: a want has no id in the store, so C links an element only (verifier
    # helper-ef8580be returned the old prompt, which offered link=join:<id>, refused here)
    return prompt_files.markdown(resources.files(__package__ or 'metaform.modules.map'),
                                 'answer_challenges_in_store', layer=run, challenges='\n'.join(lines))


def _found(project: str, record: str) -> dict[str, Any]:
    found = next((one for one in _records(project) if one.get('record') == record), None)
    if found is None:
        raise Stop(f"{record} is not a challenge of {project}: a challenge is named by its record id.",
                   'metaform map challenges layer=<run>')
    return found


def _update(found: dict[str, Any], fields: dict[str, object]) -> None:
    """Change one challenge where it is, naming the record and revision it was read at (F02)."""
    _done(project_store.run({'update': {str(found['element']): {OVERLAY: [
        {'position': found['position'], 'record': found['record'], 'revision': found['revision'], **fields}]}}}))


def answer(project: str, record: str, state: str, link: str | None) -> ChallengeState | Outcome:
    """Record a challenge's answer on its record, as the old store records it beside the critic's layer, STORE-040."""
    if state == 'plan':
        return Outcome((Notice('answer', 'plan comes only from metaform map approve, which a person runs; nothing '
                                         'was written. Answer A, B or C.'),))
    if state not in ANSWERS:
        raise Stop(f'{state!r} is not an answer: use A, B or C.', f'metaform map answer {record} A')
    found = _found(project, record)
    notices: list[Notice] = []
    if found.get('answer') == 'plan':
        notices.append(Notice('challenge', f'Challenge {record} was already approved as a plan; this answer was '
                                           'stored as given.'))
    linked: str | None = None
    if state == 'C':
        if link is None:
            notices.append(Notice('link', 'A C answer names the element that already handles the challenge; give '
                                          'it with link=element:<address>. The answer was stored without it.'))
        else:
            kind, _, address = link.partition(':') if ':' in link else ('element', '', link)
            if kind != 'element':
                raise Stop(f"{link} has no place in the project store, where {project}'s map is kept: a want there "
                           'has no id, it is named by its holder and the element it wants. Link the element that '
                           'handles the challenge.', f'metaform map answer {record} C link=element:<address>')
            linked = f'{project}.{_local(project, address)}'
            drawn = project_store.drawn(project) or {}
            if linked not in {str(one['address']) for one in cast(list[dict[str, Any]], drawn.get('elements', []))}:
                notices.append(Notice('link', f'No element is at {_local(project, linked)}; the link was stored as '
                                              'given.'))
    stamp = _now()
    _update(found, {'answer': state, 'link': linked, 'answered': stamp})
    return ChallengeState(record, cast(Any, state), Node.of('element', _local(project, linked)) if linked else None,
                          stamp, cast(str | None, found.get('approved')), tuple(notices))


def approve(project: str, record: str) -> ChallengeState:
    """A person approves a B answer; it becomes a plan, STORE-040. The store holds no element a run added, so the plan
    carries none."""
    found = _found(project, record)
    if found.get('answer') != 'B':
        raise Stop(f"Challenge {record} is {found.get('answer') or 'open'}; only a challenge answered B is approved.",
                   f'metaform map answer {record} B')
    stamp = _now()
    _update(found, {'answer': 'plan', 'approved': stamp})
    return ChallengeState(record, 'plan', None, str(found.get('answered') or ''), stamp)
